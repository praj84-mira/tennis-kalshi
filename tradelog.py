"""Log a discretionary trade BEFORE the match resolves. Standing rule from the
brief: ten of these is a sample; zero is a story about the two that won.

    python tradelog.py KXATPMATCH-26SEP03BERDEJ-BER yes 0.31 10 "1-2 down but 4-3 up, fair 0.41 vs 0.31"

Pulls the latest monitor row for the ticker (fair, mid, score) if one exists
so the log carries the model's number at entry time.
"""
import csv
import os
import sys
from datetime import datetime, timezone

from monitor import DATA, LOG

TRADES = os.path.join(DATA, "trades.csv")
COLS = ["ts", "ticker", "side", "price", "contracts", "fair", "mid", "score", "reason"]


def latest_row(ticker):
    if not os.path.exists(LOG):
        return None
    last = None
    with open(LOG) as f:
        for r in csv.DictReader(f):
            if ticker in (r["ticker_a"], r["ticker_b"]):
                last = r
    return last


def main():
    if len(sys.argv) < 6:
        print(__doc__)
        sys.exit(1)
    ticker, side, price, n, reason = sys.argv[1], sys.argv[2].lower(), float(sys.argv[3]), float(sys.argv[4]), " ".join(sys.argv[5:])
    assert side in ("yes", "no")
    if 0.45 <= price <= 0.55:
        print("WARNING: standing rule says no taker entries between 45c and 55c (max-fee coin-flip zone).")
    r = latest_row(ticker)
    fair = mid = score = ""
    if r:
        flip = ticker == r["ticker_b"]
        if r["fair"]:
            fair = f"{1 - float(r['fair']):.3f}" if flip else r["fair"]
        if r["mid"]:
            mid = f"{1 - float(r['mid']):.3f}" if flip else r["mid"]
        score = f"{r['sets_a']}-{r['sets_b']} {r['games_a']}-{r['games_b']} sv={r['server']} @{r['ts']}"
    os.makedirs(DATA, exist_ok=True)
    new = not os.path.exists(TRADES)
    with open(TRADES, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "ticker": ticker, "side": side,
                    "price": price, "contracts": n, "fair": fair, "mid": mid, "score": score, "reason": reason})
    print(f"logged: {side} {n:g} @ {price} on {ticker}  model fair={fair or 'n/a'} mid={mid or 'n/a'}  {score}")


if __name__ == "__main__":
    main()
