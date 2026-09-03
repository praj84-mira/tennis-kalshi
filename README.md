# usopen-fairvalue

A read-only fair-value monitor for live US Open singles markets on Kalshi.
It exists to answer one question before any money or automation goes in:

> Does a score-only Markov model beat the Kalshi mid on Brier score, on the
> rows where they disagree?

If no: there is no edge from score mechanics and the trading app should not
be built. If yes: size it, then decide. **There is no order code in this
package, by design.** See `docs/PROJECT_BRIEF.md` for the reasoning.

## Run

```
python3 app.py                  # dashboard at http://127.0.0.1:8765 (runs the monitor loop itself)
python3 backtest.py fetch       # ~1,750 settled matches since Wimbledon, 1-min Kalshi prices, cached in data/hist/
python3 backtest.py analyze     # calibration + H1/H2/reload P&L report -> data/hist/report.txt
python3 monitor.py              # headless monitor: every 30s, appends data/monitor.csv
python3 monitor.py --once       # one tick, print the table
python3 settle.py --min-gap 0.05          # after matches settle: Brier model vs market
python3 fair.py --tour ATP --anchor 0.92 --sets 0-1 --games 2-2 --server A --pts 30-40 --mid 0.67
python3 tradelog.py TICKER yes 0.31 10 "why"   # log a discretionary trade BEFORE it resolves
python3 latency.py TICKER                      # the stopwatch test; one match, ten Enter presses
python3 -m unittest tests.test_markov
```

No dependencies beyond Python 3.10+. Both feeds are free and unauthenticated.

## What a row means

| column | meaning |
|---|---|
| `anchor` | Kalshi's last trade on player A before ESPN's scheduled start. Fixed for the match. |
| `d_pre` | strength differential fitted to `anchor`; A serves at `base + d/2`, B at `base − d/2` (ATP base 0.64, WTA 0.57) |
| `fair` | P(A wins) now if only the score had changed since the anchor |
| `gap` | `fair − mid`. Positive = model thinks A is cheap. |
| `update_pts` | serve-point re-rating of A the live price implies. "The market thinks Alcaraz holds at 68% not 72%" is a checkable claim. |
| `server` | `A`/`B` observed from ESPN, `a`/`b` inferred by parity from an earlier observation this set, `?` unknown (fair is then averaged over both) |

Read: **large gap + small update** = disagreement about score mechanics, worth
a look. **Large gap + large update** = the market decided someone is playing
differently than expected; the model has no opinion on that.

## Why the anchor is the market, not a player model

Head-to-head, surface record, round, time of day, form, ranking: those are
pre-match inputs, and the Kalshi opening price already carries the whole
market's view of them. Re-deriving them means competing with the opening
line, which the research says is efficient. This package deliberately does
not. It holds the pre-match price fixed and asks only whether the market
prices the *score* correctly.

The one player-level input that changes the in-play number is serve/return
shape (big servers make a break worth more, grinders less). Measured effect
with the level fixed: under 0.1 pt at set-level states, 2-6 pts mid-set at
a break. `priors.py` builds those profiles from Sackmann's match CSVs on
your machine (see its docstring); the monitor uses them automatically when
`data/priors.json` exists and shows "profiles" on the row.

## Hypotheses

Every live row gets a verdict (`act` / `look` / `walk`) and a list of
checkable reasons for the gap, in `hypotheses.py`: wide spread, stale ESPN
score while the price moved, unknown server (both fairs shown), tiebreak
with unknown points, 45-55c fee zone, score-mechanics disagreement vs.
market re-rating, best-of-five reload, extreme price. They are derived from
the row, not predicted; the point is to make the next action obvious.

## Backtest (what history can and cannot answer)

Kalshi serves the full 1-minute price path for every settled ATP/WTA match
market since the series opened at Wimbledon 2026. ESPN has no historical
play-by-play. So:

- **Can test on history:** in-play and pre-match calibration (do 10¢ contracts
  win 10%?), H1 favorite bands, H2 longshots, and the best-of-five reload as a
  *price-drop* rule. That is `backtest.py`. ~1,750 matches.
- **Cannot test on history:** the score-conditional Markov model. That still
  needs the live monitor and the Brier test below.

Read the report's `t` column before the `mean` column. One entry per match,
hold to settlement, taker at the displayed ask; maker rows are an upper bound.

## Backtest result (2026-09-03, 1,655 matches, Wimbledon through US Open R64)

Full report: `reports/backtest-2026-09-03.txt`. Summary:

- **In-play prices are calibrated to within half a point in every 5c bin, both
  tours.** No favorite-longshot bias to harvest in tennis on Kalshi.
- **Every price-level taker rule loses about the fee.** H1 favorite bands:
  -2 to -4c per contract, t = -2 to -3. H2 longshots: -1 to -2c, t = -2 to -3.
  Best-of-five reload (favorite >= 0.70 whose ask fell 10-30 pts): -2 to -5c
  at every threshold, n = 190-330. Maker-side upper bounds are also negative.
- **One suggestive pre-match bin:** favorites priced 0.90-1.00 at the scheduled
  start won 96 of 97 (priced at 93%). p ~ 0.01 before any multiple-testing
  correction, n = 97. Watch it; do not size it.

What this kills: H1, H2, H3-as-taker, and the reload as a price rule. What it
does not test: the score-conditional model. That still needs live rows, but
the prior is now low: a market this calibrated in aggregate leaves room only
for situation-specific mispricing, which is what the hypotheses layer is for.

## Decision criteria

Run `monitor.py` through the round of 32. Then `settle.py --min-gap 0.05`.

- **Kill** if model Brier on flagged rows is not lower than the market's. The
  edge from score mechanics alone is zero. Stop. Do not build an agent. This
  is the expected outcome and it is a real answer obtained for free.
- **Continue** if model Brier is lower: size it (after-fee expectancy × plausible
  fill rate × realistic capital) and decide whether it clears the attention
  cost. Only then discuss automation, and the automated version is a *maker*
  resting orders at model prices, not a taker chasing gaps.

Standing rules while any of this is live:
- No taker entries between 45¢ and 55¢. (`tradelog.py` warns.)
- Log every discretionary trade before the match resolves. Ten is a sample.
- Run `latency.py` on one match. That number decides whether in-play taking is ever on the table.

## Fees (checked 2026-09-03)

`KXATPMATCH` and `KXWTAMATCH` report `fee_type: quadratic_with_maker_fees`.
The brief's open question is answered against the maker strategy: resting
orders on US Open match markets are **not** free. `feeds.fee()` uses taker
0.07 and maker 0.0175 × contracts × P(1−P), rounded up to the cent. Confirm
the maker rate on the Kalshi fee schedule before sizing strategy 1.

## Known limitations

- ESPN gives no point score within a game; `fair` is computed at 0-0. At a
  break point the truth differs by 5–8 pts. Use `fair.py` by hand there.
- ESPN's game score lags on some courts. Stale score vs live price = fake gap.
  The Brier test absorbs this honestly: those rows drag the model down.
- ESPN marks the server (`possession`) on some courts only.
- Points are i.i.d. No fatigue, injury, wind, momentum. The `update` column is
  where all of that shows up as a number.
- Base serve % is a tour constant; only the differential is fit.
