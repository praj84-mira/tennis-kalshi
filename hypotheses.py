"""Turn a monitor row into a ranked list of checkable hypotheses for WHY the
model and the market disagree. Every line is derived from data in the row;
none of it is a prediction. The point is to make the next action obvious:
look closer, spot-check, or walk away.
"""

GAP = 0.05          # |fair - mid| worth attention
UPD = 1.5           # serve-pts re-rating that counts as "the market changed its mind"
WIDE = 0.04         # spread that makes mid noise
STALE_S = 240       # score unchanged this long while price moved = suspect the feed


def _f(x):
    try:
        return None if x in ("", None) else float(x)
    except (TypeError, ValueError):
        return None


def hypotheses(r):
    """r: monitor row dict (strings ok). Returns [(severity, text)], severity in
    'act' | 'look' | 'walk'."""
    out = []
    fair, mid, gap, upd = _f(r.get("fair")), _f(r.get("mid")), _f(r.get("gap")), _f(r.get("update_pts"))
    bid, ask = _f(r.get("bid")), _f(r.get("ask"))
    anchor = _f(r.get("anchor"))
    fa, fb = _f(r.get("fair_if_a_serves")), _f(r.get("fair_if_b_serves"))
    age = _f(r.get("score_age_s"))
    dpx = _f(r.get("price_move_since_score"))
    sets_a, sets_b = int(r.get("sets_a") or 0), int(r.get("sets_b") or 0)
    best_of = int(r.get("best_of") or 3)
    if fair is None or mid is None:
        return [("walk", "No anchor or no two-sided quote; nothing to compare.")]
    spread = (ask - bid) if (ask is not None and bid is not None) else None

    # 1. is the gap even real?
    if spread is not None and spread >= WIDE:
        out.append(("walk", f"Spread is {spread * 100:.0f}c wide. The mid is noise; a 'gap' inside the spread is not tradeable as a taker. Maker-side only, if at all."))
    if age is not None and dpx is not None and age >= STALE_S and abs(dpx) >= 0.05:
        out.append(("walk", f"ESPN score unchanged for {age / 60:.0f} min while the price moved {dpx * 100:+.0f}c. The score is probably stale; the gap is probably fake. Check the broadcast score before believing the model."))
    if r.get("server") == "?" and fa is not None and fb is not None and abs(fa - fb) >= 0.03:
        out.append(("look", f"Server unknown. Fair is {fa:.2f} if A serves next, {fb:.2f} if B does; the gap may be entirely that. Find out who's serving."))
    games_a, games_b = int(r.get("games_a") or 0), int(r.get("games_b") or 0)
    if games_a == 6 and games_b == 6 and r.get("tb_a") in ("", None):
        out.append(("look", "In a tiebreak and ESPN does not show the tiebreak points. Each point here is worth 5-10 match-pts; the gap may be entirely the tiebreak score. Spot-check with --tb before believing it."))
    if 0.45 <= mid <= 0.55:
        out.append(("walk", "Mid is in the 45-55c band: max taker fee, coin-flip variance. Standing rule: no taker entries here."))

    # 2. what kind of disagreement is it?
    if gap is not None and abs(gap) >= GAP:
        if upd is not None and abs(upd) < UPD:
            side = "A cheap" if gap > 0 else "A rich"
            out.append(("act", f"Score-mechanics disagreement ({side} by {abs(gap) * 100:.0f} pts): market and model agree on the players (serve re-rated only {upd:+.1f} pts) but price this score differently. This is the model's home turf. Spot-check the point score first: ESPN gives none, and a break point moves fair 5-8 pts."))
        elif upd is not None:
            who = "A" if upd < 0 else "B"
            out.append(("look", f"The market has re-rated {'A' if upd < 0 else 'A up, i.e. B'} by {abs(upd):.1f} serve-pts since the open. Something not in the score: injury, medical timeout, conditions, visible form. The model has no opinion on that. Unless you are watching and disagree, the market is probably right."))
    elif gap is not None:
        out.append(("walk", f"Gap is {gap * 100:+.1f} pts, inside noise. Priced."))

    # 2b. the derivative: does the set-winner market agree with the chain?
    sg, sb, sa = _f(r.get("set_gap")), _f(r.get("set_bid")), _f(r.get("set_ask"))
    if sg is not None and sb is not None and sa is not None:
        sspread = sa - sb
        if abs(sg) >= 0.06 and sspread <= 0.06 and (gap is None or abs(gap) < GAP):
            out.append(("act", f"Set {r.get('set_n')} winner market is {abs(sg) * 100:.0f} pts {'below' if sg > 0 else 'above'} what the chain implies from the match price (set fair {_f(r.get('set_fair')):.2f} vs {sb:.2f}/{sa:.2f}), while the match price itself agrees with the chain. Derivative mispricing candidate: the thinner market is the one that is off."))
        elif abs(sg) >= 0.06 and sspread > 0.06:
            out.append(("walk", f"Set {r.get('set_n')} market looks off by {abs(sg) * 100:.0f} pts but the spread is {sspread * 100:.0f}c. Not tradeable as a taker."))

    # 3. patterns worth naming
    if anchor is not None and best_of == 5 and anchor >= 0.70 and sets_a < sets_b:
        out.append(("look", "Best-of-five favorite down a set: the reload pattern. Check the backtest report's 'reload' rows for what buying here has actually returned after fees before treating it as edge."))
    if anchor is not None and best_of == 5 and anchor <= 0.30 and sets_a > sets_b:
        out.append(("look", "Best-of-five underdog up a set: the market usually still favors the favorite here, and the backtest calibration table says whether that is right."))
    if mid <= 0.12 or mid >= 0.88:
        out.append(("look", "Extreme price. Longshot side is the documented losing side of this market (favorite-longshot bias); favorite side pays ~0.6c fee but needs many contracts to matter."))
    if not out:
        out.append(("walk", "Nothing to act on."))
    order = {"act": 0, "look": 1, "walk": 2}
    out.sort(key=lambda x: order[x[0]])
    return out


def verdict(hyps):
    """act only when an 'act' case stands and nothing blocks it (wide spread,
    stale score, fee zone, untradeable set market); walk if the row is priced
    or blocked; look otherwise."""
    blockers = [t for s, t in hyps if s == "walk" and "inside noise" not in t and "Nothing to act on" not in t and "No anchor" not in t]
    if any(s == "act" for s, _ in hyps) and not blockers:
        return "act"
    if blockers:
        return "walk"
    if any(s == "look" for s, _ in hyps):
        return "look"
    return "walk"
