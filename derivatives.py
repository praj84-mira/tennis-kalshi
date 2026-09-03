"""Derivative prices from the same Markov chain: set-score distribution, total
sets, set winner, tiebreak-in-match, and the per-player counterfactuals from
the research brief (implied hold rate, break-even, sensitivities).

Kalshi lists these as separate series (KXATPSETWINNER, KXATPTOTALSETS,
KXATPEXACTMATCH, KXATPTIEBREAK, ...). The research brief's argument: the
match price is set by a market that runs the same chain with better data,
but the *derived* prices are made less carefully. Whether that is true is
what the backtest/derivatives path is for.

    python derivatives.py --tour ATP --anchor 0.75 --sets 0-1 --games 2-2 --server A
"""
import argparse
from functools import lru_cache

from tennis_markov import (game_win, serve_probs, solve_d, set_dist, _set_dist_cached, tb_win, match_win)


# ---------------------------------------------------------- set-level
@lru_cache(maxsize=None)
def _set_reach_tb(pa, pb, ga, gb, server):
    """P(this set reaches 6-6) from (ga, gb) with `server` serving next game."""
    if (ga >= 6 and ga - gb >= 2) or ga == 7 or (gb >= 6 and gb - ga >= 2) or gb == 7:
        return 0.0
    if ga == 6 and gb == 6:
        return 1.0
    pg = game_win(pa) if server == 0 else 1 - game_win(pb)
    return pg * _set_reach_tb(pa, pb, ga + 1, gb, 1 - server) + (1 - pg) * _set_reach_tb(pa, pb, ga, gb + 1, 1 - server)


def set_score_dist(pa, pb, best_of=3, sets=(0, 0), games=(0, 0), server=None, pts=(0, 0), tb_pts=None):
    """Distribution over final set scores {(sa, sb): p} from the live state.
    server=None averages over both."""
    if server is None:
        d0 = set_score_dist(pa, pb, best_of, sets, games, 0, pts, tb_pts)
        d1 = set_score_dist(pa, pb, best_of, sets, games, 1, pts, tb_pts)
        return {k: 0.5 * (d0.get(k, 0) + d1.get(k, 0)) for k in set(d0) | set(d1)}
    need = (best_of + 1) // 2
    out = {}

    def rec(sa, sb, srv, p, first):
        if p < 1e-12:
            return
        if sa >= need or sb >= need:
            out[(sa, sb)] = out.get((sa, sb), 0.0) + p
            return
        final = sa == need - 1 and sb == need - 1
        if first:
            aa, ab, ba, bb = set_dist(pa, pb, games[0], games[1], srv, final, pts, tb_pts)
        else:
            aa, ab, ba, bb = _set_dist_cached(pa, pb, 0, 0, srv, final)
        rec(sa + 1, sb, 0, p * aa, False)
        rec(sa + 1, sb, 1, p * ab, False)
        rec(sa, sb + 1, 0, p * ba, False)
        rec(sa, sb + 1, 1, p * bb, False)

    rec(sets[0], sets[1], server, 1.0, True)
    return out


def total_sets_dist(dist):
    out = {}
    for (sa, sb), p in dist.items():
        out[sa + sb] = out.get(sa + sb, 0.0) + p
    return out


def current_set_winner(pa, pb, best_of, sets, games, server, pts=(0, 0), tb_pts=None):
    need = (best_of + 1) // 2
    final = sets[0] == need - 1 and sets[1] == need - 1
    if server is None:
        return 0.5 * sum(sum(set_dist(pa, pb, games[0], games[1], s, final, pts, tb_pts)[:2]) for s in (0, 1))
    return sum(set_dist(pa, pb, games[0], games[1], server, final, pts, tb_pts)[:2])


def tiebreak_in_match(pa, pb, best_of, sets, games, server, tb_seen=False):
    """P(at least one tiebreak occurs from here on), given none has yet unless tb_seen."""
    if tb_seen or (games[0] == 6 and games[1] == 6):
        return 1.0
    if server is None:
        return 0.5 * (tiebreak_in_match(pa, pb, best_of, sets, games, 0) + tiebreak_in_match(pa, pb, best_of, sets, games, 1))
    need = (best_of + 1) // 2
    # P(no tiebreak in the rest): current set, then each future set. Future sets:
    # condition on set outcomes/servers via the 4-way dist; approximate the
    # "no TB" conditional as independent of who wins (small error).
    p_tb_now = _set_reach_tb(pa, pb, games[0], games[1], server)
    p_no = 1 - p_tb_now
    # expected number of further sets: walk the set-score tree
    dist = set_score_dist(pa, pb, best_of, sets, games, server)
    p_tb_fresh_a = _set_reach_tb(pa, pb, 0, 0, 0)
    p_tb_fresh_b = _set_reach_tb(pa, pb, 0, 0, 1)
    p_tb_fresh = 0.5 * (p_tb_fresh_a + p_tb_fresh_b)
    exp_no = 0.0
    for (sa, sb), p in dist.items():
        further = (sa + sb) - (sets[0] + sets[1]) - 1
        exp_no += p * (1 - p_tb_fresh) ** max(further, 0)
    return 1 - p_no * exp_no


# --------------------------------------------------- counterfactuals
def hold_rate(p):
    return game_win(p)


def profile(tour, best_of, d_pre, d_live=None, bases=None):
    """Implied hold rates and sensitivities. Returns dict of plain numbers."""
    pa, pb = serve_probs(tour, d_pre, bases)
    out = {"pa_pre": pa, "pb_pre": pb, "hold_a_pre": hold_rate(pa), "hold_b_pre": hold_rate(pb)}
    if d_live is not None:
        qa, qb = serve_probs(tour, d_live, bases)
        out.update(pa_live=qa, pb_live=qb, hold_a_live=hold_rate(qa), hold_b_live=hold_rate(qb))
    # sensitivity of pre-match P(A) to one serve-point of A's serve, of B's serve
    eps = 0.01
    base = 0.5 * (match_win(pa, pb, best_of, server=0) + match_win(pa, pb, best_of, server=1))
    up_a = 0.5 * (match_win(pa + eps, pb, best_of, server=0) + match_win(pa + eps, pb, best_of, server=1))
    up_b = 0.5 * (match_win(pa, pb + eps, best_of, server=0) + match_win(pa, pb + eps, best_of, server=1))
    out.update(p_match=base, dP_dSPW_a=(up_a - base) / eps / 100, dP_dSPW_b=(up_b - base) / eps / 100)
    # break-even: the differential at which the match is a coin flip
    out["breakeven_d"] = solve_d(tour, best_of, 0.5, server=None, bases=bases)
    return out


def pair(s):
    a, b = s.replace(":", "-").split("-")
    return int(a), int(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tour", choices=["ATP", "WTA"], required=True)
    ap.add_argument("--best-of", type=int, default=None)
    ap.add_argument("--anchor", type=float, required=True)
    ap.add_argument("--sets", default="0-0")
    ap.add_argument("--games", default="0-0")
    ap.add_argument("--server", choices=["A", "B", "?"], default="?")
    ap.add_argument("--mid", type=float, default=None)
    a = ap.parse_args()
    best_of = a.best_of or (5 if a.tour == "ATP" else 3)
    server = None if a.server == "?" else "AB".index(a.server)
    d_pre = solve_d(a.tour, best_of, a.anchor, server=None)
    pa, pb = serve_probs(a.tour, d_pre)
    sets, games = pair(a.sets), pair(a.games)
    dist = set_score_dist(pa, pb, best_of, sets, games, server)
    print(f"anchor {a.anchor:.3f}  d_pre {d_pre:+.4f}  pa {pa:.3f} pb {pb:.3f}  hold A {hold_rate(pa):.3f} B {hold_rate(pb):.3f}")
    print(f"P(A wins match) {sum(p for (x, y), p in dist.items() if x > y):.3f}")
    print(f"P(A wins current set) {current_set_winner(pa, pb, best_of, sets, games, server):.3f}")
    print(f"P(tiebreak in match, from here) {tiebreak_in_match(pa, pb, best_of, sets, games, server):.3f}")
    print("exact score:", "  ".join(f"{x}-{y} {p:.3f}" for (x, y), p in sorted(dist.items(), key=lambda kv: -kv[1])))
    print("total sets: ", "  ".join(f"{k}: {p:.3f}" for k, p in sorted(total_sets_dist(dist).items())))
    if a.mid is not None:
        d_live = solve_d(a.tour, best_of, a.mid, server=server, sets=sets, games=games)
        pr = profile(a.tour, best_of, d_pre, d_live)
        print(f"market at {a.mid:.2f} implies A holds {pr['hold_a_live']:.1%} (pre-match {pr['hold_a_pre']:.1%}), "
              f"B holds {pr['hold_b_live']:.1%} (pre {pr['hold_b_pre']:.1%})")
    pr = profile(a.tour, best_of, d_pre)
    print(f"sensitivity: +1 serve-pt for A -> P(A) {pr['dP_dSPW_a'] * 100:+.2f} pts;  +1 serve-pt for B -> {pr['dP_dSPW_b'] * 100:+.2f} pts;  break-even d {pr['breakeven_d']:+.4f}")


if __name__ == "__main__":
    main()
