"""Manual point-level spot check. ESPN gives no point score inside a game, so
use this at break points / tiebreaks where the 0-0 assumption is off by 5-8 pts.

    python fair.py --tour ATP --best-of 5 --anchor 0.92 --sets 0-1 --games 2-2 --server A --pts 30-40 --mid 0.67
    python fair.py --tour WTA --best-of 3 --anchor 0.55 --sets 1-1 --games 6-6 --server B --tb 5-8 --mid 0.10

All scores are A-B. `pts` accepts 0/15/30/40/AD or raw counts.
"""
import argparse
from tennis_markov import fair_and_update, solve_d

PT = {"0": 0, "15": 1, "30": 2, "40": 3, "AD": 4, "A": 4}


def pair(s, conv=int):
    a, b = s.replace(":", "-").split("-")
    return conv(a), conv(b)


def pt(x):
    x = x.upper()
    return PT[x] if x in PT else int(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tour", choices=["ATP", "WTA"], required=True)
    ap.add_argument("--best-of", type=int, default=None)
    ap.add_argument("--anchor", type=float, required=True, help="pre-match P(A), e.g. Kalshi last trade before start")
    ap.add_argument("--sets", default="0-0")
    ap.add_argument("--games", default="0-0")
    ap.add_argument("--server", choices=["A", "B", "?"], default="?")
    ap.add_argument("--pts", default="0-0", help="current game points A-B (0/15/30/40/AD)")
    ap.add_argument("--tb", default=None, help="tiebreak points A-B, only at 6-6")
    ap.add_argument("--mid", type=float, default=None, help="market mid for A, to compute the implied update")
    a = ap.parse_args()
    best_of = a.best_of or (5 if a.tour == "ATP" else 3)
    server = None if a.server == "?" else "AB".index(a.server)
    d_pre = solve_d(a.tour, best_of, a.anchor, server=None)
    state = {"sets": pair(a.sets), "games": pair(a.games), "server": server,
             "pts": pair(a.pts, pt), "tb_pts": pair(a.tb) if a.tb else None}
    fair, d_live, upd = fair_and_update(a.tour, best_of, d_pre, a.mid, **state)
    print(f"anchor {a.anchor:.3f} -> d_pre {d_pre:+.4f}")
    print(f"fair  {fair:.3f}")
    if a.mid is not None:
        print(f"mid   {a.mid:.3f}   gap {fair - a.mid:+.3f}   market re-rates A's serve by {upd:+.1f} pts (d_live {d_live:+.4f})")
    # sensitivity: what a one-point swing does to fair at this state
    if state["tb_pts"] is None and server is not None:
        pa, pb = state["pts"]
        for lab, p in (("A wins next pt", (pa + 1, pb)), ("B wins next pt", (pa, pb + 1))):
            s2 = dict(state, pts=p)
            f2, _, _ = fair_and_update(a.tour, best_of, d_pre, None, **s2)
            print(f"  {lab}: {f2:.3f} ({f2 - fair:+.3f})")


if __name__ == "__main__":
    main()
