# Pocket Accountability Map — pipeline (Workstream 1)

Square Yards Surrendered (SYS): every 0.1 s, the QB's pocket (5-yd disk) is split
between the QB and the rushers; space a rusher takes beyond what he held at the snap
is charged to the blocker(s) PFF lists as blocking him (split evenly on doubles).
Full method and integrity rules: docstring of `compute.py`.

## Run

```
pip install -r pocket_accountability/requirements.txt
cd pocket_accountability
python run_all.py            # everything: compute -> checks -> leaderboard -> replays -> checks (~1.5 min)
python run_all.py --games 2  # quick smoke run
```

Individual steps:

```
python compute.py [--games N] [--workers 7] [--radius 5] [--out PATH]   # out/blocker_plays.csv, drop_report.json
python checks.py                                                         # out/checks_report.txt (exit 1 on hard fail)
python leaderboard.py                                                    # out/leaderboard.json
python replays.py [--plays gid:pid,...] [--stub]                         # out/replays.json (default: showcase.py picks)
python showcase.py                                                       # print showcase picks and why
python sensitivity.py                                                    # needs out/sens/bp_r4.csv, bp_r6.csv (see below)
```

## Results (full run, R = 5 yd)

- Plays: 8,557 seen, 8,532 kept. Dropped: 24 no snap event, 1 no rushers, 0 missing frames.
- Rows: 48,638 blocker-plays; 3.9% helper rows, 2,712 UNBLOCKED rows.
- Hard checks (`checks_report.txt`): all pass — no negative SYS, no play's total exceeds the disk,
  replay last frames match the CSV.
- Attribution vs PFF (is the PFF-charged blocker the top-SYS blocker on the play?):

  | PFF flag | sys25 | sys_peak | chance | AUC (sys_peak) |
  |---|---|---|---|---|
  | sack allowed | 48.2% | 51.3% | 19.7% | 0.836 |
  | hit allowed | 41.3% | 46.6% | 19.8% | 0.734 |
  | hurry allowed | 44.8% | 42.8% | 21.5% | 0.740 |

  Around 2.5x chance, but **sack attribution is only about 50%**, so SYS disagrees with PFF on
  half of sacks. Some of those are real disagreements (e.g. the `sack_hidden_culprit` replay:
  PFF charged the RG, SYS charges the LT, who was flagged for holding on the play). Some come
  from the method: once bodies overlap at contact, the pocket split degenerates and the charged
  blocker's SYS can fall to 0 on the final frame. **`sys_end` is unreliable on sacks — use
  `sys25` (headline) or `sys_peak`.**
- Radius sensitivity (`sensitivity.json`, 92 qualified linemen): Spearman ρ of per-player mean
  sys25 is 0.990 (R4 vs R5) and 0.992 (R6 vs R5). Per position it's ≥ 0.92, and 80–100% of the
  top/bottom-10 lists stay the same. **R = 5 is kept.** To reproduce:
  `python compute.py --radius 4 --out out/sens/bp_r4.csv` (same for 6), then
  `python sensitivity.py`. `out/sens/` is gitignored.
- Leaderboard: min 150 snaps (92 linemen qualify: T 35, G 36, C 21). Position averages of
  sys25: T 7.37, G 1.84, C 1.10 yd². Tackles face edge rushers in open space, so **compare only
  within a position**. Percentiles and tiers are computed within the slot the player actually
  lined up at (PFF), not his roster label: e.g. Olisaemeka Udoh is listed as a T but played RG
  on every snap, so he's ranked with the guards.

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


### leaderboard.json — offensive line, ranked within position

```jsonc
{
  "generated_at": "ISO time", "radius": 5.0, "metric": "sys25",
  "min_snaps": 150, "min_snaps_reason": "...", "percentile_note": "100 = best (lowest sys25)",
  "position_averages": {"T": 7.374, "G": 1.84, "C": 1.101},
  "players": [{
    "nflId": 42445, "name": "Daryl Williams", "team": "BUF",
    "position": "T",                 // slot he lined up at most (LT/RT->T, LG/RG->G, C)
    "official_position": "T", "lined_up": {"RT": 181},
    "snaps": 181,                    // qualified pass-pro snaps lasting >= 2.5 s
    "sys25_mean": 5.383, "sys_peak_mean": 0.0, "sys_end_mean": 0.0,
    "pos_avg": 7.374, "vs_avg": -1.99,
    "percentile": 100.0, "tier": "Wall|Average|Leaky",   // terciles within position
    "weekly": {"1": 4.2},            // week -> mean sys25
    "pressures_allowed": 12, "pressure_rate": 0.066,    // PFF sack+hit+hurry allowed
    "worst_rep": {"gameId": 0, "playId": 0, "sys25": 22.0}   // feed to replays.py --plays
  }]
}
```

### Showcase replays (default `replays.py` picks, from `showcase.py`)

| tag | play | why |
|---|---|---|
| sack_culprit_confirmed | 2021101007:2849 | Brady sack; PFF-charged TE O.J. Howard peak 33.2 yd² vs next 2.1 |
| sack_hidden_culprit | 2021091201:4103 | Allen sack by T.J. Watt; PFF charged RG Ford (1.4), SYS says LT Dawkins (30.8), who was flagged for holding |
| clean_pocket | 2021091204:1641 | Goff, 4.7 s, 0 yd² surrendered at 2.5 s |
| stunt | 2021091300:4765 | Lamar Jackson sack/fumble; switch block (SW) by RT Villanueva |
| unblocked | 2021101703:2962 | Rodgers sack; UNBLOCKED rusher took 50.4 yd² |
