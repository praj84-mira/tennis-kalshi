# Quantitative Drivers of Tennis Match Outcomes and Design of a Per-Player "Moneyball" Model for US Open Kalshi Markets

## TL;DR
- The single dominant driver of match outcome is the **serve-point-win-probability differential** between the two players; virtually every high-performing pre-match model (Elo variants, Barnett–Clarke opponent-adjusted point models) reduces to this, and no published academic model reliably beats sharp closing lines out-of-sample — treat all claimed betting ROI with heavy skepticism. **[Known]**
- "Clutch" statistics (break-point conversion, tiebreak win-loss) largely regress to the mean and should be shrunk hard or excluded as standalone skills; dominance ratio, serve/return points won, and rally-length dominance (0–4 shots) carry the strongest, most stable signal. **[Known/Likely]**
- For a read-only fair-value engine anchored to Kalshi prices, the highest-value build is a two-parameter (SPW/RPW) point-level Markov engine with Barnett–Clarke opponent-adjustment, surface weighting, recency shrinkage, and an explicit physical-state/injury flag — then reconcile to the market via the Klaassen–Magnus inversion, exploiting Kalshi's documented favorite-longshot bias rather than trying to out-predict the closing line. **[Likely/Hypothesis]**

## Key Findings

**1. Match outcome is overwhelmingly a function of serve/return point-win probabilities.** [Known] O'Malley (2008) proved analytically, under the i.i.d. assumption, that match-win probability depends mainly on the *difference* in the two players' probabilities of winning a point on serve. Klaassen & Magnus (2001), using a panel of almost 90,000 points from Wimbledon 1992–1995, showed points "are neither independent nor identically distributed … Deviations from iid are, however, small and hence the iid hypothesis will still provide a good approximation in many cases." This is the theoretical backbone of the entire point-based modeling tradition.

**2. Total points won is a near-deterministic proxy — but with a critical nonlinear zone.** [Known] Per Inpredictable data cited by LSports, only 4.5% of ATP matches are won by the player who scored fewer points; at the set level 2.4%. Winning 51% of points ≈ 85% match-win probability; 52% ≈ >95%. This steep sensitivity is why small edges in serve/return quality translate into large win-probability swings, and why "lottery matches" (won on fewer return points) are rare.

**3. Dominance Ratio (DR) is the best single summary stat.** [Known] DR = (return points won %) / (opponent's return points won %) = RPW/(1−SPW). Invented by Carl Bialik, a DR of 1.0 = even; winners are usually >1.0. It captures match control better than total points won and is especially decisive in the women's game where return play weighs heavily.

**4. Rally length: the O'Shannessy 70/20/10 split is well-documented but is a descriptive tournament aggregate, not a peer-reviewed causal law.** [Known/Likely] From 2015 IBM/Slam data: ~70% of men's points and ~66% of women's are 0–4 shots; ~20%/~23% are 5–8; ~10%/~11% are 9+. The most common single rally length is 1 shot (~30% of points). The match winner wins 0–4 rallies ~90% of the time (O'Shannessy). Brain Game Tennis reports 2024 US Open average rally length of 3.87 shots for both men and women — essentially identical.

**5. "Clutch" regresses to the mean.** [Known] Jeff Sackmann (Heavy Topspin/Tennis Abstract) shows tiebreak results and break-point performance have no persistent special skill beyond a player's underlying serve/return quality — long hot/cold streaks should be expected to revert. Break-point conversion beyond what return quality predicts "will eventually regress to the mean."

**6. Surface materially shifts serve effectiveness and rally length.** [Known] PLOS One / PMC10538650 (2021 Slams, men): first-serve effectiveness 69% clay, 75% grass, 75% hard; second-serve ~55% regardless of surface. Women (PMC9266198): first serve 62.4% clay, 64.2% grass, 67.5% hard. Short rallies more common on faster surfaces.

**7. ATP vs WTA differ structurally.** [Known/Likely] Men serve faster and hold more — the very top ATP servers exceed 90% of service games held (per Opta Ace via Tennis Temple, Jannik Sinner led the 2024 tour at 91.4%, ahead of Zverev 90.1%, Shelton 89.1%, Hurkacz 88.7%, Fritz 88.3%; Sackmann's Heavy Topspin puts Sinner's full-2024 hold at 91.5%) — and reach more tiebreaks; women break more often and show higher set volatility. TennisRatio data: from 0–40 down, ATP servers hold 17% vs WTA 10%; from 30-30/40-40 servers hold 74% (ATP) vs 63% (WTA); WTA players face ~2.31 pressure points per service game vs 1.61 ATP.

**8. Prediction accuracy degrades for lower-ranked players.** [Known] Kovalchik (2016) benchmarked 11 models on 2014 ATP; FiveThirtyEight Elo hit ~75% accuracy for top-ranked matches, competitive with bookmakers; career-to-date data improved lower-ranked accuracy from 59% to 64%. The Bookmaker Consensus Model was best (~72% overall). No model beat the market.

**9. The ceiling is ~70% accuracy and the market is essentially unbeatable.** [Known] Wilkens (2021) ran an extensive ML survey and found accuracy plateaus at ~70%, the same as bookmaker odds. A recent unified ML/DNN benchmark (Analytics 2024) concluded "Elo alone captures most of what can be captured from universally available pre-match features, and even the best learned model … remains below market-implied accuracy."

**10. Kalshi has a documented, exploitable favorite-longshot bias.** [Known] Bürgi, Deng & Whelan (2025, "Makers and Takers") analyzed 300,000+ contracts: low-price contracts win less often than break-even (contracts <10¢ lose >60%), contracts >50¢ earn small positive returns. Takers lose ~32% on longshots; makers ~10%. Jonathan Becker's 72.1M-trade analysis ($18.26B volume, 2021–2025) found takers earn −1.12% mean excess return per trade while makers earn +1.12%, strongest in Sports/Entertainment.

## Details

### 1. The statistical hierarchy of what drives wins

**Serve-point sensitivity (foundational).** [Known] O'Malley (2008, *J. Quantitative Analysis in Sports* 4(2)) derived closed-form expressions for winning a game/set/tiebreak/match under i.i.d. point outcomes, and his central result — echoed by Newton & Keller (2005) and Barnett–Clarke — is that match-win probability is "mainly dependent on the difference of the probabilities of players winning a point while serving" (Knottenbelt et al. 2012 restating O'Malley). O'Malley plots the better player's match-win probability for fixed serve-probability differences of 0.01, 0.02, 0.05, 0.10; even a 2-point serve edge produces a large match-win edge in best-of-three. Klaassen & Magnus (2001, *JASA* 96(454):500–509) analyzed almost 90,000 Wimbledon points (1992–1995) and found points "are neither independent nor identically distributed" but the deviations are small, so the i.i.d. hypothesis "will still provide a good approximation in many cases." [Known]

**Total points won.** [Known] Only 4.5% of ATP matches (2.4% of sets) are won by the player winning fewer points (Inpredictable, via LSports). The mapping is steeply nonlinear near 50%: 51% of points ≈ 85% match win; 52% ≈ >95% (best-of-three). This is the quantitative reason serve/return quality dominates.

**Dominance Ratio.** [Known] DR = RPW / (opponent RPW) = RPW/(1−SPW), invented by Carl Bialik. Matches are occasionally won with DR<1.0 ("lottery matches," Bialik/Sackmann) but these are rare. DR is the recommended single control metric; it is more informative than winners/unforced errors and, per multiple analytics sources, especially predictive in the WTA where return games decide more matches.

**First vs second serve.** [Known] First-serve *points won* matters far more than first-serve *percentage*; players winning >~75% of first-serve points are very hard to break (Tennisnerd). ATP Tour "Serve Effectiveness" INSIGHTS: tour-average first-serve effectiveness is 58% (aces 16%, unreturned 22%, attacking first ball 20%); second-serve effectiveness averages 23%. Second-serve points won is a strong differentiator of elite servers/returners because second serve strips out the ace shield.

**Break points / tiebreaks — regress to the mean.** [Known] Sackmann (Heavy Topspin, 2015 & 2019): "there's no special tiebreak skill"; better players win more tiebreaks because they are better, not because of a clutch gene. Break-point conversion beyond return-quality expectation "will eventually regress to the mean." Implication for modeling: do NOT feed raw break-point or tiebreak win rates as standalone skill features — shrink them to serve/return baselines. Note conflict: some betting-oriented sources (Core Sports Betting) argue break-point conversion carries hidden predictive value, especially on clay; this is weakly supported vs. the Sackmann regression evidence, which is stronger. [Likely]

**Pressure/"important" points.** [Known/Likely] Klaassen & Magnus established systematic (if small) variation in performance with pressure; Knight & O'Donoghue (2012) found receivers win break points at higher-than-baseline rates. Academic "clutch" measurement (SA-IJAS) exists but finds pressure effects are small and noisy at the player level.

**Rally length & first-four-shots.** [Likely] O'Shannessy's 70/20/10 (0–4 / 5–8 / 9+ shots) is confirmed across multiple independent restatements of the 2015 IBM Australian Open/US Open data and NYT reporting: "71 percent of the points in men's singles … and 66 percent on the women's side came on rallies of four shots or fewer" (O'Shannessy in NYT). The winner-wins-90%-of-0–4-rallies claim is O'Shannessy's own analysis, not peer-reviewed. Peer-reviewed adjacent confirmation: the Bayesian isotonic serve-advantage paper (arXiv 1909.03802) using Sackmann data found rallies ≤4 shots constitute ~90% of rallies and that the server's win probability is higher on odd-numbered shot counts (server ends the rally). The rally-length-as-player-characteristic question is treated peer-reviewed in *JRSS Series A* (2025, "What does rally length tell us about player characteristics"). [Known for the descriptive splits; Likely for the causal "win the short points, win the match" framing.]

**Serve speed/placement.** [Likely] ATP tracking (INSIGHTS) shows serve placement to T/wide zones in short rallies yields the highest efficiency (up to 86.3% on hard courts, PMC surface studies); serving to the center reduces success and lengthens rallies. First-serve placement clusters near the sidelines (~68% of successful first serves near service-box sidelines per arXiv 2506.05866); second serves are placed more conservatively (NCTL depth).

### 2. Variation by player, surface, gender, rank tier

**Archetypes & matchups.** [Likely] Serve-dominant (first-strike) players concentrate value in 0–4 shot rallies; grinders extract value in 5–8 and 9+ rallies. The Match Charting Project (Sackmann, 5,000+ matches shot-by-shot) is the public data source for return-position and serve-direction tendencies. The Unified Server Quality Metric (arXiv 2602.08083) finds serve-quality signal concentrates in the opening exchange, strongest at Wimbledon (grass, r≈0.56–0.67 with serve efficiency) and weaker at the US Open (hard, r≈0.24–0.28) — matchup and surface interact.

**Surface effects (quantified).** [Known]
- Men (PMC10538650, 2021 Slams, 4,669 points): first-serve effectiveness 69% clay / 75% grass / 75% hard; second serve ~55% all surfaces; server won first-serve short-rally points 65% clay to 75% grass/hard.
- Women (PMC9266198 / MDPI 7955, 2019 Slams, 2,759 points): first-serve effectiveness 62.4% clay / 64.2% grass / 67.5% hard; second-serve effectiveness dropped 5.5/11.2/14.5 points from first on clay/grass/hard.
- More medium/long rallies on slower (clay) surfaces; more short rallies and aces on faster surfaces.

**ATP vs WTA.** [Known/Likely] Serve advantage is larger and hold rates higher in ATP (top servers >90%, e.g., Sinner 91.4–91.5% in 2024); WTA has higher break frequency and set volatility (Tennisnerd). The serve-advantage paper (arXiv 1909.03802) quantifies average serve point-win: men 64% serve / 37% return; women 58% serve / 44% return. First-server effect on games is much stronger in ATP (odds ratio 7.59) than WTA (1.80) (arXiv 2605.04867). Pressure-point recovery: ATP servers recover from 0–40 17% vs WTA 10% (TennisRatio).

**Rank tier.** [Known] Kovalchik (2016): accuracy is highest for top-ranked matchups (~75% FiveThirtyEight, competitive with books) and drops materially for lower-ranked players; career-to-date data lifted lower-ranked accuracy from 59% to 64%. The Probit Plus model had excellent Slam accuracy but ~10% worse for lower-tier tournaments — a 10–20 point spread between tiers is consistent across models. [Known]

### 3. Injuries, fatigue, layoffs

**What moves first physiologically.** [Known/Likely] Sports-science evidence:
- A single match significantly reduces dominant-shoulder internal-rotation ROM (−1.3%) and external-rotation isometric strength (−4.8%), but serve speed was NOT significantly reduced after one ~80-min match (−1.16%, p=0.197) (PMC6461272). After a 3-hour match, leg-muscle EMG activation fell 10–40% on first serves, yet maximum ball velocity was statistically unchanged (159→154 km/h first serve; PMC11451554) — skilled players compensate. [Known]
- Fatigue meta-analysis (PMC12069318): fatigue increases serve/defensive-shot error rates and reduces accuracy (stroke accuracy down up to 49.6% under high-intensity conditions), footwork and trunk stability degrade. [Known]
- **Implication:** serve *speed* is a lagging/robust indicator; the *early* movers under fatigue/injury are accuracy-driven — first-serve %, double faults, second-serve depth/effectiveness, and error rates in longer rallies. Return depth and movement-dependent stats degrade before raw serve power. [Likely/Hypothesis — direct pre-retirement match-stat studies were not located; this is inferred from acute fatigue biomechanics.]

**How models handle it.** [Known]
- Sipko & Knottenbelt (2015, Imperial MEng) engineered 22 features "including abstract features such as player fatigue and injury," and reported an ANN ROI of 4.35% (a ~75% improvement over prior stochastic models) — a claim to treat skeptically (student project, limited out-of-sample, betting-market era-specific).
- Retirements/walkovers: standard practice (FiveThirtyEight Elo, most implementations) is to exclude retirements from rating updates or flag them; Kovalchik uses career-to-date adjustments.
- Fatigue/minutes-on-court and five-setter carryover are used as features but with weak documented lift. [Likely]

**Data availability.** [Known] ATP tracking summaries (INSIGHTS/Hawk-Eye derived) since ~2018 are largely post-match published aggregates. Slam Infosys/IBM stats are published live for broadcast but not distributed as clean feeds. Live low-latency data now flows to Kalshi via the Catalist Sports deal (see §6). Serve speed and placement are broadcast-live but only reliably available post-match in structured form to the public.

### 4. State of the art in prediction (2016–2026)

**Baselines & Elo family.** [Known]
- Kovalchik (2016): definitive benchmark; FiveThirtyEight surface-weighted Elo and the Opponent-Adjusted point model were best non-market approaches; BCM (bookmaker consensus) best overall.
- Kovalchik (2020): extended Elo to margin-of-victory (*Int. J. Forecasting* 36(4):1329–1341).
- Angelini, Candila & De Angelis (2022, *EJOR* 297(1):120–132): Weighted Elo (WElo) incorporating a "hot hand"/recent-margin weighting; claims to outperform popular methods and (in a simple betting strategy) "profitable opportunities" — but the same authors' data was later shown by Whelan-type and GNN analyses to over-bet longshots. R package `welo` available. [Known for method; Likely-skeptical for profitability.]
- Vaughan Williams et al. (2021): how well Elo predicts, *J. Quant. Anal. Sports*.

**Point-based lineage.** [Known] Barnett–Clarke (2005) opponent-adjusted serve probabilities → Knottenbelt et al. (2012) common-opponent model → Spanias & Knottenbelt (2013) low-level point model → Ingram (2019) Bayesian hierarchical (point-based) → Gollub (2021) serve forecasting via Elo-derived serve parameters → Wang & Drekic (2026) ensembling of point-based methods, which "boost average prediction accuracies to around 70%, on par with machine learning models."

**2024–2026 ML.** [Known] arXiv 2502.01613 (statistical enhanced learning, Grand Slams) and the Analytics 2024 unified ML/DNN benchmark both converge on the ~70% ceiling and confirm learned models stay below market-implied accuracy. The Unified Server Quality Metric (arXiv 2602.08083) is a new serve-quality standardization. A GNN approach (arXiv 2510.20454) reports Brier 0.215 vs bookmaker 0.196 — i.e., still worse than the market.

**Does anything beat closing lines?** [Known — skeptical] No peer-reviewed model robustly beats sharp (Pinnacle) *closing* lines out-of-sample. Reported ROIs (Sipko 4.35%; Cornman et al. 3.3%/match; various 15–35% blog backtests) are overwhelmingly in-sample, small-sample, opening-line, or era-specific. Practitioner honesty is instructive: one 2026 practitioner (DataDrivenInvestor) with +11.3% over 263 real signals wrote "I still don't trust it"; another (+35% ROI backtest over 2,591 bets) flagged the result as "suspicious." Closing-line value against a de-vigged sharp book is the only honest yardstick. [Known]

**Within-match / live.** [Known] Kovalchik & Reid (2019, *Int. J. Forecasting* 35(2):756–766) combined pre-match calibration with a dynamic empirical-Bayes update; their dynamic model delivered a **28% reduction in in-match serve-prediction error and +4 percentage points win-prediction accuracy vs. a constant-ability (static Markov) model**, validated on the 2017 season. On market over-reaction: multiple trading sources (TennisRatings, Smarkets) document that markets can over-react to a break or lost set, creating live value if the reason for the set loss is judged to be variance rather than genuine decline.

**Favorite recovery after losing a set (best-of-five, Slams).** [Known/Likely]
- Best-of-five reduces variance: Grand Slam favorites win ~76% vs ~63–68.5% at ATP 250s (TennisRatings/Smarkets); five-set format makes the favorite ~5% more likely to win vs best-of-three.
- Slam men's match length (Askalidis/Medium, 1990–Jan 2024): "About 19% of all matches in Grand Slams since 1990 had 5 sets. 48% had exactly 3 sets and 31% had exactly 4 sets," with the US Open slightly lower at 46.8% three-setters.
- First-set winner wins the match with substantial probability; the first-set winner broke first in set two ~66% of the time (TennisRatings).
- 0–2 comebacks are rare: On The Line Tennis (Open Era dataset) finds players who dropped the first two sets went on to win "5.90% of the time … 935 of 15848 matches … approximately 1 in every 17 matches," most likely at the Australian Open and least likely at Wimbledon. (Conditional on the specific matchup, when a two-sets-down comeback does force a decider the trailing player's overall win rate rises — Australian Open 57.1%, Wimbledon ~50/50 — reflecting selection toward stronger comeback players.)

### 5. Building the per-player model

**Combining serve & return (Barnett–Clarke).** [Known] The exact opponent-adjusted formula (Barnett & Clarke 2005, Eq. 2) is:

**f_ij = f_t + (f_i − f_av) − (g_j − g_av)**

where **f_t** = average serve-winning probability at the tournament; **f_i** = player i's average serve-winning probability; **f_av** = tour-average serve-winning probability; **g_j** = opponent j's average return-winning probability; **g_av** = tour-average return-winning probability. (Note: this corrects a common shorthand `f_ij = f_i − g_j + g_av`, which omits the tournament intercept f_t and the re-centering of f_i on f_av.) The formula is symmetric: since f_t + g_t = 1, it follows f_ij + f_ji = 1. Barnett–Clarke applied it to Roddick–El Aynaoui (2003 AO QF), giving Roddick 72.3% on serve and 32.0% on return, with El Aynaoui at 68.0% serve / 27.7% return. The sum t = f_ij + f_ji is used as a proxy for match length/rally environment. Best practice adds: shrinkage for small samples, surface adjustment, recency weighting.

**Two-parameter (SPW, RPW) vs single-differential.** [Likely] Two-parameter models are required if you want set-score and total-games *distributions* (not just match-winner), because the *sum* f_ij+f_ji governs the number of points/games and thus over/under and set-betting markets, while the *difference* governs the winner. A single-differential (Elo) model is competitive for match-winner accuracy but cannot produce a correct games/sets distribution. For a Kalshi engine pricing set and total-games markets, the two-parameter Markov engine is necessary.

**Klaassen–Magnus market inversion.** [Known] Given a pre-match win probability π_ij (e.g., from the market or Elo), impose f_ij + f_ji = b (overall serve ability) and back out serve parameters consistent with that win probability (Klaassen & Magnus 2003; Gollub 2021 applies with Elo forecasts). This is exactly the "anchor to pre-match prices" step for a read-only fair-value model.

**Data sources & status.** [Known]
- **Jeff Sackmann tennis_atp / tennis_wta:** the canonical public repos. The `raw.githubusercontent.com/JeffSackmann/tennis_atp/master/...` paths 404'd in Sept 2026 — GitHub renamed the default branch from `master` to `main` in past migrations, and Sackmann's account shows the repos active (Match Charting Project "Updated May 25, 2026"). Fix: use the `main` branch path or the GitHub UI; mirrors include Tennismylife/TML-Database (live-updated, now at stats.tennismylife.org) and BigTimeStats/atp-tennis. The Match Charting Project repo (5,000+ shot-by-shot matches) is active. License: CC BY-NC-SA 4.0 (non-commercial). [Known]
- **Ultimate Tennis Statistics, ATP/WTA official stats:** public, post-match.
- **Paid feeds:** Sportradar, api-tennis, etc., provide live scores; latency and coverage vary. Catalist Sports (via Kalshi) covers 65,000+ matches/year with low-latency official data.

**Set-winner / total-sets pricing.** [Likely] Evidence suggests markets price match-winner efficiently but set-score and total-games markets less so (TennisRatings' "first set wins: the most undervalued market"; deciding-set conditional stats). This is where a well-calibrated two-parameter Markov engine has the best chance of finding fair-value gaps.

### 6. Prediction-market context (Kalshi)

**Favorite-longshot bias.** [Known] Bürgi, Deng & Whelan (2025, CESifo/UCD WP; "Makers and Takers"): 300,000+ contracts; contracts <10¢ lose >60% of stake; contracts >50¢ earn small positive returns; bias present for both makers and takers but stronger for takers (takers lose ~32% on longshots vs makers ~10%); bias weakening over time (2025 ψ coefficient smaller). Prices are informative and improve toward closing.

**Becker microstructure.** [Known] Jonathan Becker (Jan 2026; "The Microstructure of Wealth Transfer in Prediction Markets"): 72.1M trades, $18.26B volume, June 2021–Nov 2025. Takers earn −1.12% mean excess return per trade; makers +1.12%. Contracts at 5¢ win only 4.18% (implied mispricing −16.36%); 95¢ contracts win 95.83%. Effect strongest in Sports/Entertainment; Finance near-efficient. Sports: taker/maker gap 2.23pp across 43.6M trades, ~$6.1B taker volume. (The transfer is reported as a per-trade percentage, not a single aggregate dollar figure.)

**Kalshi 2026 US Open & fees.** [Known] Kalshi became the Official Prediction Market Partner of the US Open starting with the 2026 main draw (USTA deal; integrity framework with ITIA restricting umpire/code-violation markets). Kalshi's own figure, announced with the partnership (Sports Video Group, Sept 1 2026), is that "tennis-related trading volume on the platform is up 25x YoY"; USTA CEO Craig Tiley framed it as pioneering "that next generation of fan engagement while ensuring the integrity of our sport." The Catalist Sports streaming/data deal (announced Aug 18, 2026) was reported and then the announcement was pulled/withdrawn by at least one outlet (LegalSportsReport) — status ambiguous. Fee formula: taker fee = ceil(0.07 × C × P × (1−P)); maker fee = ceil(0.0175 × C × P × (1−P)); max taker fee $0.0175/contract at 50¢. Maker fees apply only on "designated series"; the 0.0175 multiplier is the designated-event maker rate. Whether US Open markets carry the designated maker fee should be verified against Kalshi's live fee-schedule PDF before trading — API metadata does not reliably expose which series charge makers (PredArena).

## The ~10 statistics with the strongest evidence (ranked)

1. **Serve-point-win-probability differential (SPW_i − SPW_j)** — the analytic driver of match outcome (O'Malley 2008; Klaassen–Magnus). [Known]
2. **Return points won %** — the other half of the two-parameter core; the scarce, decisive resource (breaks). [Known]
3. **Dominance Ratio (RPW/(1−SPW))** — best single control summary; predicts winner better than total points in tight matches. [Known]
4. **Total points won %** — near-deterministic proxy with steep nonlinearity around 50%. [Known]
5. **First-serve points won %** (not first-serve %) — hold-strength driver; >75% ≈ very hard to break. [Known]
6. **Second-serve points won %** (server) and **second-serve return points won %** — strip the ace shield; separate elite from average. [Known]
7. **0–4 shot ("first-strike") rally win rate** — ~70% of points; winner takes them ~90% of the time. [Likely]
8. **Surface-specific serve/return splits** — first-serve effectiveness swings ~6–13 pts by surface. [Known]
9. **Hold %/break % baseline by tour** (ATP vs WTA volatility regime). [Known/Likely]
10. **Ace and double-fault rates** — secondary, informative for serve variance and (DF) fatigue/injury signal. [Likely]

Explicitly *demoted*: break-point conversion %, tiebreak W-L, and "clutch" ratings — these regress to the mean and should be shrunk to serve/return baselines rather than used as standalone skills. [Known]

## Recommendations

**Stage 1 — Build the core engine (do first).**
1. Ingest Sackmann tennis_atp/tennis_wta (via `main` branch) + Match Charting Project; compute per-player SPW, RPW, first/second-serve splits, by surface.
2. Implement Barnett–Clarke opponent-adjustment: f_ij = f_t + (f_i − f_av) − (g_j − g_av), with hard-court/US Open f_t.
3. Wrap in an O'Malley/Markov point→game→set→match engine producing full set-score and total-games distributions.
4. Anchor to market via Klaassen–Magnus inversion of the Kalshi/Pinnacle pre-match price.
*Kill criterion:* if your engine's match-winner Brier vs a de-vigged sharp closing line is worse than a plain surface-weighted Elo, stop adding complexity and revert to Elo for the winner market.

**Stage 2 — Calibrate & shrink.**
5. Apply recency weighting (exponential decay ~12 months) and James-Stein/empirical-Bayes shrinkage toward tour/surface means for low-sample players.
6. Explicitly shrink break-point and tiebreak stats to serve/return baselines — do NOT use them as standalone features.
*Threshold:* require ≥~20–30 matches on surface before trusting player-specific serve parameters; below that, weight toward the shrinkage prior.

**Stage 3 — Physical-state / injury overlay.**
7. Build a physical-state flag from: days since last match (layoff), minutes-on-court in prior 7/14 days, five-setters in last round, retirements/MTOs in recent matches, and (if available) first-serve % and double-fault trend vs the player's own baseline.
8. Weight the flag toward *accuracy* stats (first-serve %, DF rate, second-serve effectiveness) which move first under fatigue/injury, and away from serve speed which is robust.
*Threshold to act:* widen your model's uncertainty band (not just shift the point estimate) when the flag fires; only deviate from market when the flag is corroborated by a stat drop AND the market has not moved.

**Stage 4 — Trade selection exploiting documented bias.**
9. Given Kalshi's favorite-longshot bias and Becker/Whelan evidence, systematically avoid buying sub-15¢ longshots; prefer maker (resting limit) orders to capture the +1.12% structural edge and the ~4× lower fee.
10. Focus fair-value hunting on set-score and total-games markets (less efficiently priced) rather than match-winner (efficiently priced).
*Kill criterion:* if realized closing-line value is not consistently positive over ≥200 trades, assume no edge and treat the system as read-only/informational.

## Top 5 open questions the literature does not answer
1. **What match statistics change first, and by how much, in the matches immediately preceding an injury retirement or a documented injury** — no direct pre-retirement stat-decay study was located; the accuracy-before-power hypothesis is extrapolated from acute-fatigue biomechanics.
2. **Whether a two-parameter (SPW/RPW) Markov engine prices set-score and total-games distributions better than the market** — practitioner claims exist (first-set/total-games mispricing) but no rigorous, out-of-sample, market-benchmarked study.
3. **How much return-from-layoff (weeks off, post-surgery) durably degrades serve/return parameters, and for how long** — modeled crudely (career-to-date, exclusion flags) with no quantified recovery curve.
4. **Whether live markets systematically over-react to a lost set/break in a way that is exploitable net of fees** — repeatedly asserted by trading sources, never cleanly demonstrated out-of-sample.
5. **Whether Kalshi's favorite-longshot bias persists in the specific, newly-liquid US Open singles markets (2026+) or arbitrages away** — the bias is documented on legacy Kalshi data and is weakening over time; its magnitude in high-volume, officially-partnered tennis markets is untested.

## Caveats
- **The market is the benchmark and it usually wins.** Every credible study caps non-market accuracy at ~70% and finds models below market-implied accuracy. Do not expect to out-predict the closing line; expect to exploit structural pricing biases at the margins.
- **All betting ROI figures cited are suspect.** Sipko's 4.35%, Cornman's 3.3%, WElo's "profitable opportunities," and blog backtests of 15–35% are variously in-sample, opening-line, small-sample, or era-specific. Treat them as hypotheses, not evidence of a durable edge.
- **The 70/20/10 rally split and "win-the-short-points" are descriptive, not causal law** — they are O'Shannessy/IBM tournament aggregates, corroborated but not established as a peer-reviewed predictive model.
- **Injury pre-retirement stat-change studies were not located** — the injury-overlay design is inferred from acute fatigue biomechanics (serve speed robust; accuracy degrades first), which is a reasonable but untested extrapolation to the injury case.
- **Kalshi–Catalist data-deal status is ambiguous** (announced then pulled by at least one outlet); confirm live-data provenance before relying on it. Confirm whether US Open markets carry the designated maker fee.
- **Data licensing:** Sackmann data is CC BY-NC-SA 4.0 (non-commercial); a commercial fair-value/trading tool may violate the license — obtain appropriate data rights.
- **Where sources conflict:** break-point conversion's predictive value (Sackmann regression skepticism vs betting-source advocacy) — I weight Sackmann's regression evidence more heavily. WElo profitability claims conflict with independent longshot-overbetting findings — I weight the skeptics more heavily.

## References
- Klaassen & Magnus (2001), *JASA* 96(454):500–509 — i.i.d. points. https://www.janmagnus.nl/papers/JRM065.pdf
- Klaassen & Magnus (2003), *EJOR* 148(2):257–267 — forecasting the winner. https://www.sciencedirect.com/science/article/abs/pii/S0377221702006823
- O'Malley (2008), *JQAS* 4(2) — probability formulas. https://ideas.repec.org/a/bpj/jqsprt/v4y2008i2n15.html
- Barnett & Clarke (2005), *IMA J. Management Mathematics* 16(2):113–120. https://academic.oup.com/imaman/article-abstract/16/2/113/704903
- Knottenbelt, Spanias & Madurska (2012), *Computers & Math with Applications* — common-opponent. https://www.sciencedirect.com/science/article/pii/S0898122112002106
- Kovalchik (2016), *JQAS* 12(3):127–138 — "Searching for the GOAT." https://vuir.vu.edu.au/34652/1/jqas-2015-0059.pdf
- Kovalchik (2020), *Int. J. Forecasting* 36(4):1329–1341 — Elo margin of victory.
- Kovalchik & Reid (2019), *Int. J. Forecasting* 35(2):756–766 — within-match calibration. https://www.sciencedirect.com/science/article/abs/pii/S0169207017301395
- Angelini, Candila & De Angelis (2022), *EJOR* 297(1):120–132 — Weighted Elo. https://www.sciencedirect.com/science/article/abs/pii/S0377221721003234
- Ingram (2019), *JQAS* 15(4):313–325 — Bayesian hierarchical point model. https://martiningram.github.io/papers/bayes_point_based.pdf
- Gollub (2021), *J. Sports Analytics* — serve performance forecasting. https://journals.sagepub.com/doi/10.3233/JSA-200345
- Wang & Drekic (2026), *J. Sports Analytics* — ensembling markovian prediction. https://journals.sagepub.com/doi/10.1177/22150218251412670
- Wilkens (2021), *J. Sports Analytics* — ML survey, ~70% ceiling. https://doi.org/10.3233/JSA-200463
- Sipko & Knottenbelt (2015), Imperial College MEng. https://www.doc.ic.ac.uk/teaching/distinguished-projects/2015/m.sipko.pdf
- Unified Server Quality Metric (2026), arXiv 2602.08083. https://arxiv.org/pdf/2602.08083
- Statistical enhanced learning (2025), arXiv 2502.01613. https://arxiv.org/pdf/2502.01613
- Intransitive dominance GNN (2025), arXiv 2510.20454. https://arxiv.org/html/2510.20454v1
- Serve advantage isotonic regression (2019), arXiv 1909.03802. https://arxiv.org/pdf/1909.03802
- First-server effect (2026), arXiv 2605.04867. https://arxiv.org/pdf/2605.04867
- Match analysis men, surface (2021), PLOS One / PMC10538650. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10538650/
- Match analysis women, surface (2022), PMC9266198 / MDPI 7955. https://www.mdpi.com/1660-4601/19/13/7955
- Rally length & player characteristics (2025), *JRSS Series A* 188(1):188. https://academic.oup.com/jrsssa/article/188/1/188/7634720
- Acute serve/shoulder effects, PMC6461272. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6461272/
- Prolonged play & serve EMG, PMC11451554. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11451554/
- Fatigue meta-analysis, PMC12069318. https://pmc.ncbi.nlm.nih.gov/articles/PMC12069318/
- O'Shannessy rally length: Tennis.com, SportsEdTV, Brain Game Tennis. https://www.tennis.com/news/articles/how-craig-o-shannessy-brings-the-analytics-revolution-to-tennis
- Sackmann Heavy Topspin — break points / tiebreaks regress. https://www.tennisabstract.com/blog/2019/01/04/measuring-the-impact-of-break-points/
- ATP INSIGHTS Serve Effectiveness. https://www.atptour.com/en/news/insights-serve-effectiveness
- TennisRatio pressure points ATP/WTA. https://www.tennisratio.com/analysis-atp.html
- Askalidis, 0–2 down comebacks (Medium, 1990–2024). https://medium.com/@yaskalidis/a-deep-dive-into-2-0-down-comebacks-in-tennis-97de01e7d3ec
- On The Line Tennis, 0–2 comeback Open Era. https://onthelinetennis.substack.com/p/0-2-down-the-chance-of-making-a-comeback
- Smarkets Grand Slam trading strategy. https://help.smarkets.com/hc/en-gb/articles/115000821689-Tennis-Grand-Slam-trading-strategy
- Bürgi, Deng & Whelan (2025), "Makers and Takers." https://www.karlwhelan.com/Papers/Kalshi.pdf
- Becker (2026), Kalshi microstructure. https://www.jbecker.dev/research/prediction-market-microstructure
- Kalshi–USTA US Open partnership. https://www.sportcal.com/sponsorship/us-open-adds-kalshi-as-new-commercial-partner-amid-ny-lawsuit/
- Kalshi–Catalist deal (announced/pulled). https://www.legalsportsreport.com/273319/kalshi-catalist-live-streaming-deal-announced-then-pulled/
- Kalshi fee schedule. https://kalshi.com/docs/kalshi-fee-schedule.pdf
- Sackmann tennis_atp / Match Charting Project. https://github.com/JeffSackmann
- Tennisnerd ATP vs WTA betting. https://www.tennisnerd.net/articles/betting-strategies-for-atp-vs-wta-markets/68302