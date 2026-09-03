"""Exact nested Markov model for a tennis match: point -> game -> set -> match.

US Open rules: 7-point tiebreak at 6-6 in non-final sets, 10-point tiebreak at
6-6 in the final set, win by two. Points are i.i.d. given the server.

Conventions
    pa : P(A wins a point when A serves)
    pb : P(B wins a point when B serves)
    server : 0 = A, 1 = B  (whoever serves the *next* point / game)
All functions return P(A wins ...).
"""
from functools import lru_cache

BASE_SERVE = {"ATP": 0.64, "WTA": 0.57}


# ---------------------------------------------------------------- game
@lru_cache(maxsize=None)
def game_win(p, a=0, b=0):
    """P(server wins the game) from point score (a=server pts, b=receiver pts)."""
    if a >= 4 and a - b >= 2:
        return 1.0
    if b >= 4 and b - a >= 2:
        return 0.0
    if a >= 3 and b >= 3 and a == b:  # deuce closed form
        return p * p / (p * p + (1 - p) ** 2)
    return p * game_win(p, a + 1, b) + (1 - p) * game_win(p, a, b + 1)


# ------------------------------------------------------------ tiebreak
@lru_cache(maxsize=None)
def tb_win(pa, pb, target, a=0, b=0, server=0):
    """P(A wins a first-to-`target`, win-by-2 tiebreak) from (a, b) with
    `server` serving the next point. Rotation: 1 point, then 2, 2, 2..."""
    if a >= target and a - b >= 2:
        return 1.0
    if b >= target and b - a >= 2:
        return 0.0
    if a >= target - 1 and b >= target - 1 and a == b:
        # From a tie the next two points are always served by different
        # players, so the two-point cycle has fixed odds regardless of order.
        w = pa * (1 - pb)
        l = (1 - pa) * pb
        return w / (w + l)
    p = pa if server == 0 else 1 - pb
    nxt = 1 - server if (a + b) % 2 == 0 else server
    return p * tb_win(pa, pb, target, a + 1, b, nxt) + (1 - p) * tb_win(pa, pb, target, a, b + 1, nxt)


# ----------------------------------------------------------------- set
def _set_dist(pa, pb, ga, gb, server, final, pts=(0, 0), tb_pts=None):
    """Return (A wins & A serves next set, A wins & B next, B wins & A next,
    B wins & B next). `server` = who serves the next game (or next tiebreak
    point). Next-set first server = the player who would have served the
    following game, i.e. `server` at set end; after a tiebreak, 1-server."""
    target = 10 if final else 7
    if (ga >= 6 and ga - gb >= 2) or ga == 7:
        return (1.0, 0.0, 0.0, 0.0) if server == 0 else (0.0, 1.0, 0.0, 0.0)
    if (gb >= 6 and gb - ga >= 2) or gb == 7:
        return (0.0, 0.0, 1.0, 0.0) if server == 0 else (0.0, 0.0, 0.0, 1.0)
    if ga == 6 and gb == 6:
        ta, tb_ = tb_pts if tb_pts else (0, 0)
        t = tb_win(pa, pb, target, ta, tb_, server)
        # After the tiebreak the *other* player opens the next set relative
        # to who served the tiebreak's first point. If tb_pts are given we
        # don't know who opened; approximate with the current point server.
        nxt = 1 - server
        return (t, 0.0, 1 - t, 0.0) if nxt == 0 else (0.0, t, 0.0, 1 - t)
    if server == 0:
        pg = game_win(pa, pts[0], pts[1])
    else:
        pg = 1 - game_win(pb, pts[1], pts[0])
    w = _set_dist(pa, pb, ga + 1, gb, 1 - server, final)
    l = _set_dist(pa, pb, ga, gb + 1, 1 - server, final)
    return tuple(pg * x + (1 - pg) * y for x, y in zip(w, l))


_set_dist_cached = lru_cache(maxsize=None)(_set_dist)


def set_dist(pa, pb, ga=0, gb=0, server=0, final=False, pts=(0, 0), tb_pts=None):
    if pts == (0, 0) and tb_pts is None:
        return _set_dist_cached(pa, pb, ga, gb, server, final)
    return _set_dist(pa, pb, ga, gb, server, final, tuple(pts), tb_pts)


# --------------------------------------------------------------- match
@lru_cache(maxsize=None)
def _match_from_sets(pa, pb, best_of, sa, sb, server):
    need = (best_of + 1) // 2
    if sa >= need:
        return 1.0
    if sb >= need:
        return 0.0
    final = sa == need - 1 and sb == need - 1
    aa, ab, ba, bb = _set_dist_cached(pa, pb, 0, 0, server, final)
    return (aa * _match_from_sets(pa, pb, best_of, sa + 1, sb, 0)
            + ab * _match_from_sets(pa, pb, best_of, sa + 1, sb, 1)
            + ba * _match_from_sets(pa, pb, best_of, sa, sb + 1, 0)
            + bb * _match_from_sets(pa, pb, best_of, sa, sb + 1, 1))


def match_win(pa, pb, best_of=3, sets=(0, 0), games=(0, 0), server=0,
              pts=(0, 0), tb_pts=None):
    """P(A wins the match) from an arbitrary live state.

    sets   : sets won (A, B)
    games  : games in the current set (A, B)
    server : who serves the next point/game, 0=A 1=B
    pts    : points in the current game (A, B), as counts 0..N (not 15/30/40)
    tb_pts : points in the current tiebreak (A, B) if games == (6, 6)
    """
    sa, sb = sets
    need = (best_of + 1) // 2
    if sa >= need:
        return 1.0
    if sb >= need:
        return 0.0
    final = sa == need - 1 and sb == need - 1
    aa, ab, ba, bb = set_dist(pa, pb, games[0], games[1], server, final, pts, tb_pts)
    return (aa * _match_from_sets(pa, pb, best_of, sa + 1, sb, 0)
            + ab * _match_from_sets(pa, pb, best_of, sa + 1, sb, 1)
            + ba * _match_from_sets(pa, pb, best_of, sa, sb + 1, 0)
            + bb * _match_from_sets(pa, pb, best_of, sa, sb + 1, 1))


def match_win_avg_server(pa, pb, best_of=3, **kw):
    """Average over unknown server (coin toss or unobserved)."""
    return 0.5 * (match_win(pa, pb, best_of, server=0, **kw)
                  + match_win(pa, pb, best_of, server=1, **kw))


# ------------------------------------------------------------ strength
def serve_probs(tour, d):
    """Map a strength differential d to (pa, pb) around the tour base rate."""
    base = BASE_SERVE[tour]
    return _clip(base + d / 2), _clip(base - d / 2)


def _clip(x, lo=0.30, hi=0.95):
    return max(lo, min(hi, x))


def prob_at(tour, d, best_of, **state):
    pa, pb = serve_probs(tour, d)
    if state.get("server") is None:
        state.pop("server", None)
        return match_win_avg_server(pa, pb, best_of, **state)
    return match_win(pa, pb, best_of, **state)


def solve_d(tour, best_of, target, lo=-0.5, hi=0.5, **state):
    """Bisection: find d such that prob_at(tour, d, best_of, **state) = target."""
    target = min(max(target, 1e-4), 1 - 1e-4)
    flo, fhi = prob_at(tour, lo, best_of, **state), prob_at(tour, hi, best_of, **state)
    if target <= flo:
        return lo
    if target >= fhi:
        return hi
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        f = prob_at(tour, mid, best_of, **state)
        if f < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def fair_and_update(tour, best_of, d_pre, mid, **state):
    """fair   : P(A) now if only the score changed since the pre-match anchor.
       d_live : strength differential the live price implies at this score.
       update : serve-point re-rating of A implied by the market, in pct pts
                (= (pa_live - pa_pre) * 100)."""
    fair = prob_at(tour, d_pre, best_of, **state)
    if mid is None:
        return fair, None, None
    d_live = solve_d(tour, best_of, mid, **state)
    update = (d_live - d_pre) / 2 * 100
    return fair, d_live, update
