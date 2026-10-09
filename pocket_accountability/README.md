# Pocket Accountability Map — pipeline (Workstream 1)

Square Yards Surrendered (SYS): every 0.1 s, the QB's pocket (5-yd disk) is split
between the QB and the rushers; space a rusher takes beyond what he held at the snap
is charged to the blocker(s) PFF lists as blocking him (split evenly on doubles).
Full method and integrity rules: docstring of `compute.py`.

## Run

```
pip install -r pocket_accountability/requirements.txt
python pocket_accountability/compute.py --games 2   # quick check
python pocket_accountability/compute.py             # all 122 games (~1 min)
python pocket_accountability/replays.py --stub      # one sack play -> out/replays.json
```

Options for `compute.py`: `--games N`, `--workers N` (default 7), `--radius YD` (default 5),
`--out PATH`.

## Outputs (`pocket_accountability/out/`)

### blocker_plays.csv — one row per blocker per play

| column | meaning |
|---|---|
| gameId, playId, nflId | keys (nflId empty on UNBLOCKED rows) |
| is_unblocked | row holds space taken by rushers nobody blocked |
| is_helper | blocker had no rusher charged to him (no PFF target, or target wasn't a rusher). SYS is 0; exclude from averages |
| team, week | offense team, game week |
| frames | frames in the snap→end window (10 Hz) |
| sys25 | SYS (yd²) at 2.5 s; empty if the play ended sooner |
| sys_end, sys_peak, sys_mean | SYS at end of window / max / mean over window |
| displayName, officialPosition | from players.csv |
| pff_positionLinedUp, pff_blockType, pff_sackAllowed, pff_hitAllowed, pff_hurryAllowed, pff_beatenByDefender | from pffScoutingData.csv |

### drop_report.json
Plays seen / kept and drops by reason (`no_pff, no_qb, no_rushers, no_snap, too_short, missing_frames`).
Full run, R=5: 8,557 plays seen, 8,532 kept; dropped 24 `no_snap`, 1 `no_rushers`, 0 `missing_frames`.

### replays.json — list of plays (this is the format for the front end)

Coordinates are normalised: offense always moves up, line of scrimmage at `up = 0`.
`across` = yards to the offense's right of the ball at the snap, so draw screen-x = across,
screen-y = up (viewed from behind the QB; LT is negative, RT positive).

```jsonc
[{
  "meta": {"gameId": 2021091200, "playId": 4112, "quarter": 4, "down": 4, "yardsToGo": 10,
           "gameClock": "5:45", "possessionTeam": "ATL", "defensiveTeam": "PHI",
           "playDescription": "...", "passResult": "S", "dropBackType": "...",
           "fps": 10, "radius": 5.0, "pocket_area_full": 78.54, "t_std": 2.5,
           "showcase": "sack"},
  "players": [{"nflId": 33084, "side": "QB|BLOCK|RUSH", "name": "Matt Ryan",
               "position": "QB", "jersey": 2, "lined_up": "QB"}],
  "assign": {"<rusherId>": ["<blockerId>", ...] /* or ["UNBLOCKED"] */},
  "helpers": ["<blockerId>"],                 // blockers with no rusher charged
  "pff_allowed": {"<blockerId>": ["sack", "hit", "hurry", "beaten"]},
  "frames": [{
    "t": 0.0,                                 // seconds since snap
    "pos": {"<nflId>": [across, up]},         // QB, blockers, rushers
    "ball": [across, up],
    "sys": {"<blockerId>|UNBLOCKED": 0.0},    // cumulative SYS (yd²) at this frame
    "pocket": 58.75                           // yd² of the disk the QB still controls
  }]
}]
```
All IDs are strings in object keys. `sys` on the last frame equals `sys_end` in the CSV.
