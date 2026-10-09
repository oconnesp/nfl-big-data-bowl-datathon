# Data the page reads (`web/public/data/`)

The page fetches three files at runtime. Swap in new files and the page renders them with no code changes. Rebuild the first two with `npm run data` (reads Workstream A's outputs, read-only).

## replays.json (Workstream A format)
Exactly the format in `pocket_accountability/README.md` (`meta`, `players[side QB|BLOCK|RUSH]`, `assign`, `helpers`, `pff_allowed`, `frames[{t, pos, ball, sys, pocket}]`). Coordinates: `[across, up]`, offense moving up, line of scrimmage at `up = 0`.
- The page recomputes ownership and SYS from `pos` (same method). A test checks it against the pipeline's `sys` and `pocket` within 0.5 yd², and it currently matches.
- Optional extras the page understands: `meta.synthetic` (illustrative play), `meta.events` (`[[t, label], …]` slider ticks), `meta.sackBy` (jersey for the sack label).
- `npm run data` writes the pipeline's plays plus the illustrative mockup play.

## leaderboard.json
`{ stub?, provisional?, source?, minSnaps, positionAverages: {T,G,C}, players: [{ nflId, name, team, position: T|G|C, snaps, sys25, sysEnd, positionAvg, percentile (0–100, higher = less space given up), pressureRate?, byWeek?: [{week, snaps, sys25}], worstRep?: {gameId, playId, week, sys25, description} }] }`
Currently **provisional**: aggregated in `web/` from `pocket_accountability/out/blocker_plays.csv` (non-helper OL rows with sys25). Replace it with Workstream A's `leaderboard.json` when it ships.

## validation.json (Workstream B)
`{ stub?, headlines: [{label, value, unit?, note?}], charts: [{id, title, type: bar|line|scatter, xLabel, yLabel, xTicks?, series: [{name, points: [[x, y], …]}], caption?}] }`
While `stub` is `true`, every tile and chart shows a "Placeholder" label.
