"""Backtest H1/H2/reload on Kalshi's own history: every settled ATP/WTA match
market since the series opened (Wimbledon onward), 1-minute price path,
joined to ESPN for scheduled start time and final scoreline.

What this CAN test (price path + outcome only):
  * in-play calibration: do 10c contracts win 10% of the time? do 85c ones win 85%?
  * pre-match calibration: is the opening line right?
  * H1 favorites, H2 longshots, and the best-of-five "reload" as price rules
What it CANNOT test: the score-conditional Markov model. ESPN has no
historical play-by-play. That still needs the live monitor.

    python backtest.py fetch      # ~1800 matches, cached in data/hist/ (re-runnable)
    python backtest.py analyze    # prints report, writes data/hist/report.txt
"""
import concurrent.futures as cf
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.parse
from datetime import datetime, timezone, timedelta

import feeds
from feeds import KALSHI, SERIES, fee, name_key, iso_ts, _get, _f

HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "hist")
EVENTS = os.path.join(HIST, "events.json")
REPORT = os.path.join(HIST, "report.txt")
ESPN_DATE = "https://site.api.espn.com/apis/site/v2/sports/tennis/{league}/scoreboard?dates={d}"


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


# ================================================================ fetch
def list_settled(series):
    out, cursor = [], None
    while True:
        p = {"series_ticker": series, "status": "settled", "limit": 200}
        if cursor:
            p["cursor"] = cursor
        d = _get(f"{KALSHI}/markets", p)
        out += d.get("markets", [])
        cursor = d.get("cursor")
        if not cursor:
            break
    return out


def parse_rules(r):
    m = re.search(r"in the (.+?) after a ball", r or "")
    tourn = m.group(1) if m else ""
    rnd = ""
    m2 = re.search(r"(Round Of \d+|Qualification.*|Quarterfinal|Semifinal|Final)$", tourn)
    if m2:
        rnd = m2.group(1)
        tourn = tourn[: m2.start()].strip()
    return tourn, rnd


def candles(series, ticker, start, end):
    cs = _get(f"{KALSHI}/series/{series}/markets/{ticker}/candlesticks",
              {"start_ts": int(start), "end_ts": int(end), "period_interval": 1}).get("candlesticks", [])
    rows = []
    for c in cs:
        b, a = _f(c.get("yes_bid", {}).get("close_dollars")), _f(c.get("yes_ask", {}).get("close_dollars"))
        rows.append([int(c["end_period_ts"]), b, a, _f(c.get("price", {}).get("close_dollars")), _f(c.get("volume_fp")) or 0.0])
    return rows


def espn_days(d0, d1):
    """Singles competitions by date across both league endpoints."""
    out = {}
    day = d0
    while day <= d1:
        for lg in ("atp", "wta"):
            try:
                d = _get(ESPN_DATE.format(league=lg, d=day.strftime("%Y%m%d")))
            except RuntimeError as e:
                print("espn", day, lg, e, file=sys.stderr)
                continue
            for ev in d.get("events", []):
                for g in ev.get("groupings", []):
                    gname = g.get("grouping", {}).get("displayName", "")
                    tour = "ATP" if gname == "Men's Singles" else "WTA" if gname == "Women's Singles" else None
                    if not tour:
                        continue
                    for c in g.get("competitions", []):
                        comps = [x for x in c.get("competitors", []) if "athlete" in x]
                        if len(comps) != 2:
                            continue
                        keys = frozenset(name_key(x["athlete"].get("displayName", "")) for x in comps)
                        notes = " ".join(n.get("text", "") for n in c.get("notes", []))
                        out.setdefault((tour, keys), []).append({
                            "id": c.get("id"), "start_ts": iso_ts(c.get("date")), "event": ev.get("name"),
                            "best_of": int((c.get("format") or {}).get("regulation", {}).get("periods") or (5 if tour == "ATP" else 3)),
                            "notes": notes, "state": c.get("status", {}).get("type", {}).get("state"),
                        })
        day += timedelta(days=1)
    return out


def fetch():
    os.makedirs(HIST, exist_ok=True)
    events = {}
    for tour, series in SERIES.items():
        ms = list_settled(series)
        print(f"{series}: {len(ms)} settled markets", file=sys.stderr)
        by_ev = {}
        for m in ms:
            by_ev.setdefault(m["event_ticker"], []).append(m)
        for ev, pair in by_ev.items():
            if len(pair) != 2 or any(m.get("result") not in ("yes", "no") for m in pair):
                continue
            pair.sort(key=lambda m: m["ticker"])
            a, b = pair
            tourn, rnd = parse_rules(a.get("rules_primary"))
            events[ev] = {
                "event_ticker": ev, "tour": tour, "series": series, "tournament": tourn, "round": rnd,
                "ticker_a": a["ticker"], "ticker_b": b["ticker"],
                "player_a": a.get("yes_sub_title") or "", "player_b": b.get("yes_sub_title") or "",
                "result_a": 1 if a["result"] == "yes" else 0,
                "open_ts": ts(a["open_time"]), "close_ts": ts(a["close_time"]),
                "volume": _f(a.get("volume_fp")) or 0.0,
            }
    # ESPN join for start time / best-of / scoreline
    d0 = datetime.fromtimestamp(min(e["open_ts"] for e in events.values()), tz=timezone.utc).date()
    d1 = datetime.fromtimestamp(max(e["close_ts"] for e in events.values()), tz=timezone.utc).date()
    print(f"ESPN {d0}..{d1}", file=sys.stderr)
    espn = espn_days(d0, d1)
    matched = 0
    for e in events.values():
        cands = espn.get((e["tour"], frozenset([name_key(e["player_a"]), name_key(e["player_b"])])), [])
        cands = [c for c in cands if c["start_ts"] and e["open_ts"] - 86400 <= c["start_ts"] <= e["close_ts"]]
        if cands:
            c = min(cands, key=lambda c: abs(c["start_ts"] - e["close_ts"]))
            e.update({"start_ts": c["start_ts"], "best_of": c["best_of"], "scoreline": c["notes"], "espn_id": c["id"]})
            matched += 1
        else:
            e.update({"start_ts": None, "best_of": 5 if (e["tour"] == "ATP" and any(k in e["tournament"] for k in ("Wimbledon", "US Open", "French", "Australian"))) else 3, "scoreline": "", "espn_id": None})
    print(f"events {len(events)}  espn-matched {matched}", file=sys.stderr)
    # candles, cached per event
    have = {}
    if os.path.exists(EVENTS):
        with open(EVENTS) as f:
            have = {e["event_ticker"]: e for e in json.load(f) if e.get("candles")}
    todo = [e for e in events.values() if e["event_ticker"] not in have]
    print(f"candles to fetch: {len(todo)}", file=sys.stderr)

    def work(e):
        for i in range(3):
            try:
                return e["event_ticker"], candles(e["series"], e["ticker_a"], e["open_ts"], e["close_ts"] + 120)
            except RuntimeError as ex:
                time.sleep(2 * (i + 1))
                err = ex
        print("candles failed", e["ticker_a"], err, file=sys.stderr)
        return e["event_ticker"], None

    done = 0
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for ev, cs in ex.map(work, todo):
            events[ev]["candles"] = cs
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(todo)}", file=sys.stderr)
                _save(events, have)
    _save(events, have)
    print("saved", EVENTS, file=sys.stderr)


def _save(events, have):
    out = []
    for ev, e in events.items():
        if e.get("candles") is None and ev in have:
            e = dict(e, candles=have[ev]["candles"])
        out.append(e)
    tmp = EVENTS + ".tmp"
    with open(tmp, "w") as f:
        json.dump(out, f)
    os.replace(tmp, EVENTS)


# ============================================================== analyze
def quotes(e):
    """In-play candles with a real two-sided quote: (ts, bid, ask, mid)."""
    st = e.get("start_ts")
    out = []
    for t, b, a, _, _ in e.get("candles") or []:
        if st is None or t < st or t > e["close_ts"]:
            continue
        if b is None or a is None or b <= 0 or a >= 1 or a - b > 0.15:
            continue
        out.append((t, b, a, 0.5 * (a + b)))
    return out


def prematch(e):
    st = e.get("start_ts")
    if st is None:
        return None
    last = None
    for t, b, a, _, _ in e.get("candles") or []:
        if t >= st:
            break
        if b is not None and a is not None and b > 0 and a < 1 and a - b <= 0.15:
            last = 0.5 * (a + b)
    return last


def stat(pnls):
    n = len(pnls)
    if n == 0:
        return "n=0"
    m = statistics.fmean(pnls)
    sd = statistics.pstdev(pnls) if n > 1 else 0.0
    t = m / (sd / math.sqrt(n)) if sd > 0 else float("nan")
    wins = sum(1 for p in pnls if p > 0)
    return f"n={n:<4d} mean={m:+.4f}/contract  sd={sd:.3f}  t={t:+.2f}  win%={wins / n:.0%}"


def strategy(events, name, entry, filt=lambda e: True, maker=False):
    """entry(e, qs, pre) -> (price, is_yes) or None. Hold to settlement.
    Taker: pay ask (or 1-bid for NO) + taker fee. Maker (upper bound): fill at
    bid (or 1-ask for NO) + maker fee, assuming the resting order fills."""
    pnls, prices = [], []
    for e in events:
        if not filt(e):
            continue
        qs = quotes(e)
        pre = prematch(e)
        if not qs or pre is None:
            continue
        r = entry(e, qs, pre)
        if not r:
            continue
        px, is_yes = r
        y = e["result_a"] if is_yes else 1 - e["result_a"]
        pnls.append((y - px) - fee(px, 1, maker))
        prices.append(px)
    label = f"{name:<58}"
    if pnls:
        label += f" avg_px={statistics.fmean(prices):.2f} realized={statistics.fmean([p + fee(px, 1, maker) + px for p, px in zip(pnls, prices)]):.2f}"
    return f"{label}\n      {stat(pnls)}"


def calibration(events, lo=0.0, hi=1.0, step=0.05):
    """One observation per match per bin per side: the first in-play minute the
    mid enters that bin. Realized win rate vs mid, and taker return at ask."""
    bins = {}
    for e in events:
        seen = set()
        for t, b, a, mid in quotes(e):
            for side in (0, 1):
                m = mid if side == 0 else 1 - mid
                ask = a if side == 0 else 1 - b
                k = min(int(m / step), int(1 / step) - 1)
                if (side, k) in seen:
                    continue
                seen.add((side, k))
                y = e["result_a"] if side == 0 else 1 - e["result_a"]
                bins.setdefault(k, []).append((m, y, (y - ask) - fee(ask)))
    lines = [f"{'mid bin':<10}{'n':>6}{'avg mid':>9}{'win rate':>10}{'bias':>8}{'taker ret':>11}{'t':>7}"]
    for k in sorted(bins):
        rows = bins[k]
        n = len(rows)
        am = statistics.fmean(r[0] for r in rows)
        wr = statistics.fmean(r[1] for r in rows)
        ret = [r[2] for r in rows]
        mr = statistics.fmean(ret)
        sd = statistics.pstdev(ret) if n > 1 else 0
        t = mr / (sd / math.sqrt(n)) if sd > 0 else float("nan")
        lines.append(f"{k * step:.2f}-{(k + 1) * step:.2f} {n:>6d}{am:>9.3f}{wr:>10.3f}{wr - am:>+8.3f}{mr:>+11.4f}{t:>+7.2f}")
    return "\n".join(lines)


def pre_calibration(events, step=0.10):
    bins = {}
    for e in events:
        pre = prematch(e)
        if pre is None:
            continue
        for side in (0, 1):
            m = pre if side == 0 else 1 - pre
            y = e["result_a"] if side == 0 else 1 - e["result_a"]
            k = min(int(m / step), int(1 / step) - 1)
            bins.setdefault(k, []).append((m, y))
    lines = [f"{'pre bin':<10}{'n':>6}{'avg':>8}{'win rate':>10}{'bias':>8}"]
    for k in sorted(bins):
        rows = bins[k]
        am, wr = statistics.fmean(r[0] for r in rows), statistics.fmean(r[1] for r in rows)
        lines.append(f"{k * step:.1f}-{(k + 1) * step:.1f} {len(rows):>6d}{am:>8.3f}{wr:>10.3f}{wr - am:>+8.3f}")
    return "\n".join(lines)


# --- entry rules -------------------------------------------------------
def fav_reload(drop, fav_min=0.70):
    """Pre-match favorite whose ask has fallen >= drop below its pre-match price
    (proxy for 'dropped a set'). Buy the favorite at the ask, first trigger."""
    def entry(e, qs, pre):
        side = 0 if pre >= 0.5 else 1
        p0 = pre if side == 0 else 1 - pre
        if p0 < fav_min:
            return None
        for t, b, a, mid in qs:
            ask = a if side == 0 else 1 - b
            if ask <= p0 - drop and ask >= 0.15:
                return ask, side == 0
        return None
    return entry


def longshot(max_ask, min_ask=0.02):
    """Buy either player the first time their in-play ask is <= max_ask."""
    def entry(e, qs, pre):
        for t, b, a, mid in qs:
            for side in (0, 1):
                ask = a if side == 0 else 1 - b
                if min_ask <= ask <= max_ask:
                    return ask, side == 0
        return None
    return entry


def favorite_band(lo, hi):
    """H1: buy a favorite the first time its in-play ask sits in [lo, hi]
    (1.3x-1.5x payout == 0.67-0.77)."""
    def entry(e, qs, pre):
        for t, b, a, mid in qs:
            for side in (0, 1):
                ask = a if side == 0 else 1 - b
                if lo <= ask <= hi:
                    return ask, side == 0
        return None
    return entry


def prematch_side(fav=True):
    def entry(e, qs, pre):
        side = 0 if (pre >= 0.5) == fav else 1
        t, b, a, mid = qs[0]
        return (a if side == 0 else 1 - b), side == 0
    return entry


def analyze():
    with open(EVENTS) as f:
        events = [e for e in json.load(f) if e.get("candles")]
    ok = [e for e in events if e.get("start_ts") and quotes(e)]
    L = []
    P = L.append
    P(f"Kalshi tennis match markets, settled, fetched {datetime.now(timezone.utc):%Y-%m-%d %H:%M}Z")
    P(f"events with candles {len(events)}   with ESPN start + in-play quotes {len(ok)}   "
      f"ATP {sum(e['tour'] == 'ATP' for e in ok)}  WTA {sum(e['tour'] == 'WTA' for e in ok)}   "
      f"best-of-5 {sum(e['best_of'] == 5 for e in ok)}")
    tourn = {}
    for e in ok:
        tourn[e["tournament"]] = tourn.get(e["tournament"], 0) + 1
    P("tournaments: " + ", ".join(f"{k} {v}" for k, v in sorted(tourn.items(), key=lambda x: -x[1])[:12]))
    P("\nFees: taker 0.07*P(1-P), maker 0.0175*P(1-P), rounded up per contract. All P&L is per $1 contract, hold to settlement.")

    P("\n== PRE-MATCH CALIBRATION (last quote before ESPN start; both sides) ==")
    P(pre_calibration(ok))
    P("\n== IN-PLAY CALIBRATION (first entry into each 5c bin per match per side) ==")
    P("bias = win rate - avg mid. Positive at high prices + negative at low prices = favorite-longshot bias.")
    P(calibration(ok))
    for tour in ("ATP", "WTA"):
        P(f"\n-- {tour} only --")
        P(calibration([e for e in ok if e["tour"] == tour]))

    P("\n== STRATEGIES (taker at displayed ask, first trigger per match) ==")
    P(strategy(ok, "pre-match: buy the favorite at first in-play ask", prematch_side(True)))
    P(strategy(ok, "pre-match: buy the underdog at first in-play ask", prematch_side(False)))
    for lo, hi in ((0.60, 0.70), (0.67, 0.77), (0.75, 0.85), (0.85, 0.92)):
        P(strategy(ok, f"H1 favorite band ask in [{lo:.2f},{hi:.2f}]", favorite_band(lo, hi)))
    for mx in (0.05, 0.10, 0.15, 0.20):
        P(strategy(ok, f"H2 longshot ask <= {mx:.2f}", longshot(mx)))
    for drop in (0.10, 0.15, 0.20, 0.25, 0.30):
        P(strategy(ok, f"reload: fav>=0.70 pre, ask fell >= {drop:.2f}  [best-of-5]", fav_reload(drop), lambda e: e["best_of"] == 5))
        P(strategy(ok, f"reload: fav>=0.70 pre, ask fell >= {drop:.2f}  [best-of-3]", fav_reload(drop), lambda e: e["best_of"] == 3))
    P("\n== SAME, AS MAKER (fill at bid, maker fee; UPPER BOUND, assumes the resting order fills) ==")
    for mx in (0.10, 0.20):
        P(strategy(ok, f"H2 longshot bid <= {mx:.2f} (maker)", longshot(mx), maker=True))
    for drop in (0.15, 0.25):
        P(strategy(ok, f"reload fav>=0.70, fell >= {drop:.2f} [best-of-5] (maker)", fav_reload(drop), lambda e: e["best_of"] == 5, maker=True))
    P("\nCaveats: one entry per match, hold to settlement, no exits. Reload uses a price drop as a")
    P("proxy for 'lost a set'. Retirements included (Kalshi settles them). Taker fills assume the")
    P("displayed ask was available at that minute; thin books make that optimistic. t > 2 with n > 100")
    P("before believing anything; the in-play bins are not independent across sides of one match.")
    rep = "\n".join(L)
    print(rep)
    with open(REPORT, "w") as f:
        f.write(rep)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    fetch() if cmd == "fetch" else analyze()
