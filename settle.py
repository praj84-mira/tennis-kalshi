"""Join monitor rows to Kalshi settlement and score model vs market.

    python settle.py                 # all rows
    python settle.py --min-gap 0.05  # only rows where |fair - mid| >= 0.05
    python settle.py --trades        # also score data/trades.csv

Brier = mean (p - y)^2, lower is better. `y` = 1 if player A won.
P&L is a naive, taker-at-displayed-ask, one-contract-per-row UPPER BOUND:
it assumes every flagged row was fillable at the logged ask and ignores
score staleness. Treat it as "if the edge is real, at most this much".
"""
import argparse
import csv
import json
import math
import os
import statistics
import sys

import feeds
from monitor import DATA, LOG

RESULTS = os.path.join(DATA, "results.json")
TRADES = os.path.join(DATA, "trades.csv")


def load_results():
    try:
        with open(RESULTS) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def resolve(tickers, cache):
    for t in tickers:
        if cache.get(t) in ("yes", "no"):
            continue
        try:
            m = feeds.kalshi_market(t)
        except RuntimeError as e:
            print(f"lookup failed {t}: {e}", file=sys.stderr)
            continue
        cache[t] = m["result"] if m["result"] in ("yes", "no") else m["status"]
    os.makedirs(DATA, exist_ok=True)
    with open(RESULTS, "w") as f:
        json.dump(cache, f, indent=1)
    return cache


def brier(pairs):
    return statistics.fmean((p - y) ** 2 for p, y in pairs) if pairs else float("nan")


def pnl_row(r, y):
    """One contract, taker, model side, at the logged bid/ask. Returns net $."""
    gap, bid, ask = float(r["gap"]), float(r["bid"]), float(r["ask"])
    if gap > 0:  # model says A is cheap: buy YES at ask
        px = ask
        return (y - px) - feeds.fee(px)
    px = 1 - bid  # buy NO at (1 - bid)
    return ((1 - y) - px) - feeds.fee(px)


def summarize(label, rows):
    if not rows:
        print(f"{label}: no rows")
        return
    model = brier([(float(r["fair"]), r["y"]) for r in rows])
    market = brier([(float(r["mid"]), r["y"]) for r in rows])
    closer = sum(1 for r in rows if abs(float(r["fair"]) - r["y"]) < abs(float(r["mid"]) - r["y"]))
    pnl = [pnl_row(r, r["y"]) for r in rows]
    n = len(rows)
    print(f"{label}")
    print(f"  rows {n}   matches {len({r['ticker_a'] for r in rows})}")
    print(f"  Brier  model {model:.4f}   market {market:.4f}   diff {model - market:+.4f}  (negative = model better)")
    print(f"  model closer on {closer}/{n} rows ({closer / n:.0%})")
    print(f"  naive taker P&L: total {sum(pnl):+.2f}  per contract {statistics.fmean(pnl):+.4f}"
          + (f"  sd {statistics.pstdev(pnl):.3f}" if n > 1 else ""))
    # one entry per match at the first flagged row: the version you could actually take
    first = {}
    for r in rows:
        first.setdefault(r["ticker_a"], r)
    p1 = [pnl_row(r, r["y"]) for r in first.values()]
    print(f"  first-flag-per-match P&L: total {sum(p1):+.2f} over {len(p1)} matches, per contract {statistics.fmean(p1):+.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-gap", type=float, default=0.0)
    ap.add_argument("--trades", action="store_true")
    ap.add_argument("--log", default=LOG)
    args = ap.parse_args()
    with open(args.log) as f:
        rows = [r for r in csv.DictReader(f) if r["fair"] != "" and r["mid"] != "" and r["gap"] != ""]
    cache = resolve(sorted({r["ticker_a"] for r in rows}), load_results())
    settled, pending = [], set()
    for r in rows:
        res = cache.get(r["ticker_a"])
        if res in ("yes", "no"):
            r["y"] = 1.0 if res == "yes" else 0.0
            settled.append(r)
        else:
            pending.add(r["ticker_a"])
    print(f"settled matches: {len({r['ticker_a'] for r in settled})}   pending: {len(pending)}")
    summarize("ALL settled rows", settled)
    flagged = [r for r in settled if abs(float(r["gap"])) >= args.min_gap]
    if args.min_gap > 0:
        summarize(f"FLAGGED |gap| >= {args.min_gap}", flagged)
        known = [r for r in flagged if r["server"] in ("A", "B")]
        summarize(f"FLAGGED with observed server", known)
    if args.trades and os.path.exists(TRADES):
        with open(TRADES) as f:
            tr = list(csv.DictReader(f))
        cache = resolve(sorted({t["ticker"] for t in tr}), cache)
        tot = 0.0
        print("\nDISCRETIONARY TRADES")
        for t in tr:
            res = cache.get(t["ticker"])
            px, n = float(t["price"]), float(t["contracts"])
            if res not in ("yes", "no"):
                print(f"  {t['ts']} {t['ticker']} {t['side']} {n:g}@{px:.2f}  pending")
                continue
            won = (res == "yes") == (t["side"] == "yes")
            net = n * ((1 - px) if won else -px) - feeds.fee(px, n)
            tot += net
            print(f"  {t['ts']} {t['ticker']} {t['side']} {n:g}@{px:.2f} fair={t['fair']}  {'WIN ' if won else 'LOSS'} {net:+.2f}   {t['reason'][:60]}")
        print(f"  total {tot:+.2f} over {len(tr)} trades")


if __name__ == "__main__":
    main()
