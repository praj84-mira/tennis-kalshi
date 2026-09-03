"""Read-only fair-value monitor. Loops over live US Open singles matches,
joins Kalshi bid/ask to the ESPN score, and logs one CSV row per match per
tick: fair (score-only), gap (fair - mid), and update (serve-point re-rating
the market implies). No order code.

    python monitor.py            # loop every 30s until Ctrl-C
    python monitor.py --once     # single tick, print table
"""
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

import feeds
from tennis_markov import fair_and_update, solve_d, prob_at, serve_probs
from derivatives import current_set_winner
import priors as priors_mod
from hypotheses import hypotheses, verdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOG = os.path.join(DATA, "monitor.csv")
ANCHORS = os.path.join(DATA, "anchors.json")
SERVERS = os.path.join(DATA, "servers.json")

COLS = ["ts", "event_ticker", "ticker_a", "ticker_b", "tour", "best_of", "round", "court",
        "a", "b", "seed_a", "seed_b", "state", "detail", "sets_a", "sets_b", "games_a", "games_b",
        "tb_a", "tb_b", "server", "bid", "ask", "mid", "last", "bid_size", "ask_size", "volume",
        "anchor", "anchor_src", "d_pre", "fair", "gap", "d_live", "update_pts",
        "fair_if_a_serves", "fair_if_b_serves", "score_age_s", "price_move_since_score", "bases", "verdict",
        "set_n", "set_ticker", "set_bid", "set_ask", "set_mid", "set_fair", "set_gap"]


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, obj):
    os.makedirs(DATA, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def anchor_for(anchors, m, a, b, log, bases=None):
    """Pre-match price for player A: last Kalshi trade before ESPN's scheduled
    start; else last candle mid before start; else first live mid (flagged)."""
    key = a["ticker"]
    if key in anchors:
        return anchors[key]
    px, src = None, None
    if m["start_ts"]:
        try:
            px = feeds.kalshi_last_trade_before(a["ticker"], m["start_ts"])
            src = "trade"
            if px is None:
                pb_ = feeds.kalshi_last_trade_before(b["ticker"], m["start_ts"])
                if pb_ is not None:
                    px, src = 1 - pb_, "trade_b"
            if px is None:
                px = feeds.kalshi_last_candle_before(feeds.SERIES[m["tour"]], a["ticker"], m["start_ts"])
                src = "candle"
        except RuntimeError as e:
            log(f"anchor fetch failed {key}: {e}")
    if px is None and a["mid"] is not None:
        px, src = a["mid"], "live_first_seen"
    if px is None:
        return None
    px = min(max(px, 0.02), 0.98)
    d_pre = solve_d(m["tour"], m["best_of"], px, server=None, bases=bases)
    rec = {"price": px, "src": src, "d_pre": d_pre, "ts": time.time(), "bases": bases}
    anchors[key] = rec
    return rec


def infer_server(servers, m):
    """Observed server from ESPN, else parity from a first-server we saw
    earlier in this set, else None. Returns (server, label)."""
    key = m["id"]
    set_idx = sum(m["sets"])
    g = sum(m["games"])
    if m["server"] is not None:
        first = m["server"] if g % 2 == 0 else 1 - m["server"]
        servers[key] = {"set": set_idx, "first": first}
        return m["server"], "AB"[m["server"]]
    rec = servers.get(key)
    if rec and rec["set"] == set_idx and m["tb_pts"] is None:
        s = rec["first"] if g % 2 == 0 else 1 - rec["first"]
        return s, "ab"[s]
    return None, "?"


def score_age(servers, m, mid):
    """Seconds since the ESPN score last changed, and the mid move since then."""
    key = "score:" + str(m["id"])
    sig = f"{m['sets']}|{m['games']}|{m['tb_pts']}"
    rec = servers.get(key)
    now = time.time()
    if not rec or rec["sig"] != sig:
        servers[key] = {"sig": sig, "ts": now, "mid": mid}
        return 0.0, 0.0
    return now - rec["ts"], (mid - rec["mid"]) if (mid is not None and rec.get("mid") is not None) else 0.0


PRIORS = priors_mod.load()


def tick(anchors, servers, log):
    events, setmk = {}, {}
    for tour in ("ATP", "WTA"):
        events.update(feeds.kalshi_open_markets(tour))
        try:
            setmk.update(feeds.kalshi_open_by_ticker(feeds.SET_SERIES[tour]))
        except RuntimeError as e:
            log(f"set markets fetch failed {tour}: {e}")
    matches = feeds.espn_singles()
    joined = feeds.match_kalshi_to_espn(events, matches)
    rows = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for m, a, b in joined:
        if m["state"] != "in":
            continue
        bases = priors_mod.bases_for(PRIORS, m["tour"], m["names"][0], m["names"][1]) if PRIORS else None
        anc = anchor_for(anchors, m, a, b, log, bases)
        server, slabel = infer_server(servers, m)
        age, dpx = score_age(servers, m, a["mid"])
        row = {c: "" for c in COLS}
        row.update({
            "ts": now, "event_ticker": a["event_ticker"], "ticker_a": a["ticker"], "ticker_b": b["ticker"],
            "tour": m["tour"], "best_of": m["best_of"], "round": m["round"] or "", "court": m["court"] or "",
            "a": m["names"][0], "b": m["names"][1], "seed_a": m["seeds"][0] or "", "seed_b": m["seeds"][1] or "",
            "state": m["state"], "detail": m["detail"], "sets_a": m["sets"][0], "sets_b": m["sets"][1],
            "games_a": m["games"][0], "games_b": m["games"][1],
            "tb_a": m["tb_pts"][0] if m["tb_pts"] else "", "tb_b": m["tb_pts"][1] if m["tb_pts"] else "",
            "server": slabel, "bid": a["bid"], "ask": a["ask"], "mid": a["mid"], "last": a["last"],
            "bid_size": a["bid_size"], "ask_size": a["ask_size"], "volume": a["volume"],
        })
        if anc:
            state = {"sets": m["sets"], "games": m["games"], "server": server, "tb_pts": m["tb_pts"]}
            b_ = anc.get("bases")
            fair, d_live, upd = fair_and_update(m["tour"], m["best_of"], anc["d_pre"], a["mid"], bases=b_, **state)
            fa = prob_at(m["tour"], anc["d_pre"], m["best_of"], bases=b_, **dict(state, server=0))
            fb = prob_at(m["tour"], anc["d_pre"], m["best_of"], bases=b_, **dict(state, server=1))
            row.update({"anchor": round(anc["price"], 4), "anchor_src": anc["src"], "d_pre": round(anc["d_pre"], 5),
                        "fair": round(fair, 4), "gap": round(fair - a["mid"], 4) if a["mid"] is not None else "",
                        "d_live": round(d_live, 5) if d_live is not None else "",
                        "update_pts": round(upd, 2) if upd is not None else "",
                        "fair_if_a_serves": round(fa, 4), "fair_if_b_serves": round(fb, 4),
                        "score_age_s": int(age), "price_move_since_score": round(dpx, 4),
                        "bases": f"{b_[0]:.3f}/{b_[1]:.3f}" if b_ else ""})
            # current-set winner market for A, priced off the same chain
            set_n = m["sets"][0] + m["sets"][1] + 1
            code, suffix = a["event_ticker"].split("-")[1], a["ticker"].split("-")[-1]
            sm = setmk.get(f"{feeds.SET_SERIES[m['tour']]}-{code}-{set_n}-{suffix}")
            pa_, pb_ = serve_probs(m["tour"], anc["d_pre"], b_)
            set_fair = current_set_winner(pa_, pb_, m["best_of"], m["sets"], m["games"], server, tb_pts=m["tb_pts"])
            row.update({"set_n": set_n, "set_fair": round(set_fair, 4)})
            if sm:
                row.update({"set_ticker": sm["ticker"], "set_bid": sm["bid"], "set_ask": sm["ask"], "set_mid": sm["mid"],
                            "set_gap": round(set_fair - sm["mid"], 4) if sm["mid"] is not None else ""})
        hyps = hypotheses(row)
        row["verdict"] = verdict(hyps)
        row["hypotheses"] = hyps
        rows.append(row)
    unmatched = [ev for ev in events if ev not in {a["event_ticker"] for _, a, _ in joined}]
    return rows, len(matches), unmatched


def rotate_if_stale(path):
    """If the CSV on disk has a different header than COLS, move it aside so
    the new schema gets a fresh file. Returns True if a header must be written."""
    if not os.path.exists(path):
        return True
    with open(path) as f:
        hdr = f.readline().strip().split(",")
    if hdr == COLS:
        return False
    os.replace(path, path.replace(".csv", f".{int(time.time())}.csv"))
    return True


def fmt(rows):
    hdr = f"{'match':<38} {'score':<22} {'sv':<2} {'bid':>5} {'ask':>5} {'anch':>5} {'fair':>5} {'gap':>6} {'upd':>6} {'vol':>6}  verdict"
    out = [hdr, "-" * len(hdr)]
    for r in sorted(rows, key=lambda r: -abs(float(r["gap"]) if r["gap"] != "" else 0)):
        score = f"{r['sets_a']}-{r['sets_b']} {r['games_a']}-{r['games_b']}" + (f" ({r['tb_a']}-{r['tb_b']})" if r["tb_a"] != "" else "")
        nm = f"{r['a'][:17]} v {r['b'][:17]}"
        f_ = lambda v, w=5, p=2: (f"{float(v):>{w}.{p}f}" if v not in ("", None) else " " * w)
        out.append(f"{nm:<38} {score:<22} {r['server']:<2} {f_(r['bid'])} {f_(r['ask'])} {f_(r['anchor'])} {f_(r['fair'])} {f_(r['gap'], 6, 3)} {f_(r['update_pts'], 6, 1)} {f_(r['volume'], 6, 0)}  {r['verdict']}")
        for sev, text in r.get("hypotheses", []):
            out.append(f"    [{sev}] {text}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=30)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    log = (lambda *a: None) if args.quiet else (lambda *a: print(*a, file=sys.stderr))
    anchors, servers = load(ANCHORS, {}), load(SERVERS, {})
    os.makedirs(DATA, exist_ok=True)
    new = rotate_if_stale(LOG)
    while True:
        try:
            rows, n_espn, unmatched = tick(anchors, servers, log)
            with open(LOG, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
                if new:
                    w.writeheader()
                    new = False
                w.writerows(rows)
            save(ANCHORS, anchors)
            save(SERVERS, servers)
            print(f"\n{rows[0]['ts'] if rows else datetime.now(timezone.utc).isoformat()}  live={len(rows)}  espn_singles={n_espn}  kalshi_events_unmatched={len(unmatched)}")
            print(fmt(rows))
        except Exception as e:  # noqa: BLE001
            log(f"tick error: {e!r}")
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
