"""Strength uncertainty. Instead of one differential d fit to the anchor, use
d ~ Normal(mu, sigma). Consequences: (1) favorites win set 1 more often than
the point-estimate chain says (the market's set prices show this), and (2)
observed set results update the posterior over d, so losing a set is evidence
about the player, not just a scoreboard change. sigma is fit on history
(backtest_sets.py --fit) and held out.
"""
import math
from functools import lru_cache

from tennis_markov import serve_probs, match_win, match_win_avg_server, _set_dist_cached
from derivatives import current_set_winner

# 9-point Gauss-Hermite nodes/weights for N(0,1)
_GH = [(-4.512745833, 2.234584e-05), (-3.205429003, 0.002789141), (-2.076847979, 0.0499164068),
       (-1.023255663, 0.244097503), (0.0, 0.406349206), (1.023255663, 0.244097503),
       (2.076847979, 0.0499164068), (3.205429003, 0.002789141), (4.512745833, 2.234584e-05)]


def nodes(mu, sigma):
    if sigma <= 0:
        return [(mu, 1.0)]
    return [(mu + sigma * x, w) for x, w in _GH]


def _set_prob(pa, pb, final, server):
    """P(A wins a fresh set) given server (None = average)."""
    if server is None:
        return 0.5 * (sum(_set_dist_cached(pa, pb, 0, 0, 0, final)[:2]) + sum(_set_dist_cached(pa, pb, 0, 0, 1, final)[:2]))
    return sum(_set_dist_cached(pa, pb, 0, 0, server, final)[:2])


def posterior(tour, mu, sigma, best_of, sets=(0, 0), bases=None):
    """Weights over d nodes after observing the set results so far (order of
    set wins ignored; each observed set treated as a fresh non-final set)."""
    ws = []
    for d, w in nodes(mu, sigma):
        pa, pb = serve_probs(tour, d, bases)
        ps = _set_prob(pa, pb, False, None)
        like = ps ** sets[0] * (1 - ps) ** sets[1]
        ws.append((d, w * like))
    z = sum(w for _, w in ws) or 1.0
    return [(d, w / z) for d, w in ws]


def prob_mix(tour, mu, sigma, best_of, bases=None, update_on_sets=True, **state):
    """Mixture P(A wins match) from live state."""
    sets = state.get("sets", (0, 0))
    post = posterior(tour, mu, sigma, best_of, sets, bases) if update_on_sets else nodes(mu, sigma)
    tot = 0.0
    for d, w in post:
        pa, pb = serve_probs(tour, d, bases)
        st = dict(state)
        srv = st.pop("server", None)
        tot += w * (match_win_avg_server(pa, pb, best_of, **st) if srv is None else match_win(pa, pb, best_of, server=srv, **st))
    return tot


def set_prob_mix(tour, mu, sigma, best_of, sets=(0, 0), games=(0, 0), server=None, tb_pts=None, bases=None):
    post = posterior(tour, mu, sigma, best_of, sets, bases)
    return sum(w * current_set_winner(*serve_probs(tour, d, bases), best_of, sets, games, server, tb_pts=tb_pts) for d, w in post)


def solve_mu(tour, sigma, best_of, target, bases=None, lo=-0.5, hi=0.5):
    """mu such that the PRE-MATCH mixture probability equals the anchor."""
    target = min(max(target, 1e-4), 1 - 1e-4)
    f = lambda m: prob_mix(tour, m, sigma, best_of, bases=bases, update_on_sets=False, server=None)
    if target <= f(lo):
        return lo
    if target >= f(hi):
        return hi
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)
