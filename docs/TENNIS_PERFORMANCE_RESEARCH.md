# What wins tennis matches: a quantitative view

*Research brief, 2 Sept 2026. Companion to `PROJECT_BRIEF.md` and the `usopen-fairvalue` engine. Tags: [Known] = established in the literature or directly measurable; [Likely] = well-supported but with caveats; [Hypothesis] = my inference, not yet tested.*

---

## 0. The answer in ten lines

1. Tennis is won at the point level, and the margin is tiny. Winning 52% of points instead of 50% roughly doubles your odds of winning the match. Everything else is a story about where those two points come from.
2. Two numbers carry almost all the signal: **serve points won %** and **return points won %**. Their ratio — the **dominance ratio** — is the single best in-match summary of who is actually better.
3. **First-serve percentage is weak.** First-serve *points won* and, above all, **second-serve points won** are where players separate.
4. **Break-point conversion is mostly noise.** It regresses to the serve/return rates that produce it.
5. Seventy percent of points end within four shots. The serve, the return, and each player's next shot decide most matches. Long-rally consistency is over-weighted by fans and under-weighted by nothing.
6. Points are *almost* independent. Momentum and pressure effects exist, are small, and are larger for weaker players.
7. For pre-match prediction, a **surface-weighted Elo** is the best single number ever tested. Bookmakers still edge it. Head-to-head is nearly worthless.
8. Injuries show up first in **serve speed, second-serve quality, and return points won** — not in the scoreline. The literature handles them crudely (a retirement flag on the next match). There is room to do better.
9. A "moneyball" model for a given player is: (a) their serve and return ratings, opponent-adjusted; (b) their sensitivity — how many serve-points of edge flips their typical match; (c) the specific lever — hold rate, second-serve return, first-four-shot win rate — that moves that number.
10. The system is a stack: data → player ratings → matchup serve probabilities → the Markov engine we built → state adjustments → calibration against the market → per-player counterfactuals.

---

## 1. What actually drives wins and losses

### 1.1 The causal chain

Tennis's scoring system is a multiplier. A small edge at the point level compounds through game, set, and match. This is why point-based Markov models work and why the inputs matter so much.

**[Known]** Klaassen & Magnus showed that the probability of winning a match is a steep function of the *difference* between the two players' probabilities of winning a point on serve. On a fast surface, a two-point difference in serve-point win rate (say 66% vs 64%) is roughly a 60/40 match. Our engine reproduces this: a strength differential of 0.045 serve-points corresponds to a 92% pre-match favorite.

So the question "what drives wins" reduces to "what drives serve points won and return points won."

### 1.2 The hierarchy of statistics

Ranked by predictive value, with what the evidence says about each.

**Tier 1 — the primitives**

| Stat | Verdict | Why |
|---|---|---|
| **Serve points won % (SPW)** | [Known] Core input | The single most important number. Everything on the serve side aggregates here. |
| **Return points won % (RPW)** | [Known] Core input | The single most important number on the other side. Return is where matches are decided at the elite level because everyone holds. |
| **Dominance ratio (DR = RPW / (1 − SPW))** | [Known] Best in-match summary | Invented by Carl Bialik, popularised by Jeff Sackmann. Equals 1.0 when you're as good on return as your opponent is on serve. Winners are almost always above 1.0; a winner below 0.9 is a clutch-or-luck story. Note DR compares *your* return to *your opponent's* return, so it's opponent-adjusted by construction. |

**Tier 2 — the decompositions that carry real signal**

| Stat | Verdict | Why |
|---|---|---|
| **Second-serve points won (server)** | [Known] Highly discriminating | The gap between first- and second-serve effectiveness is the largest single skill gap in tennis. Djokovic's career split is roughly 76.5% on first serve vs 53.4% on second — without his first serve he's barely better than opponents. Second-serve points won tracks ranking more tightly than any other single serve stat. |
| **Second-serve return points won** | [Known] Highly discriminating | The mirror. Elite returners win 55%+ of second-serve return points. This is the stat that lets a player like Djokovic or Medvedev break big servers. |
| **First-serve points won** | [Known] Strong, surface-dependent | ~69% on clay, ~75% on grass and hard at the 2021 Slam quarterfinals-onward. Reflects serve quality *and* serve+1. |
| **First-serve % (in)** | [Likely] Weak alone | Players trade first-serve % against first-serve effectiveness. A 55% first serve at 80% won beats a 70% first serve at 68% won. First-serve % matters mainly as a *change* signal (fatigue, injury, nerves) rather than as a level. |
| **Ace %, double-fault %** | [Likely] Moderate, partly skill | Components of SPW. Ace rate is a stable player trait; DF rate is noisier and spikes under physical or mental stress. Useful as *diagnostics* more than as predictors. |

**Tier 3 — the tactical layer (shot-level data)**

| Stat | Verdict | Why |
|---|---|---|
| **Rally-length distribution** | [Known] 70 / 20 / 10 | O'Shannessy's finding from IBM rally-length data: ~70% of points end in 0–4 shots, ~20% in 5–8, ~10% in 9+. The most common rally length is one shot (serve unreturned or return error). Confirmed at 65–77% short rallies in Grand Slam late rounds. |
| **First-four-shots win rate** | [Likely] The real tactical lever | Serve, return, serve+1, return+1. Roughly 80% of points with a first serve *and* a short rally are won by the server. With first serve and a medium rally, it's ~50/50. The server's edge evaporates once the rally goes past shot four. |
| **Serve direction / return impact position** | [Likely] Matchup-specific | ATP tracking data (2018+) records return impact location. Players have exploitable tendencies: some returners struggle from open stances, some servers are more effective wide vs T. This is where per-player scouting lives. |
| **Serve speed and variability** | [Likely] Skill and health proxy | A 2026 arXiv paper builds a Server Quality Score from speed, speed variance, and placement with crossed server/returner random effects — the right structure for separating serve skill from opponent quality. Also the earliest injury indicator. |

**Tier 4 — the "clutch" stats, mostly noise**

| Stat | Verdict | Why |
|---|---|---|
| **Break points converted / saved** | [Known] Mostly regression to SPW/RPW | Tennis Abstract has documented this repeatedly: BP conversion is far less stable season-to-season than SPW/RPW. A player "converting poorly" is usually a player facing good servers. Sackmann's DR+ (dominance ratio × break-point leverage ratio) exists precisely to reconcile the cases where DR > 1 and the player still lost. |
| **Pressure-point performance** | [Known] Real but small | Klaassen & Magnus, ~90,000 Wimbledon points: at important points it is harder for the server to win, and winning the previous point has a small positive effect on the current one. Both effects are larger for weaker players. Deviations from i.i.d. are small enough that the i.i.d. model remains a good approximation. |
| **Tiebreak record** | [Likely] Noise | Small samples, dominated by serve. Tiebreak SPW is the stat, not tiebreak W-L. |
| **Head-to-head** | [Known] Nearly worthless | Kovalchik and others find it adds almost nothing once ratings are included. It's a small-sample artifact of two ratings and their surface interaction. Nalbandian's record against Federer is the canonical fluke. |

### 1.3 What does not predict (or predicts less than people think)

- **Ranking points** lag ability by months (52-week rolling, tournament-weighted). Elo responds in weeks.
- **Win/loss record** ignores opponent quality and margin. Point-level stats beat it.
- **"Form" measured as last five results** — same problem. Form measured as recent SPW/RPW residual vs. baseline is real; form as W-L is noise.
- **Momentum within a match** — exists, small, and already in the price of any market run by a point-based model.

---

## 2. How this varies by player

The primitives are the same for everyone; the *composition* differs, and composition determines matchups.

### 2.1 Archetypes (illustrative, not exhaustive)

| Archetype | Profile | Where they win | Where they lose |
|---|---|---|---|
| **Serve-dominant** (Isner, Opelka, Shelton) | Very high SPW, high ace rate, below-average RPW | Tiebreaks, fast surfaces, matches that stay on serve | Any match where they get broken once; clay; against elite second-serve returners |
| **Return-dominant** (Djokovic, Medvedev, Alcaraz on his day) | Above-average SPW, elite RPW, especially 2nd-serve return | Grinding down servers, deciding sets | Rarely; the profile is robust across surfaces |
| **First-strike** (Fritz, Berrettini, Sinner) | High SPW driven by serve+1, average RPW | Fast courts, short rallies | Long rallies, slow conditions, when first-serve % drops |
| **Grinders** (Ruud, Alcaraz's defensive mode, many WTA players) | Average SPW, above-average RPW from rally consistency | Clay, extended rallies, physical attrition | Fast surfaces against big servers |

**[Hypothesis]** The Markov engine's single-differential calibration is too coarse for matchup work. Serve-dominant vs. return-dominant is not symmetric: the same match-win probability can hide very different set-score distributions and very different sensitivity to a single break. This is testable by fitting two parameters (SPW, RPW per player) instead of one differential and checking whether set-score predictions improve.

### 2.2 Surface interaction

- **[Known]** Surface changes the base serve advantage: first-serve effectiveness ~69% clay vs ~75% hard/grass; second-serve effectiveness ~55% on all surfaces. So surface primarily moves *first-serve* leverage.
- **[Known]** Kovalchik and FiveThirtyEight found surface-weighted Elo outperforms unweighted. Sackmann's "sElo" blends overall and surface-specific ratings.
- **[Likely]** Surface *also* changes rally-length distribution (more 5+ shot rallies on clay), which shifts value from serve-dominant toward grinder profiles.

### 2.3 Men vs. women

- **[Known]** The serve advantage is smaller in WTA (roughly 57% base SPW vs 64% ATP in our engine's constants). Consequences: more breaks, more volatile sets, lower per-game hold rates, and momentum/pressure effects that are proportionally larger. Klaassen & Magnus note women's sets are more lopsided (6-0, 6-1 more common) because the serve advantage is smaller and quality differences show up faster.
- **[Likely]** WTA return stats carry relatively more predictive weight than ATP return stats, because more points are decided on return.

### 2.4 Rank tiers

- **[Known]** Kovalchik: all models were 10–20 percentage points less accurate for lower-ranked players than for the top. The FiveThirtyEight Elo hit 75% on top-player matches (competitive with bookmakers) but only 59–64% lower down.
- Implication: early-round Grand Slam matches between qualifiers are where *everyone's* model is worst — including the market's. That's consistent with the thin-market thesis, but it also means our model is equally blind there.

---

## 3. Accounting for injuries

This is the least-solved problem in tennis analytics and probably the largest source of exploitable disagreement with a market, because injury information is soft, sparse, and slow to propagate into ratings.

### 3.1 Where injuries show up first (the physiological chain)

**[Likely]** In roughly this order:

1. **Serve speed** drops (shoulder, back, abdominal, leg drive). The Server Quality Score literature treats speed and speed variability as primary skill features — they are also the primary health features.
2. **First-serve % drops or second-serve gets shorter.** A player protecting a body part serves safer. Watch for a *simultaneous* drop in first-serve % and rise in DF rate — that combination is rarely tactical.
3. **Return points won drops** (movement injuries: ankle, knee, hip, hamstring). Return is movement-intensive. A player with a lower-body problem holds serve normally for a set and gets broken because they can't push off on return.
4. **Rally-length distribution shifts** — the injured player shortens points (goes for more) or lengthens them (can't finish). Either direction from baseline is a signal.
5. **Set-score pattern** — winning the first set and collapsing is the classic signature of a player who started on adrenaline and painkillers.

### 3.2 How the literature handles it (crudely)

- **[Known]** Most Elo implementations, including Sackmann's, *exclude* retirements and walkovers from rating updates entirely. This avoids penalising an injured player's rating but also throws away information.
- **[Known]** Sipko & Knottenbelt (2015) tried "time since retirement" as an injury-severity proxy and abandoned it — longer layoff means both more serious injury and more recovery. They settled on a binary "retired in previous match" flag, and found the effect is only significant for the *immediately following* match.
- **[Likely]** Their neural-net model with 22 features (including fatigue and injury proxies) reported a 4.35% ROI against the betting market. Treat that number with suspicion — single-season, likely overfit, and 2015 markets were softer — but the *direction* (injury features add value) is credible.

### 3.3 What a better approach looks like

**[Hypothesis]** — the design I'd build:

1. **Player baselines** for serve speed (avg, max, std), first-serve %, DF %, SPW, RPW, rally-length share — computed on a rolling 26-week window, surface-adjusted.
2. **Residual monitoring**: for each match, compute z-scores of each stat vs. baseline. An injury is a *correlated* negative residual across serve speed, first-serve %, and RPW. Any one of them alone is noise; three together is a flag.
3. **A latent "physical state" variable** in the ratings model that decays back to 1.0 over ~3 weeks, is shocked downward by retirements, medical timeouts, and correlated negative residuals, and widens the *variance* of the player's rating (not just the mean). The point is not that an injured player is worse by X; it's that you know less about how good they are.
4. **Return-from-layoff shrinkage**: after a gap of 8+ weeks, blend the player's rating toward the tour mean for their rank tier, and raise variance. Kovalchik's "career-to-date" adjustment helped lower-ranked players; the same idea applies to returning players.
5. **In-match**: track serve speed and first-serve % *within* the match against the player's own baseline. A 10 km/h drop in first-serve speed mid-match is the most honest injury signal there is and it's visible before the scoreline moves.

Data reality: serve speed is available from tournament tracking (Slams, Masters) and ATP's published tracking summaries since 2018. It is not in the free ESPN feed. Getting it live is the gate.

---

## 4. The "moneyball" model, per player

Moneyball wasn't a model; it was a *reframing* — finding the stat the market underpriced (on-base %) and buying it. The tennis version:

### 4.1 What the market probably prices well

- Overall strength (Elo-equivalent). Bookmakers beat every published model on this.
- Surface.
- Live score state (they run the same Markov chain we do, with better inputs and faster data).

### 4.2 Where the market probably has less information

**[Hypothesis]** — in rough order of promise:

1. **Injury and physical state**, for the reasons in §3. Ratings adjust slowly; retail flow doesn't adjust at all.
2. **Matchup-specific serve/return interactions.** Elo is one number; it can't see that Player A's second serve is exactly what Player B's return feasts on. Barnett–Clarke's opponent-adjusted serve probability is the standard fix and Kovalchik found it the best of the point-based methods. Common-opponent models (Knottenbelt) go further but starve on data.
3. **Set-score and duration distributions.** Even if the market's match price is right, its implied *set* distribution may not be — and set-winner and total-sets markets exist on Kalshi. A serve-dominant favorite has a very different set profile from a return-dominant one at the same match price.
4. **Best-of-five recovery equity** — the structural asymmetry we've already discussed.

### 4.3 The per-player "what must be true to win"

For any player against any opponent, the model produces three numbers:

- **Break-even serve edge.** Solve for the (SPW, RPW) pair at which P(win) = 50%. Express as: "You need to hold at X% and win Y% of return points."
- **Sensitivity.** ∂P(win)/∂SPW and ∂P(win)/∂RPW. Serve-dominant players are sensitive to RPW (they can't afford a single break); return-dominant players are sensitive to SPW (their edge assumes they hold).
- **The lever.** Translate the sensitivity into the first-four-shots layer: which of serve, return, serve+1, return+1 has the highest leverage *for this player against this opponent*. That's the scouting output.

This is what a coach's "game plan" is, made quantitative. It's also the counterfactual that tells you whether a live price is reasonable: if Alcaraz at 67% implies he's holding at 72% and his baseline is 88%, either something is physically wrong or the market is wrong. Those are the only two options and both are worth knowing.

---

## 5. Building it into a system

### 5.1 The stack

```
Layer 0  DATA
         Match-level: SPW, RPW, 1st%, 1stW, 2ndW, aces, DFs, BP — Sackmann's tennis_atp/tennis_wta
                      (CSV; currently unavailable at the old GitHub path — locate the mirror)
         Point-level: Match Charting Project (Sackmann, volunteer-charted, shot-level)
         Tracking:    ATP/Slam serve speed, return impact (Infosys / IBM / Hawkeye published summaries)
         Market:      Kalshi API (have), Betfair/Pinnacle closing lines for calibration
         Live score:  ESPN (have, laggy), or a paid feed if in-play ever becomes real

Layer 1  PLAYER RATINGS
         Surface-weighted Elo (Kovalchik/538 K-factor schedule) — the baseline everything is judged against
         Serve rating + return rating, opponent-adjusted (Barnett–Clarke), surface-adjusted, recency-weighted
         Physical-state variable (§3.3) with decay and variance inflation

Layer 2  MATCHUP
         Two serve-point probabilities for the specific pair: p_A = f_A + (g_avg − g_B), p_B = f_B + (g_avg − g_A)
         where f = serve rating, g = return rating, avg = surface field mean.
         Shrink toward Elo-implied differential when serve/return samples are thin.

Layer 3  ENGINE  (built)
         Point → game → set → match Markov chain. Exact. US Open rules.
         Extend: set-score distribution, expected duration, total-games.

Layer 4  STATE ADJUSTMENTS  (small; only if Layer 5 says they help)
         Pressure-point penalty on server at high-leverage points (Klaassen–Magnus)
         Fatigue: minutes on court prior 48h, five-setters in last 7 days
         Within-match residuals: serve speed vs baseline (if tracking data available)

Layer 5  CALIBRATION
         Brier score vs. market, vs. surface-Elo, on held-out matches.
         Per-tier: top-30 vs. rest. Per-surface. Per-gender.
         If Layer 2 doesn't beat Elo, drop it. If Layer 4 doesn't beat Layer 3, drop it.

Layer 6  OUTPUT
         Pre-match: P(win), set distribution, per-player break-even and levers
         In-match: fair value at any score; implied ability update vs. pre-match; injury flag
         Divergence log vs. Kalshi, with fee-adjusted expectancy
```

### 5.2 Build sequence and kill gates

| Phase | Build | Gate to proceed |
|---|---|---|
| 1 (done) | Markov engine + Kalshi/ESPN monitor, anchored to pre-match price | Brier on flagged rows ≤ market's → stop; else continue |
| 2 | Surface-Elo + serve/return ratings from historical match stats (3 seasons) | Elo alone must reproduce ~70% accuracy on top-tier matches out of sample. Serve/return ratings must beat Elo on Brier or they're dropped. |
| 3 | Opponent-adjusted matchup probabilities feeding the engine; set-score distribution output | Set-score Brier vs. Kalshi set-winner / total-sets markets. This is where a real edge would first appear, because it's a thinner market. |
| 4 | Physical-state variable from residual monitoring; retirement/MTO flags | Does the flag predict *subsequent* under-performance vs. Elo? If not, it's noise. |
| 5 | Serve-speed ingestion (Slam tracking summaries, post-match at first) | Only if Phase 4 shows physical state matters. |
| Never | Live in-play taking off a broadcast or ESPN | Latency. Settled. |

### 5.3 What to expect

**[Known]** The published state of the art — Elo with one year of data — is about 75% accurate on top-tier matches and competitive with bookmakers; nothing published consistently beats the closing line. **[Likely]** A well-built version of Layers 1–3 will land in the same place: roughly market-equivalent on match winner. **[Hypothesis]** The edge, if any, is in the things the market prices *derivatively* rather than directly — set distributions, physical state, thin early-round matchups — not in the headline match price.

That is the honest framing for the whole project: you are not going to out-forecast Pinnacle on who wins. You might be able to know *how* a specific player wins or loses better than a retail-flooded exchange prices it.

---

## 6. The ten things, one line each

1. **Serve points won %** — the number.
2. **Return points won %** — the other number.
3. **Dominance ratio** — the two combined, opponent-adjusted for free.
4. **Second-serve points won** — where servers separate.
5. **Second-serve return points won** — where returners separate.
6. **First-serve points won** — surface-sensitive; first-serve *percentage* is weak on its own.
7. **First-four-shots win rate** — the tactical layer; 70% of points live here.
8. **Serve speed vs. own baseline** — skill proxy and earliest injury signal.
9. **Rally-length distribution vs. own baseline** — style, surface, and health in one histogram.
10. **Surface-weighted Elo** — the aggregate benchmark every other number has to beat.

Not on the list, deliberately: break-point conversion, head-to-head, ranking, win-loss record, "clutch."

---

## 7. Sources

Academic
- Klaassen, F. & Magnus, J. (2001). *Are points in tennis independent and identically distributed?* JASA 96(454). — momentum and pressure effects, small, larger for weaker players.
- Klaassen, F. & Magnus, J. (2003). *Forecasting the winner of a tennis match.* Eur. J. Oper. Res. — match probability from serve-point differential.
- Barnett, T. & Clarke, S. (2005). *Combining player statistics to predict outcomes of tennis matches.* IMA J. Mgmt. Math. 16(2). — opponent-adjusted serve probabilities.
- Newton, P. & Keller, J. (2005). *Probability of winning at tennis.* Studies in Applied Math. — closed-form hierarchy.
- O'Malley, A.J. (2008). *Probability formulas and statistical analysis in tennis.* JQAS 4(2).
- Knottenbelt, W., Spanias, D. & Madurska, A. (2012). *A common-opponent stochastic model.* Computers & Math. with Applications.
- Sipko, M. & Knottenbelt, W. (2015). *Machine learning for the prediction of professional tennis matches.* Imperial College MEng thesis. — 22 features incl. fatigue/injury; retirement flag.
- Kovalchik, S. (2016). *Searching for the GOAT of tennis win prediction.* JQAS 12(3). — 11 models vs. bookmakers; Elo best; opponent-adjusted best point-based.
- Kovalchik, S. & Reid, M. (2019). *A calibration method with dynamic updates for within-match forecasting.* Int. J. Forecasting 35(2).
- Kovalchik, S. (2020). *Extension of the Elo rating system to margin of victory.* Int. J. Forecasting 36(4).
- Angelini, Candila & De Angelis (2022). *Weighted Elo rating for tennis match predictions.* EJOR 297(1).
- Gollub, J. (2021). *Forecasting serve performance in professional tennis matches.* J. Sports Analytics.
- Wang, C. & Drekic, S. (2026). *Boosting Markovian tennis prediction.* J. Sports Analytics.
- *A Unified Server Quality Metric for Tennis* (2026), arXiv:2602.08083. — serve speed/variability/placement with crossed random effects.
- *Match analysis and probability of winning a point in elite men's singles tennis* (2023), PMC10538650. — surface effects on first/second serve, rally length.

Practitioner
- Sackmann, J. — Tennis Abstract (tennisabstract.com), Heavy Topspin blog, Match Charting Project. Dominance ratio, DR+, break-point regression, surface Elo.
- O'Shannessy, C. — Brain Game Tennis. First four shots; 70/20/10 rally length.
- Ultimate Tennis Statistics — glossary of derived metrics (points/games dominance ratio, serve/return ratings).
- FiveThirtyEight (Morris & Bialik, 2015) — tennis Elo methodology.

Market
- Whelan, K. et al. (2025). *Makers and Takers: The Economics of the Kalshi Prediction Market.* — favorite-longshot bias, maker/taker transfer.
