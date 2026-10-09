# Threat Load: pressure received per offensive lineman

The question this answers is how hard each lineman's job was on a play, given how the defense lined up at the snap. It measures pressure *received*. The Pocket Accountability Map's SYS measures pressure *allowed*. The two together give **Pressure Over Expected (POE)**.

## Method

For each play, take everyone's position at the snap frame. Positions are normalised so the offense attacks +x, with the ball at (0, 0). Then for lineman *i*:

**Threat_i = Σ_d P(rush_d) × w_di × q_d**

| Term | What it is | How it's estimated |
|---|---|---|
| P(rush_d) | Chance defender *d* rushes | Gradient-boosted classifier using alignment only: depth, lateral offset, how far outside the tackle he is, distance to the nearest lineman, which way he's facing, speed at the snap, number of men in the box, official position, down and distance. Target: PFF `pff_role == "Pass Rush"`. Predictions are leave-one-week-out. |
| w_di | Share of defender *d* that falls on lineman *i* | Gaussian on lateral distance to each of the 5 linemen, normalised. σ = 1.5 yd, chosen by maximum likelihood against PFF's actual blocker. |
| q_d | Rusher quality (1.0 = league average) | Pressure rate per rush (hit, hurry or sack), leave-one-week-out, shrunk toward the mean with a beta-binomial prior (μ = 0.116, κ = 86, method of moments). |

**xP (expected pressure)** is a gradient-boosted model of P(lineman allows a hit, hurry or sack). It uses only things outside the lineman's control: his threat, the expected rushers on him, total expected rushers, the threat on his teammates, TE/RB help on his side, tackle/guard/center, down, distance, dropback type and play action. Predictions are leave-one-week-out.

**POE per 100 snaps** = 100 × (actual pressures − expected pressures) / snaps. **Negative is good.**

## Results (2021 weeks 1–8, 42,655 lineman-plays, pressure-allowed rate 6.2%)

- **P(rush) from alignment:** AUC 0.988. That's easy, because linemen almost always rush and DBs almost never do. The expected rusher count per play correlates 0.44 with the actual count, because blitzes and drops are the hard part.
- **The assignment matches PFF:** the lineman with the most weight is PFF's actual blocker 74% of the time.
- **Threat Load predicts pressure, but weakly and steadily:**

  | Threat quintile | Q1 (lightest) | Q2 | Q3 | Q4 | Q5 (heaviest) |
  |---|---|---|---|---|---|
  | Pressure allowed | 4.3% | 5.6% | 6.2% | 7.0% | 8.1% |

  The heaviest fifth of assignments allows pressure about 1.9 times as often as the lightest. AUC is 0.57 overall and 0.51–0.56 within position.
- **xP:** AUC 0.642, against 0.628 for position plus situation alone. It's well calibrated across deciles.
- **Stability between odd and even weeks (164 linemen):** raw pressure rate r = 0.34, POE r = 0.23. The adjustment makes comparisons fairer but **not** more stable.
- **The load a lineman faces is mostly play-to-play noise, not a trait:** within position, the odd-week and even-week averages correlate at only 0.12–0.23. That is exactly the variance worth adjusting out.
- **Realized load** reruns the same formula with actual rushers in place of P(rush). It only reaches AUC 0.585, and correlates 0.86 with the snap version. Alignment captures most of what the eventual rush tells you.

## Files

- `build.py`: snap features, P(rush), q_d, σ fit, Threat Load. Writes `out/ol_plays.csv` and `out/defenders_snap.csv`.
- `evaluate.py`: validation, xP, POE, stability. Writes `out/ol_plays_scored.csv` and `out/ol_leaderboard.csv`.
- `work/extract.py`: pulls the snap frame out of the 122 tracking files and writes `work/snap.csv`.
- `out/ol_leaderboard.csv`: one row per lineman. Rows with `qualified_150 = True` (150+ snaps) come first, sorted by POE.
- `out/ol_plays_scored.csv`: one row per lineman per play, with threat, expected rushers, help, xP and the actual outcome. Join it to SYS on gameId, playId and nflId.

Run: `python work/extract.py`, then `python build.py <repo root> out`, then `python evaluate.py out`. The whole run takes under a minute and needs pandas, numpy and scikit-learn.

## Caveats

- The pressure label comes from PFF's charting, and so does the blocker assignment used to fit σ.
- Tracking at the snap doesn't show pre-snap motion or a late creep up to the line.
- 8 weeks is a small sample. Use the 150+ snap filter.
- Tackles face roughly 2–3 times the threat of interior linemen. Compare threat percentiles within position (`threat_pct`), not across positions.
