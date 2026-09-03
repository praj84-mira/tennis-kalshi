# US Open / Kalshi: project brief

*Written 2 Sept 2026, mid-tournament (round of 64 in progress). Companion to the `usopen-fairvalue` package.*

---

## 1. What we're trying to do

Test whether there is a repeatable, quantifiable edge in trading live US Open singles markets on Kalshi — and whether that edge is large enough to justify building a trading agent around it.

Secondary objective, arguably the real one: hands-on reps in agentic systems and market microstructure at trivial stakes. Budget is "not tens of thousands." Treat the money as tuition; optimise the build for information, not P&L.

## 2. The original hypotheses

Two strategies Prithvi described, both from lived wins:

**H1 — Underpriced favorites.** When a clear favorite's payout looks too generous (1.3–1.5×), buy the favorite.

**H2 — Underdogs at extreme moments.** When a match is in a high-variance state and the underdog is priced very low, buy the underdog. Two cited wins: against Djokovic after a saved break point in a third set; an unranked player at 5-8 down in a final-set tiebreak, priced at 10%, that paid.

**H3 — Thin early-round markets.** Inefficiency lives in low-volume early-round matches where a few bets swing the price.

## 3. What the analysis found

### H2 is the documented losing side of the market

The single most robust finding in prediction-market research is favorite-longshot bias. On Kalshi specifically:

- A 300,000+ contract study (Whelan et al.) found cheap contracts win *less* often than their price implies, expensive contracts slightly *more*. Buyers of low-priced contracts have highly negative returns; buyers of high-priced contracts get small positive returns.
- A 72-million-trade analysis found longshot contracts returning as low as 43¢ on the dollar — worse than a Vegas slot machine.

**The 5-8 tiebreak was not mispriced.** A first-to-10 tiebreak from 5-8 down requires 5 points before the opponent takes 2; that's decided within 6 points. Under coin-flip points: (1+6)/64 = **10.9%**. With realistic serve rotation, 8–12% depending on who served first. Market said 10. That was a fairly priced 9:1 shot that landed — variance, not edge.

**Conclusion:** H2 contradicts H1. H1 is on the side the research supports. H2 is the side that funds the exchange. Two winning trades on H2 are not evidence.

### H3 is right about *where*, wrong about *which side*

Thin early-round markets are where inefficiency lives. But the research shows a persistent wealth transfer **from takers to makers** on Kalshi, driven by asymmetric retail order flow. Maker fees are zero on most markets; taker fees peak at 1.75% at 50¢. The way to harvest thin-market panic is to *provide* liquidity with resting limit orders, not to *consume* it by chasing momentum.

### Latency is the structural killer for any in-play taker strategy

Live tennis markets price off courtside point-by-point feeds (1–3 s). Kalshi has a Catalist Sports data deal covering 65k+ matches. A broadcast is 5–10 s behind on cable, 20–45 s on streaming. Every "he's about to break" read is a trade against someone who already knows how the point ended. This is not a skill gap; it can't be closed by knowing tennis better.

### Fees are worst exactly where H2 lives

Taker fee = ceil(0.07 × contracts × P × (1−P)) cents. Peaks at 50¢: 1.75¢/contract. A taker round-trip at mid prices costs ~3.5¢ on a $1 contract — ~7% of capital risked — requiring a 3.5-point probability edge per trade just to break even. Favorites near 90¢ pay ~0.6¢. Longshots near 10¢ pay ~0.6¢ too, but that's 6% of the stake.

Open question: whether US Open markets are "designated" events carrying the 0.0175 maker multiplier. Check the fee schedule before assuming maker orders are free.

### Kalshi's US Open position, for context

Kalshi is now the exclusive prediction-market partner of the US Open (multi-year, from the 2026 main draw), with venue and ESPN broadcast presence and tennis volume up 25× YoY. Retail flow is flooding in. That is the best argument that *some* edge exists — and it argues for making markets, not taking them.

## 4. The four live boards we looked at

| Board | State | Market | What the math said |
|---|---|---|---|
| Faria v Alcaraz | Alcaraz down a set, 0-0 | 74% | Pre-match was 92% (not mid-90s as read off the chart). Score-only fair value **78%**. Gap <4 pts. Market re-rated his serve by <0.5 pts. Directionally right side, but small edge, deepest book on the app. |
| Li v Vekic | 3-3 in decider, Vekic serving | 65% | Evenly matched server at 3-3 ≈ 54–56%. Extra ~10 pts = market's revision of Li after she lost momentum. No structural asymmetry in a best-of-three decider. Max-fee zone. Pass. |
| Faria v Alcaraz | Alcaraz serving 30-40, set 2 | 67% | Break point mid-flight. Fair ≈ 68% by weighting hold/break outcomes. Priced. Buying it is buying one point, blind, ten seconds late. |
| Berrettini v Navone | 1-2 sets, 2-3 games | 10¢ → 20¢ in 2 min | Price doubled while the ESPN score didn't change. Feed lag made visible. |

Pattern: four boards in eleven minutes, each framed as "the price feels wrong," each priced when the arithmetic was done. That's the failure mode this whole project exists to prevent.

## 5. Strategies ranked by how much to believe them

1. **Passive liquidity provision in thin markets.** Matches the evidence. Zero maker fee. Adverse selection by fast players is the cost.
2. **Best-of-five favorite reload.** A seeded player who drops a set to a qualifier retains recovery equity retail may underweight. Men's draw only. Empirically testable — this is what the monitor measures.
3. **Kalshi vs. sharper books divergence.** If sponsorship retail skews prices toward popular/seeded/American players, it's measurable.
4. **Retirement/heat risk** in best-of-five day sessions. Undermodelled but you still lose the latency race to act on it.

Dropped: reading momentum off the broadcast. Point-based models already know the score state exactly; the eye adds nothing and arrives late.

## 6. What was built

A read-only fair-value monitor. No order code exists in the package, by design.

**Engine** (`tennis_markov.py`): nested Markov chains, point → game → set → match, exact recursion. US Open rules: 7-point tiebreak at 6-6, 10-point in the decider, next-set first-server rule. Verified: 5-8 tiebreak = 10.94%; deuce closed form p²/(p²+q²) matches.

**Calibration**: strength differential fit to **Kalshi's own pre-match price** (last trade before ESPN's scheduled start) and held fixed. Isolates the question *does the market over-update on in-match evidence?* from *is the opening line right?*

**Two outputs per row:**
- `fair` — what the pre-match price would be now if only the score had changed. `gap = fair − mid`.
- `update` — inversion: solve for the strength differential the live price implies at this score; report how many serve-points the market has re-rated player A. Converts "the odds feel weird" into "the market thinks Alcaraz holds at 68% instead of 72%" — a claim that can be checked.

**Read**: large gap + small update = disagreement about score mechanics, worth a look. Large gap + large update = the market has decided someone is playing differently than expected; the model has no opinion on that.

**Feeds**: Kalshi public API (bid/ask, candlestick history) + ESPN scoreboard (sets, games, server). Both free and unauthenticated.

**Files**: `tennis_markov.py`, `feeds.py`, `monitor.py` (loop + CSV log), `fair.py` (manual point-level spot check), `settle.py` (join outcomes, Brier-score model vs market, naive after-fee P&L upper bound), `README.md`.

## 7. Known limitations of the build

- ESPN gives no point score within a game; fair value is computed at 0-0. At a break point the true number can differ by 5–8 pts. Use `fair.py` by hand for those.
- ESPN's game-level score lags by minutes on some courts. Stale score vs. live price = fake gap.
- ESPN drops the server between games; inferred by parity (lowercase in the log). Wrong inside tiebreaks.
- Points modelled as i.i.d. No fatigue, injury, wind, momentum.
- Base serve % is a tour constant (ATP 0.64, WTA 0.57); only the differential is fit.
- Historical stats repo used for serve priors was unavailable; pre-match-price anchoring was chosen instead. Serve-stat priors can be added as an alternative anchor later.

The Brier test absorbs all of this honestly: rows built on stale scores will score badly and drag the model down, which is the correct answer if that's what's happening.

## 8. Decision criteria

**Run**: `python monitor.py` through the round of 32. Then `python settle.py --min-gap 0.05`.

**Kill**: if the model's Brier score on flagged rows is not lower than the market's, the edge from score mechanics alone is zero. Stop. Do not build an agent. This is the expected outcome and it is a real answer obtained for free.

**Continue**: if the model's Brier is lower, size the effect (per-trade after-fee expectancy × plausible fill rate × realistic capital), then decide whether it clears the attention cost. Only then discuss automation — and the automated version should be a *maker*, resting orders at model-derived prices, not a taker chasing gaps.

**Standing rules while any of this is live:**
- No taker entries between 45¢ and 55¢. Keeps you out of the max-fee, coin-flip zone.
- Log every discretionary trade before the match resolves: entry, model fair value, reasoning. Ten of those is a sample. Zero is a story about the two that won.
- Latency test still not done: stopwatch a point ending on screen vs. the Kalshi price moving. One match. That number decides whether in-play *taking* is ever on the table.

## 9. Council check

**Decision:** Build an agent to trade live US Open markets.
**Likely bottleneck:** Latency and side-of-trade, not strategy.
**Open prerequisite:** A fair-value model (now exists) and a Brier test against the market (pending). Worthless until the test runs.
**Ignored advisor:** Operator of Reality. An agent on delayed data loses at machine speed, unattended.
**Biggest failure mode:** Automating a strategy validated by two winning trades.
**Recommendation:** Read-only through round of 32. Decide on the Brier result, not on how the next board feels.
**Next action:** Start `monitor.py` on a machine that stays awake tonight.
