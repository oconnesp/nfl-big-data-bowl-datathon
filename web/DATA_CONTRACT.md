# Data the page reads (`web/public/data/`)

The page fetches three files at runtime. Swap in new files and the page renders them with no code changes. Rebuild the first two with `npm run data` (reads Workstream A's outputs, read-only).

## replays.json (Workstream A format)
Exactly the format in `pocket_accountability/README.md` (`meta`, `players[side QB|BLOCK|RUSH]`, `assign`, `helpers`, `pff_allowed`, `frames[{t, pos, ball, sys, pocket}]`). Coordinates: `[across, up]`, offense moving up, line of scrimmage at `up = 0`.
- The page recomputes ownership and SYS from `pos` (same method). A test checks it against the pipeline's `sys` and `pocket` within 0.5 yd², and it currently matches.
- Optional extras the page understands: `meta.synthetic` (illustrative play), `meta.events` (`[[t, label], …]` slider ticks), `meta.sackBy` (jersey for the sack label).
- `npm run data` writes the pipeline's plays plus the illustrative mockup play.

## leaderboard.json
`{ stub?, provisional?, source?, minSnaps, positionAverages: {T,G,C}, players: [{ nflId, name, team, position: T|G|C, snaps, sys25, sysEnd, positionAvg, percentile (0–100, higher = less space given up), pressureRate?, byWeek?: [{week, snaps, sys25}], worstRep?: {gameId, playId, week, sys25, description} }] }`
`npm run data` maps Workstream A's final `pocket_accountability/out/leaderboard.json` into this shape (`tier` is taken from A). If that file is missing, it falls back to aggregating `blocker_plays.csv`.

## validation.json
`npm run data` computes it from the pipeline outputs: AUC of sys25 vs PFF pressure allowed, odd/even-week stability within position (vs PFF pressure rate), the radius-sensitivity ρ from `sensitivity.json`, and mean sys25 by PFF outcome.

`{ stub?, headlines: [{label, value, unit?, note?}], charts: [{id, title, type: bar|line|scatter, xLabel, yLabel, xTicks?, series: [{name, points: [[x, y], …]}], caption?}] }`
While `stub` is `true`, every tile and chart shows a "Placeholder" label.
