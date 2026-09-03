"""Per-player serve/return profiles from Jeff Sackmann's match CSVs.

Why: the engine's tour-constant serve rate (ATP 0.64 / WTA 0.57) gets the
LEVEL from the market anchor but assumes every match has the same SHAPE.
Two big servers produce more tiebreaks and make a break worth more; two
returners make a set lead worth less. That changes in-play fair value by a
few points at a set + break. Head-to-head, surface win rate, round, time of
day, form: those are pre-match inputs and the Kalshi opening price already
carries the market's view of them. We don't re-derive them.

Setup (on your machine; GitHub is not reachable from the remote session):
    git clone --depth 1 https://github.com/JeffSackmann/tennis_atp ../tennis_atp
    git clone --depth 1 https://github.com/JeffSackmann/tennis_wta ../tennis_wta
    python priors.py ../tennis_atp ../tennis_wta        # writes data/priors.json

Model (Barnett & Clarke 2005): P(A wins a point on A's serve) = f_A - g_B + g_avg
where f_A = A's serve points won %, g_B = B's return points won %, g_avg =
tour average return %. Rolling 52 weeks, hard-court matches weighted 2x,
shrunk to the tour mean with k=300 points so a thin sample stays near base.
"""
import csv
import glob
import json
import os
import sys
import unicodedata
from datetime import date, timedelta

from feeds import name_key

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "priors.json")
K = 300.0          # shrinkage in points
SURFACE_W = 2.0    # weight for matches on the target surface


def _i(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def _full_key(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return " ".join(s.split())


def load_matches(repo_dir, since):
    """Yield (date, surface, name, svpt, svwon, rtpt, rtwon) per player-match."""
    for path in sorted(glob.glob(os.path.join(repo_dir, "*_matches_20[0-9][0-9].csv"))):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                d = r.get("tourney_date") or ""
                if len(d) != 8 or date(int(d[:4]), int(d[4:6]), int(d[6:])) < since:
                    continue
                w_sv, w_1w, w_2w = _i(r.get("w_svpt")), _i(r.get("w_1stWon")), _i(r.get("w_2ndWon"))
                l_sv, l_1w, l_2w = _i(r.get("l_svpt")), _i(r.get("l_1stWon")), _i(r.get("l_2ndWon"))
                if not w_sv or not l_sv:
                    continue
                w_won, l_won = w_1w + w_2w, l_1w + l_2w
                sf = r.get("surface") or ""
                yield d, sf, r.get("winner_name", ""), w_sv, w_won, l_sv, l_sv - l_won
                yield d, sf, r.get("loser_name", ""), l_sv, l_won, w_sv, w_sv - w_won


def build(repo_dir, tour, surface="Hard", weeks=52, today=None):
    today = today or date.today()
    since = today - timedelta(weeks=weeks)
    acc = {}
    tot_sv = tot_svw = tot_rt = tot_rtw = 0.0
    for d, sf, name, svpt, svwon, rtpt, rtwon in load_matches(repo_dir, since):
        w = SURFACE_W if sf.lower() == surface.lower() else 1.0
        a = acc.setdefault(name, [0.0, 0.0, 0.0, 0.0, 0])
        a[0] += w * svpt; a[1] += w * svwon; a[2] += w * rtpt; a[3] += w * rtwon; a[4] += 1
        tot_sv += svpt; tot_svw += svwon; tot_rt += rtpt; tot_rtw += rtwon
    if not tot_sv:
        return {}
    f_avg, g_avg = tot_svw / tot_sv, tot_rtw / tot_rt
    out = {"_avg": {"serve": f_avg, "return": g_avg, "n_players": len(acc)}}
    for name, (sv, svw, rt, rtw, n) in acc.items():
        f = (svw + K * f_avg) / (sv + K)
        g = (rtw + K * g_avg) / (rt + K)
        out[_full_key(name)] = {"name": name, "key": name_key(name), "serve": round(f, 4), "return": round(g, 4), "n": n}
    return out


def lookup(priors, tour, name):
    """Find a player's profile by full name, then by surname."""
    p = priors.get(tour) or {}
    hit = p.get(_full_key(name))
    if hit:
        return hit
    k = name_key(name)
    cands = [v for kk, v in p.items() if kk != "_avg" and v.get("key") == k]
    return cands[0] if len(cands) == 1 else None


def bases_for(priors, tour, name_a, name_b):
    """(base_a, base_b) serve point-win rates for the engine, or None."""
    p = priors.get(tour) or {}
    avg = p.get("_avg")
    a, b = lookup(priors, tour, name_a), lookup(priors, tour, name_b)
    if not (avg and a and b):
        return None
    g = avg["return"]
    return a["serve"] - b["return"] + g, b["serve"] - a["return"] + g


def load():
    try:
        with open(OUT) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    atp, wta = sys.argv[1], sys.argv[2]
    out = {"ATP": build(atp, "ATP"), "WTA": build(wta, "WTA")}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f)
    for t in ("ATP", "WTA"):
        a = out[t].get("_avg", {})
        print(f"{t}: {a.get('n_players', 0)} players, avg serve {a.get('serve', 0):.3f} return {a.get('return', 0):.3f}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
