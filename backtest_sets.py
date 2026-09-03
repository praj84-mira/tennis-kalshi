"""Are Kalshi's set-winner prices consistent with the match price?

The research brief's thesis: the match price is made carefully, the derived
prices less so. Cleanest historical test without a score timeline: at the
scheduled start, both the match market and the set-1 market are quoted and
the score is 0-0. Fit the chain to the match price, read off P(A wins set 1),
and score it against the set-1 market price on the actual set-1 result.

    python backtest_sets.py fetch     # needs data/hist/events.json from backtest.py
    python backtest_sets.py analyze
"""
import concurrent.futures as cf
import json
import math
import os
import re
import statistics
import sys
import time

from feeds import KALSHI, fee, _get, _f
from backtest import HIST, EVENTS, prematch, list_settled
from tennis_markov import serve_probs, solve_d
from derivatives import current_set_winner

SET_SERIES = {"ATP": "KXATPSETWINNER", "WTA": "KXWTASETWINNER"}
OUT = os.path.join(HIST, "sets.json")
REPORT = os.path.join(HIST, "report_sets.txt")


def fetch():
    with open(EVENTS) as f:
        events = {e["event_ticker"].split("-")[1]: e for e in json.load(f) if e.get("candles") and e.get("start_ts")}
    rows = []
    for tour, series in SET_SERIES.items():
        ms = list_settled(series)
        print(f"{series}: {len(ms)} settled", file=sys.stderr)
        for m in ms:
            parts = m["ticker"].split("-")          # KXATPSETWINNER-26SEP02PRIPAU-1-PRI
            if len(parts) != 4 or parts[2] != "1" or m.get("result") not in ("yes", "no"):
                continue
            e = events.get(parts[1])
            if not e or e["tour"] != tour:
                continue
            suffix_a = e["ticker_a"].split("-")[-1]
            if parts[3] != suffix_a:
                continue
            rows.append({"ticker": m["ticker"], "code": parts[1], "tour": tour, "best_of": e["best_of"],
                         "start_ts": e["start_ts"], "result": 1 if m["result"] == "yes" else 0,
                         "match_pre": prematch(e), "player_a": e["player_a"], "player_b": e["player_b"],
                         "tournament": e["tournament"]})
    print(f"set-1 markets joined to a match with a start time: {len(rows)}", file=sys.stderr)

    def work(r):
        for i in range(3):
            try:
                d = _get(f"{KALSHI}/markets/trades", {"ticker": r["ticker"], "max_ts": int(r["start_ts"]), "limit": 1})
                tr = d.get("trades") or []
                r["set_pre_trade"] = _f(tr[0]["yes_price_dollars"]) if tr else None
                # first trade after start too: the price the set actually opened at
                d2 = _get(f"{KALSHI}/markets/trades", {"ticker": r["ticker"], "min_ts": int(r["start_ts"]), "limit": 1000})
                tr2 = d2.get("trades") or []
                r["set_first_live_trade"] = _f(tr2[-1]["yes_price_dollars"]) if tr2 else None  # trades are newest-first
                r["n_live_trades"] = len(tr2)
                return r
            except RuntimeError:
                time.sleep(2 * (i + 1))
        r["set_pre_trade"] = None
        return r

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(work, rows))
    with open(OUT, "w") as f:
        json.dump(rows, f)
    print("saved", OUT, file=sys.stderr)


def brier(pairs):
    return statistics.fmean((p - y) ** 2 for p, y in pairs) if pairs else float("nan")


def analyze():
    with open(OUT) as f:
        rows = json.load(f)
    L = []
    P = L.append
    for label, key in (("PRE-START set-1 trade", "set_pre_trade"), ("FIRST LIVE set-1 trade", "set_first_live_trade")):
        ok = [r for r in rows if r.get(key) is not None and r.get("match_pre") is not None and 0.02 < r[key] < 0.98]
        P(f"\n== {label} vs chain fit to the match price ==   n={len(ok)}  ATP {sum(r['tour'] == 'ATP' for r in ok)}  WTA {sum(r['tour'] == 'WTA' for r in ok)}")
        if not ok:
            continue
        pairs_m, pairs_e, pnl, diffs = [], [], [], []
        bins = {}
        for r in ok:
            d = solve_d(r["tour"], r["best_of"], r["match_pre"], server=None)
            pa, pb = serve_probs(r["tour"], d)
            p_eng = current_set_winner(pa, pb, r["best_of"], (0, 0), (0, 0), None)
            p_mkt = r[key]
            y = r["result"]
            pairs_m.append((p_mkt, y))
            pairs_e.append((p_eng, y))
            diffs.append(p_eng - p_mkt)
            # naive: if engine says the market is >= 5 pts cheap on either side, buy that side
            # at the trade price + 2c (half a typical spread) as a taker
            if p_eng - p_mkt >= 0.05:
                px = min(p_mkt + 0.02, 0.99)
                pnl.append((y - px) - fee(px))
            elif p_mkt - p_eng >= 0.05:
                px = min(1 - p_mkt + 0.02, 0.99)
                pnl.append(((1 - y) - px) - fee(px))
            k = min(int(p_mkt / 0.1), 9)
            bins.setdefault(k, []).append((p_mkt, p_eng, y))
        P(f"Brier  market {brier(pairs_m):.4f}   engine {brier(pairs_e):.4f}   diff {brier(pairs_e) - brier(pairs_m):+.4f}  (negative = engine better)")
        P(f"engine - market: mean {statistics.fmean(diffs):+.4f}  sd {statistics.pstdev(diffs):.4f}  |diff|>=5pts in {sum(abs(x) >= 0.05 for x in diffs)} of {len(diffs)}")
        if pnl:
            m = statistics.fmean(pnl)
            sd = statistics.pstdev(pnl) if len(pnl) > 1 else 0
            t = m / (sd / math.sqrt(len(pnl))) if sd else float("nan")
            P(f"naive taker on >=5pt disagreements: n={len(pnl)} mean={m:+.4f}/contract sd={sd:.3f} t={t:+.2f}")
        P(f"{'mkt bin':<10}{'n':>5}{'avg mkt':>9}{'avg eng':>9}{'win rate':>10}{'mkt bias':>10}{'eng bias':>10}")
        for k in sorted(bins):
            b = bins[k]
            am, ae, wr = (statistics.fmean(x[i] for x in b) for i in range(3))
            P(f"{k / 10:.1f}-{(k + 1) / 10:.1f} {len(b):>5d}{am:>9.3f}{ae:>9.3f}{wr:>10.3f}{wr - am:>+10.3f}{wr - ae:>+10.3f}")
    P("\nCaveat: engine set-1 probability assumes an unknown first server (averaged). The market may know")
    P("the toss by the first live trade. Pre-start trades on set markets are sparse; n is what it is.")
    rep = "\n".join(L)
    print(rep)
    with open(REPORT, "w") as f:
        f.write(rep)


if __name__ == "__main__":
    fetch() if (sys.argv[1:] and sys.argv[1] == "fetch") else analyze()
