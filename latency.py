"""The latency test the brief says still isn't done. One match, one number.

    python latency.py KXATPMATCH-26SEP03BERDEJ-BER

Polls the Kalshi book every ~0.7s and timestamps every price move. Each time
you SEE a point end on your screen, press Enter. The script prints how long
ago the last Kalshi move happened. If Kalshi moved BEFORE your screen showed
the point, the number is positive: that is how far behind you are. Ten
presses gives a distribution; that number decides whether in-play taking is
ever on the table.
"""
import sys
import threading
import time

import feeds

moves = []
stop = False


def poll(ticker):
    last = None
    while not stop:
        try:
            m = feeds.kalshi_market(ticker)
            cur = (m["bid"], m["ask"])
            if cur != last and last is not None:
                moves.append((time.time(), cur))
                print(f"\r  [kalshi moved to {cur[0]}/{cur[1]} at {time.strftime('%H:%M:%S')}]", end="", flush=True)
            last = cur
        except RuntimeError:
            pass
        time.sleep(0.7)


def main():
    global stop
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    t = threading.Thread(target=poll, args=(sys.argv[1],), daemon=True)
    t.start()
    print("Press Enter the moment a point ends on your screen. Ctrl-C to finish.")
    lags = []
    try:
        while True:
            input()
            now = time.time()
            if not moves:
                print("  no Kalshi move seen yet")
                continue
            lag = now - moves[-1][0]
            lags.append(lag)
            print(f"  screen is {lag:+.1f}s behind the last Kalshi move ({moves[-1][1]})")
    except (KeyboardInterrupt, EOFError):
        stop = True
        if lags:
            lags.sort()
            print(f"\n{len(lags)} samples: median {lags[len(lags) // 2]:.1f}s  min {lags[0]:.1f}s  max {lags[-1]:.1f}s")


if __name__ == "__main__":
    main()
