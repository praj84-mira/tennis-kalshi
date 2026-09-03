# usopen-fairvalue

A read-only fair-value monitor for live US Open singles markets on Kalshi.
It exists to answer one question before any money or automation goes in:

> Does a score-only Markov model beat the Kalshi mid on Brier score, on the
> rows where they disagree?

If no: there is no edge from score mechanics and the trading app should not
be built. If yes: size it, then decide. **There is no order code in this
package, by design.** See `PROJECT_BRIEF.md` for the reasoning.

## Run

```
python3 monitor.py              # every 30s, appends data/monitor.csv; leave it running
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
