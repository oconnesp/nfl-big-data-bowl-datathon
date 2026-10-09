# Requirements Document

## Introduction

The Pocket Accountability Map is the Workstream C (Visualisation & Pitch) deliverable for an NFL Big Data Bowl 2023 hackathon entry (2021 season, weeks 1–8, dropback passes only). The page presents a new position-specific offensive-line metric, Square Yards Surrendered (SYS), to three audiences: coaches, scouts and broadcasters.

SYS definition (shared with Workstreams A and B): every 0.1 s, the pocket is sampled as a 5-yard-radius disk around the QB on a 0.25-yard grid. A grid point is lost when a pass rusher is closer to the point than the QB, and the point belongs to the nearest such rusher. Each rusher's area at the snap is subtracted (clipped at 0). The remaining area is charged to the rusher's blocker(s) according to PFF assignments, split evenly across double teams; rushers with no blocker are charged to UNBLOCKED. Headline value: SYS at 2.5 s (sys25); secondary values: sys_end, sys_peak, sys_mean.

This workstream ports an existing static HTML/canvas mockup (the "Pocket Blame Map") into a lightweight framework producing a static, Vercel-ready build, renames the product to "Pocket Accountability Map", replaces hard-coded keyframes with runtime-loaded per-frame data, and adds a play picker, a data-driven leaderboard with player panels, a validation section, three audience angles and a 2-minute demo script. Workstreams A (data pipeline) and B (validation) are out of scope except for the data contracts defined in Requirements 2–4, which Workstream A and B outputs must match.

## Glossary

- **Viz_App**: The Workstream C static web application (the Pocket Accountability Map) located in the top-level `web/` folder.
- **Mockup**: The user-supplied single-page HTML/vanilla JS/canvas prototype titled "Pocket Blame Map", preserved for reference at `web/reference/mockup.html`.
- **Data_Loader**: The Viz_App module that fetches and validates `replays.json`, `leaderboard.json` and `validation.json` at runtime.
- **Schema_Validator**: The Viz_App module that checks a parsed data file against the Data_Contract and returns either a typed value or a list of validation errors.
- **Data_Contract**: The JSON shapes for `replays.json`, `leaderboard.json` and `validation.json` defined in Requirements 2, 3 and 4.
- **Stub_Data**: Placeholder data files shipped inside `web/` until Workstreams A and B deliver real files; each Stub_Data file carries `"stub": true`.
- **Stub_Generator**: The script in `web/scripts/` that produces the stub `replays.json` by sampling the Mockup's keyframed play at 0.1 s intervals.
- **SYS_Engine**: The Viz_App module that computes per-frame pocket state and per-blocker SYS from frame positions (the ported `state()` and `blame()` semantics of the Mockup).
- **Replay**: One play record in `replays.json`.
- **Frame**: One time sample of a Replay, at a multiple of 0.1 s after the snap, holding the position of every listed player.
- **Snap_Frame**: The Frame with `t = 0`.
- **Pocket_Disk**: The set of Grid_Points within radius R = 5 yd of the QB position in a Frame (Grid_Point offset `(i·0.25, j·0.25)` from the QB with `(i·0.25)² + (j·0.25)² ≤ 25`).
- **Grid_Point**: One sample point of the Pocket_Disk; each Grid_Point represents a Cell_Area of 0.0625 yd².
- **Full_Pocket**: The nominal pocket area πR² ≈ 78.54 yd².
- **Lost_Point**: A Grid_Point for which at least one rusher's Euclidean distance is strictly less than the QB's distance; the Owner of a Lost_Point is the nearest rusher (ties broken by the rusher's order in the Replay `players` list).
- **Rusher_Area**: For one rusher in one Frame, the count of Lost_Points owned by that rusher multiplied by Cell_Area.
- **Charged_Area**: For one rusher in one Frame, `max(0, Rusher_Area(frame) − Rusher_Area(Snap_Frame))`.
- **Blocker_SYS**: For one blocker in one Frame, the sum over rushers assigned to that blocker of Charged_Area divided by the number of blockers assigned to that rusher.
- **UNBLOCKED**: The accountability bucket that receives the Charged_Area of every rusher whose assignment list is empty or absent.
- **Pocket_Remaining**: For one Frame, Full_Pocket area sampled (Grid_Point count × Cell_Area) minus the area of all Lost_Points.
- **sys25**: Blocker_SYS at the Frame with `t = 2.5`, or at the last Frame when the Replay ends before 2.5 s.
- **sys_end / sys_peak / sys_mean**: Blocker_SYS at the last Frame / maximum over all Frames / mean over all Frames.
- **Field_View**: The canvas rendering of a Replay (VIEW x −12..12, y 3..−11, line of scrimmage at y = 0, aspect 24/14).
- **Rail**: The 320 px side panel next to the Field_View holding the Pocket_Remaining hero number, the Sparkline and the SYS_Bars.
- **Sparkline**: The SVG chart of Pocket_Remaining over time with a cursor at the current time.
- **SYS_Bars**: The per-blocker horizontal bars in the Rail showing Blocker_SYS at the current time.
- **Playback_Controls**: The Play/Pause/Replay button, the time Slider, event tick labels and the clock.
- **Slider**: The range input that selects the current Frame in 0.1 s steps.
- **Tooltip**: The hover/focus readout for a Grid_Point on the Field_View.
- **Play_Picker**: The dropdown control listing all Replays in `replays.json`.
- **Leaderboard**: The season table driven by `leaderboard.json`.
- **Player_Panel**: The per-player detail view opened from the Leaderboard.
- **Validation_Section**: The "Does it work?" page section driven by `validation.json`.
- **Broadcast_Mode**: The Field_View overlay mode that emphasises the shrinking pocket for a TV audience.
- **Audience_Angles**: The three page sections addressed to Coach, Scout and Broadcaster.
- **Blocker_Palette**: The mapping from blocker slot to colour token (`--b-lt`, `--b-lg`, `--b-c`, `--b-rg`, `--b-rt` plus extension tokens for additional blockers and UNBLOCKED).
- **Tier**: Leaderboard label derived from `d = sys25 − position average`: "Wall" when d < −1, "Leaky" when d > 1.5, otherwise "Average".
- **Demo_Script**: The 2-minute spoken walkthrough in Markdown.
- **Working_Branch**: The git branch `feat/viz-pitch`.
- **Valid_Blocker**: An `nflId` in a rusher's assignment list that references a `players` entry with role "Pass Block" in the same Replay.
- **Extension_Tokens**: The four additional Blocker_Palette colour tokens (`--b-x1` to `--b-x4`) assigned, in `players` order, to blockers beyond the five slot tokens; plus `--b-unblocked` for UNBLOCKED.
- **Leading_Blocker**: For one Frame, the blocker (or UNBLOCKED) with the largest Blocker_SYS; ties are broken by earliest position in `players` order, with UNBLOCKED last. The Leading_Blocker's bar in the SYS_Bars is the leading bar.
- **Current_Time**: The single shared state holding the selected Replay, the current Frame index and the playback state (playing or paused).
- **Selected_Grid_Point**: The Grid_Point chosen by keyboard navigation on the Field_View for the Tooltip.
- **Live_Region**: The polite ARIA live region that announces the Field_View summary to assistive technologies.
- **Mockup_Tag**: The "Mockup" label in the page header indicating that stub data is displayed.
- **Displayed_Rows**: The Leaderboard rows visible after the active position chip and search filters are applied.
- **Shared_Branch**: Any remote branch other than the Working_Branch.
- **Path_Check**: The command `git diff --name-only origin/main...feat/viz-pitch`, whose output lists the paths changed by Workstream C.

## Requirements

### Requirement 1: Framework port with preserved visual design

**User Story:** As the Workstream C developer, I want the Mockup ported to a lightweight framework with a static build, so that the page is maintainable, testable and deployable on Vercel without losing the agreed design.

#### Acceptance Criteria

1. WHEN `npm run build` is executed in `web/` and no TypeScript or Vite errors occur, THE Viz_App build SHALL exit with code 0 and write the static build to `web/dist/`.
2. IF a TypeScript or Vite error occurs during `npm run build`, THEN THE Viz_App build SHALL exit with a non-zero code.
3. THE Viz_App build output in `web/dist/` SHALL contain only HTML, CSS, JS, font, image and JSON files.
4. WHEN the contents of `web/dist/` are served from the root of any static host, THE Viz_App SHALL load with zero failed asset requests and zero uncaught console errors.
5. THE Viz_App SHALL define the CSS custom properties `--bg`, `--panel`, `--fg`, `--fg-2`, `--muted`, `--line`, `--accent`, `--chip`, `--b-lt` (#2a78d6), `--b-lg` (#eb6834), `--b-c` (#1baf7a), `--b-rg` (#c98500), `--b-rt` (#d55181), `--bad` and `--good` on `:root` with values identical to the Mockup.
6. THE Viz_App SHALL render the h1, the eyebrow and section headings in Saira Semi Condensed, body text in IBM Plex Sans, and the clock, hero number, SYS values and Leaderboard numbers in IBM Plex Mono.
7. IF a web font fails to load, THEN THE Viz_App SHALL render the affected text in a generic font family of the same class (sans-serif or monospace).
8. THE Viz_App SHALL render, in order, the header (eyebrow "Offensive line · pass protection", h1, lede), the stage (Field_View and Rail), the legend, the Leaderboard and the method section with the step titles "Draw the pocket", "Find who took it" and "Charge the blocker" in that order.
9. WHILE the viewport width is 900 px or greater, THE Viz_App SHALL display the Field_View and the 320 px Rail side by side.
10. WHILE the viewport width is below 900 px, THE Viz_App SHALL stack the Rail below the Field_View.
11. THE Viz_App SHALL render the Field_View inside a field box of colour #11151b with VIEW x −12..12, y 3..−11, aspect ratio 24/14 at all viewport widths and the line of scrimmage drawn and labelled at y = 0.
12. THE Viz_App SHALL keep `web/reference/mockup.html` byte-identical to the user-supplied Mockup.

### Requirement 2: Replay data contract (`replays.json`)

**User Story:** As the Workstream A developer, I want a precise contract for `replays.json`, so that I can produce a file the Viz_App accepts without code changes.

#### Acceptance Criteria

1. THE Data_Contract SHALL define `replays.json` as a JSON array of 1 to 500 Replay objects, each with a unique (`gameId`, `playId`) pair.
2. THE Data_Contract SHALL require each Replay to contain `gameId` (integer), `playId` (integer), `situation` (non-empty string of at most 80 characters), `pffOutcome` (one of "Sack", "Hurry", "Hit", "Clean"), `events`, `players`, `assignments` and `frames`.
3. THE Data_Contract SHALL define `events` as an array of 0 to 20 entries `{t: number, label: string}` with `label` of at most 24 characters and `t` within [0, last Frame `t`].
4. THE Data_Contract SHALL require each `players` entry to contain `nflId` (integer, unique within the Replay), `name` (string of at most 40 characters), `jersey` (integer 0–99), `position` (string) and `role` (one of "QB", "Pass Block", "Pass Rush"), with an optional `slot` string holding the PFF `pff_positionLinedUp` value.
5. THE Data_Contract SHALL require each Replay to contain 2 to 22 `players` entries with exactly 1 "QB", at least 1 "Pass Rush" and at most 11 "Pass Block" entries.
6. THE Data_Contract SHALL define `assignments` as an object whose keys are rusher `nflId` strings and whose values are arrays of 0 to 3 distinct "Pass Block" `nflId` integers, where an empty or absent array means UNBLOCKED.
7. THE Data_Contract SHALL define `frames` as an array of 1 to 151 Frames `{t: number, positions: {<nflId string>: [x, y]}}`, with the first Frame at `t = 0`, `t` strictly increasing in steps of 0.1 s (tolerance ±0.001 s), the last `t` at most 15.0, and a finite `[x, y]` pair for every listed player in every Frame.
8. THE Data_Contract SHALL define positions in yards, normalised so that the offense moves toward positive y, the line of scrimmage is at y = 0 and x = 0 is the ball position at the snap.
9. WHERE a Replay contains the optional `sys` object, THE Data_Contract SHALL require keys that are "Pass Block" `nflId` strings or "UNBLOCKED", each with non-negative numeric `sys25`, `sys_end`, `sys_peak` and `sys_mean`, where `sys_peak ≥ sys_end` and `sys_peak ≥ sys_mean`.
10. THE Data_Contract SHALL define the optional Replay `stub` boolean as `true` in Stub_Data and absent or `false` in Workstream A output.
11. THE Data_Contract SHALL be documented in `web/DATA_CONTRACT.md` with a minimal example of each file from Requirements 2, 3 and 4, and each example SHALL pass the Schema_Validator with zero errors.
12. IF `replays.json` violates any rule of this Requirement, THEN THE Schema_Validator SHALL return one error per violation stating the Replay index, the field and the rule, and SHALL return no typed value.
13. WHEN `replays.json` satisfies every rule of this Requirement, THE Schema_Validator SHALL return the typed Replay array in file order.

### Requirement 3: Leaderboard data contract (`leaderboard.json`)

**User Story:** As the Workstream A developer, I want a precise contract for `leaderboard.json`, so that season aggregates drop into the Viz_App without code changes.

#### Acceptance Criteria

1. THE Data_Contract SHALL define `leaderboard.json` as an object with optional `stub` (boolean, treated as `false` when absent), `minSnaps` (integer 1–1000, default 150), `positionAverages` (object with exactly the keys "T", "G" and "C", each a number ≥ 0) and `players` (array of 0 to 500 entries).
2. THE Data_Contract SHALL require each `players` entry to contain `nflId` (integer > 0, unique), `name` (string of 1–64 characters), `team` (2–3 uppercase letters), `position` (one of "T", "G", "C"), `snaps` (integer ≥ `minSnaps`), `sys25` (number ≥ 0), `sysEnd` (number ≥ 0), `positionAvg` (number equal to `positionAverages[position]` within ±0.001) and `percentile` (number 0–100, where higher means fewer square yards surrendered).
3. WHERE a `players` entry contains `byWeek`, THE Data_Contract SHALL require 0 to 8 entries `{week, snaps, sys25}` with unique integer `week` values 1–8, integer `snaps` ≥ 0 and `sys25` ≥ 0.
4. WHERE a `players` entry contains `worstRep`, THE Data_Contract SHALL require `gameId` (integer > 0), `playId` (integer > 0), `week` (integer 1–8), `sys25` (number ≥ 0) and `description` (string of 1–200 characters).
5. IF `leaderboard.json` violates any rule of this Requirement, THEN THE Schema_Validator SHALL return one error per violation with its field path and SHALL return no typed value.
6. IF `leaderboard.json` fails validation, THEN THE Viz_App SHALL show an error state in place of the Leaderboard and keep all other sections functional.
7. WHEN a valid `leaderboard.json` has an empty `players` array, THE Leaderboard SHALL show zero rows and the message "No players met the minimum snap count".

### Requirement 4: Validation data contract (`validation.json`)

**User Story:** As the Workstream B developer, I want a precise contract for `validation.json`, so that my headline numbers and charts render on the page without code changes.

#### Acceptance Criteria

1. THE Data_Contract SHALL define `validation.json` as an object with optional `stub` (boolean), `headlines` (array of 3 to 4 entries) and `charts` (array of exactly 2 entries).
2. WHEN `validation.json` contains top-level fields beyond `stub`, `headlines` and `charts`, THE Schema_Validator SHALL ignore those fields.
3. THE Data_Contract SHALL require each `headlines` entry to contain `label` (string of 1–60 characters) and `value` (finite number or string of 1–20 characters), with optional `unit` (string of 1–20 characters) and optional `note` (string of 1–200 characters).
4. THE Data_Contract SHALL require each `charts` entry to contain `id` (string of 1–40 characters, unique), `title` (string of 1–100 characters), `type` (one of "bar", "line", "scatter"), `xLabel` and `yLabel` (strings of 1–60 characters), `series` (array of 1–6 entries `{name, points}` with `name` of 1–40 characters and `points` an array of 0–500 finite `[x, y]` pairs) and optional `caption` (string of 1–300 characters).
5. IF `validation.json` violates any rule of this Requirement, THEN THE Schema_Validator SHALL return one error per violation with its location and SHALL return no typed value.
6. IF `validation.json` fails to load, parse or validate, THEN THE Viz_App SHALL show the error state in the Validation_Section only.
7. WHILE `validation.json` has `stub` set to `true`, THE Validation_Section SHALL display the placeholder label defined in Requirement 15.

### Requirement 5: Runtime data loading and validation

**User Story:** As a viewer, I want the page to tell me clearly when data is missing or broken, so that I never see a blank or misleading visualisation.

#### Acceptance Criteria

1. WHEN the Viz_App starts, THE Data_Loader SHALL issue exactly one request each, in parallel, for `data/replays.json`, `data/leaderboard.json` and `data/validation.json` relative to the site root.
2. THE Viz_App SHALL render content from a data file only after the Schema_Validator returns zero errors for that file.
3. IF a data file request fails with a network error, returns a non-2xx status or exceeds a 10 s timeout, THEN THE Viz_App SHALL replace the loading indicator of the affected sections with an error state naming the file and stating that the file could not be loaded.
4. IF a data file is not valid JSON or fails Schema_Validator checks, THEN THE Viz_App SHALL show, in the affected sections only, an error state naming the file, listing the first 5 errors with their JSON paths and stating the count of remaining errors, and SHALL render no partial content from that file.
5. THE Viz_App SHALL map `replays.json` to the Field_View, Rail, Playback_Controls and Play_Picker, `leaderboard.json` to the Leaderboard and Player_Panel, and `validation.json` to the Validation_Section.
6. WHILE one data file is in an error state, THE Viz_App SHALL keep the sections mapped to the other valid data files fully interactive.
7. IF a Replay references in `assignments` or `positions` an `nflId` absent from its `players` list, THEN THE Schema_Validator SHALL report the Replay index and the unknown `nflId`.
8. IF a Frame lacks a position for a player listed in `players`, THEN THE Schema_Validator SHALL report the Replay index, the Frame `t` and the missing `nflId`.
9. WHILE a data file request is pending, THE Viz_App SHALL show a loading indicator in each affected section, and WHEN the request settles, THE Viz_App SHALL remove that indicator.
10. WHEN conforming real data files from Workstreams A and B replace the files in `web/public/data/`, THE Viz_App SHALL render the real data with no source code changes, whether `stub` is `false` or absent.

### Requirement 6: Stub data

**User Story:** As the Workstream C developer, I want stub data that matches the contract, so that I can build and demo the page before Workstream A delivers.

#### Acceptance Criteria

1. WHEN the Stub_Generator runs, THE Stub_Generator SHALL write to `web/public/data/replays.json` a Mockup Replay of exactly 37 Frames at `t` = 0.0, 0.1, …, 3.6 (rounded to 1 decimal), sampled from the Mockup's OL, DL and QB keyframes with the Mockup's smoothstep interpolation.
2. THE Stub_Generator SHALL carry the Mockup events (Snap 0.0 s, RT beaten 1.6 s, Pressure 2.8 s, Sack 3.6 s), the Mockup jersey numbers and the Mockup blocker assignments into the Mockup Replay, using unique synthetic `nflId` values and placeholder names.
3. THE Stub_Generator SHALL include at least one additional synthetic Replay lasting at least 2.5 s with at least 6 blockers (including a TE or RB) and at least one rusher with an empty assignment list.
4. THE Viz_App SHALL ship a placeholder `web/public/data/leaderboard.json` with at least 12 players and at least 3 players each at positions T, G and C.
5. THE Viz_App SHALL ship a placeholder `web/public/data/validation.json` with exactly 3 headlines and 2 charts.
6. THE Stub_Data files `replays.json`, `leaderboard.json` and `validation.json` SHALL each set top-level `"stub": true`.
7. WHEN the Mockup Replay is loaded, THE SYS_Engine SHALL produce at `t = 3.6` an RT Blocker_SYS of 27.99–34.21 yd², an LG Blocker_SYS of 6.66–8.14 yd² and a Pocket_Remaining of 18.9–23.1 yd², and a Snap_Frame Pocket_Remaining of 56.7–69.3 yd².
8. THE Schema_Validator SHALL return zero errors for every Stub_Data file.
9. WHEN the Stub_Generator runs twice on the same input, THE Stub_Generator SHALL write byte-identical output.
10. IF the generated output fails Schema_Validator checks, THEN THE Stub_Generator SHALL exit with a non-zero code, report the errors and leave the existing `replays.json` unchanged.

### Requirement 7: SYS computation

**User Story:** As a coach, I want the replay numbers computed with the same rules as the season metric, so that what I see on a play is consistent with the leaderboard.

#### Acceptance Criteria

1. WHEN a Replay is selected, THE SYS_Engine SHALL compute, for every Frame in ascending `t`, the Lost_Points with exactly one Owner each, each rusher's Rusher_Area and Charged_Area, Pocket_Remaining and each blocker's Blocker_SYS including UNBLOCKED, all in yd².
2. THE SYS_Engine SHALL centre the Pocket_Disk on the QB position of each Frame with radius 5 yd and grid spacing 0.25 yd, giving an identical Grid_Point count in every Frame.
3. THE SYS_Engine SHALL use each rusher's Snap_Frame Rusher_Area as that rusher's baseline, clip Charged_Area at 0, and produce a Charged_Area of 0 for every rusher at the Snap_Frame.
4. WHEN a rusher has N ≥ 2 Valid_Blockers, THE SYS_Engine SHALL credit Charged_Area divided by N to each of the N Valid_Blockers, where N counts only Valid_Blockers.
5. WHEN a rusher's assignment list is empty, absent or contains no Valid_Blocker, THE SYS_Engine SHALL credit the full Charged_Area of that rusher to UNBLOCKED.
6. THE SYS_Engine SHALL satisfy, for every Frame, the invariant that the sum of Blocker_SYS over all blockers plus UNBLOCKED equals the sum of Charged_Area over all rushers within 1e-9 yd².
7. THE SYS_Engine SHALL satisfy, for every Frame, the invariants 0 ≤ Pocket_Remaining ≤ Grid_Point count × Cell_Area and Blocker_SYS ≥ 0.
8. THE SYS_Engine SHALL report unrounded sys25, sys_end, sys_peak and sys_mean (mean including the Snap_Frame) for every blocker and for UNBLOCKED, reporting 0 for a blocker with no assigned rusher.
9. WHERE a Replay contains the optional `sys` object, THE SYS_Engine SHALL match each provided `sys25` value within ±0.5 yd² inclusive, and the automated test suite SHALL report the Replay, blocker and difference of every mismatch.
10. WHEN a Replay with up to 80 Frames and up to 7 rushers is selected, THE SYS_Engine SHALL complete the per-Frame timeline within 300 ms, excluding fetch time, on a 2020-or-newer laptop browser.
11. WHEN the SYS_Engine runs twice on identical input, THE SYS_Engine SHALL return exactly equal results.
12. IF a Replay lacks a Snap_Frame or contains a non-finite position, THEN THE SYS_Engine SHALL return an error naming the Replay and the first offending `t`, return no partial results and leave the previous results displayed.
13. WHEN a Replay has zero rushers, THE SYS_Engine SHALL return an empty Lost_Point set, Pocket_Remaining equal to Grid_Point count × Cell_Area and zero for every Blocker_SYS.

### Requirement 8: Replay rendering

**User Story:** As a coach, I want to watch the pocket shrink with each lost yard coloured by the responsible blocker, so that I can see who gave up ground and when.

#### Acceptance Criteria

1. WHEN the Current_Time changes, THE Field_View SHALL redraw within one animation frame using only the SYS_Engine result of the current Frame.
2. WHEN the Field_View redraws, THE Field_View SHALL draw the field background, yard lines, the labelled line of scrimmage, the Pocket_Disk Grid_Points, the dashed 5 yd pocket circle, rusher trails for `t` ≤ current `t`, dotted assignment lines from each blocker to each assigned rusher, and player discs for blockers, rushers and the QB.
3. THE Field_View SHALL fill clean Grid_Points with the light clean colour and every Lost_Point, including Lost_Points at the Snap_Frame, according to the charge of its Owner.
4. WHEN a Lost_Point's Owner has exactly one Valid_Blocker, THE Field_View SHALL fill the Lost_Point with that blocker's Blocker_Palette colour at 0.62 alpha.
5. WHEN a Lost_Point's Owner has 2 or more Valid_Blockers, THE Field_View SHALL fill the Lost_Point with a checkerboard containing every assigned blocker's colour at 0.62 alpha.
6. WHEN a Lost_Point's Owner is charged to UNBLOCKED, THE Field_View SHALL fill the Lost_Point with the UNBLOCKED colour and a diagonal hatch pattern.
7. THE Field_View SHALL label each blocker disc with its `slot`, or with its `position` when `slot` is absent, and SHALL label each rusher disc with the jersey number on a dark fill with a red stroke.
8. WHILE the current `t` is at or after the `t` of an event whose label begins with "Sack", THE Field_View SHALL display "SACK · #<jersey>" when the event label contains the jersey of a listed rusher, or "SACK" otherwise.
9. WHILE the current `t` is before the `t` of every event whose label begins with "Sack", THE Field_View SHALL hide the sack label.
10. THE Viz_App SHALL assign each blocker in a Replay a distinct Blocker_Palette colour, using `--b-lt`, `--b-lg`, `--b-c`, `--b-rg`, `--b-rt` for slots LT, LG, C, RG, RT and the Extension_Tokens in `players` order for up to 4 additional blockers.
11. THE Viz_App SHALL render Replays with 5 to 9 blockers and 3 to 8 rushers.
12. IF a selected Replay has fewer than 5 or more than 9 blockers, or fewer than 3 or more than 8 rushers, THEN THE Viz_App SHALL show an error naming the Replay and the out-of-range count and keep the previous Replay displayed.
13. WHEN the Field_View container is resized, THE Field_View SHALL redraw within 100 ms at CSS size × device pixel ratio with the 24/14 aspect ratio preserved within ±1 px.
14. WHEN a player position lies outside VIEW, THE Field_View SHALL clip that player at the VIEW boundary without rescaling VIEW.

### Requirement 9: Rail readouts

**User Story:** As a viewer, I want live numbers next to the replay, so that I can read the pocket size and each blocker's surrendered area at any moment.

#### Acceptance Criteria

1. WHEN the Current_Time changes, THE Rail SHALL display the current Frame's Pocket_Remaining in yd² to 1 decimal as the hero number, in the same update as the Field_View redraw.
2. THE Rail SHALL caption the hero number "P% of the N yd² pocket at the snap", where N is the Snap_Frame Pocket_Remaining rounded to an integer and P is the current Pocket_Remaining as a rounded percentage of the Snap_Frame Pocket_Remaining, with P = 0 when the Snap_Frame Pocket_Remaining is 0.
3. THE Sparkline SHALL plot Pocket_Remaining over all Frames on an x-axis from `t = 0` to the last Frame `t`, and WHEN the Current_Time changes, THE Sparkline SHALL move its cursor to the current `t`.
4. THE SYS_Bars SHALL show one bar per blocker in `players` order, followed by an UNBLOCKED bar only when at least one rusher is charged to UNBLOCKED.
5. THE SYS_Bars SHALL scale every bar to the maximum Blocker_SYS over all Frames and all bars including UNBLOCKED, and display each value in yd² equal to the SYS_Engine value for the current Frame rounded to 1 decimal.
6. WHILE the Leading_Blocker's Blocker_SYS exceeds 2.0 yd², THE SYS_Bars SHALL show the leading bar in `--bad` with the visible text label "most surrendered".
7. WHILE the Leading_Blocker's Blocker_SYS is at most 2.0 yd², THE SYS_Bars SHALL show no highlight and no "most surrendered" label.
8. WHEN the maximum Blocker_SYS over all Frames is 0, THE SYS_Bars SHALL show zero-length bars labelled "0.0" without error.

### Requirement 10: Playback controls

**User Story:** As a viewer, I want to play, pause and scrub through the play, so that I can study any moment.

#### Acceptance Criteria

1. WHEN the user activates the Play button while the current Frame is not the last Frame, THE Viz_App SHALL label the button "Pause" and advance the Current_Time at 0.75× real time (one 0.1 s Frame per 133 ± 10 ms on average).
2. WHEN playback reaches the last Frame, THE Viz_App SHALL stop on the last Frame and label the button "Replay".
3. WHEN the user activates the Pause button, THE Viz_App SHALL stop on the current Frame, label the button "Play" and leave the Slider and clock unchanged.
4. WHEN the user activates the Replay button, THE Viz_App SHALL reset the Current_Time to `t = 0`, label the button "Pause" and start playback.
5. WHEN the user moves the Slider, THE Viz_App SHALL set the current Frame to the Slider value, pause playback and label the button "Play", or "Replay" when the selected Frame is the last Frame.
6. THE Slider SHALL range from 0 to the last Frame `t` in 0.1 s steps and accept mouse, touch and keyboard input, with arrow keys stepping one Frame and Home/End jumping to the first/last Frame.
7. THE Playback_Controls SHALL display one tick per Replay event, positioned at the event `t` and labelled with the event label.
8. THE Playback_Controls SHALL display a clock showing the current `t` to exactly 1 decimal followed by " s" (e.g. "2.5 s").
9. THE Play/Pause/Replay button SHALL be focusable, operable with Enter and Space, and expose an accessible name equal to its visible label.
10. THE Field_View, Rail, Slider, clock and Tooltip SHALL read the current Frame from the single Current_Time state.
11. WHEN the selected Replay changes, THE Viz_App SHALL stop playback, reset the Current_Time to `t = 0`, reset the Slider maximum and event ticks to the new Replay and label the button "Play".

### Requirement 11: Grid point tooltip

**User Story:** As a coach, I want to point at any spot in the pocket and see who took it, so that I can attribute lost ground precisely.

#### Acceptance Criteria

1. WHEN the pointer moves over the Pocket_Disk, THE Tooltip SHALL update within 100 ms for the Grid_Point nearest the pointer.
2. WHEN the Tooltip targets a clean Grid_Point, THE Tooltip SHALL display "Clean pocket" and "QB reaches this spot first".
3. WHEN the Tooltip targets a Lost_Point whose Owner has Valid_Blockers, THE Tooltip SHALL display "Lost to #<jersey> (<position>)" and "Charged to <slot>", appending "+ <slot>" for each additional Valid_Blocker in assignment order.
4. WHEN the Tooltip targets a Lost_Point whose Owner is charged to UNBLOCKED, THE Tooltip SHALL display "Lost to #<jersey> (<position>)" and "Charged to UNBLOCKED".
5. WHEN the pointer leaves the Field_View or moves outside the Pocket_Disk, THE Tooltip SHALL hide.
6. WHILE the Tooltip is visible, WHEN the current Frame changes, THE Tooltip SHALL recompute its text for the same Grid_Point offset in the new Frame.
7. WHEN the Field_View receives keyboard focus, THE Viz_App SHALL set the Selected_Grid_Point to the Grid_Point at the QB position.
8. WHILE focus is on the Field_View, WHEN the user presses Shift+Arrow, THE Viz_App SHALL move the Selected_Grid_Point 0.25 yd in the arrow direction, clamped to the Pocket_Disk, and show the Tooltip for the Selected_Grid_Point.

### Requirement 12: Play picker

**User Story:** As a presenter, I want to switch between 4–6 showcase plays, so that I can show different protection failures.

#### Acceptance Criteria

1. THE Play_Picker SHALL list every Replay in `replays.json` exactly once, in file order, labelled with the situation text and the PFF outcome.
2. WHEN the user selects a different Replay in the Play_Picker, THE Viz_App SHALL within 500 ms load that Replay at `t = 0`, paused, and update the Field_View, Rail, Sparkline, Slider event ticks, legend and SYS_Bars.
3. WHEN the user selects a Replay, THE Viz_App SHALL write `?play=<gameId>-<playId>` to the page URL via `history.replaceState`, without reloading, without adding a history entry and preserving other URL parameters.
4. WHEN the page loads with a `play` URL parameter matching a Replay, THE Play_Picker SHALL select that Replay at `t = 0`, paused.
5. IF the `play` URL parameter is absent, empty or matches no Replay, THEN THE Play_Picker SHALL select the first Replay without showing an error.
6. THE legend SHALL list each blocker of the selected Replay in `players` order with colour swatch, slot label and name, followed by UNBLOCKED only when present.
7. IF `replays.json` is valid and contains zero Replays, THEN THE Viz_App SHALL disable the Play_Picker and show "No plays available" in place of the Field_View, leaving the Leaderboard and Validation_Section unaffected.
8. THE Play_Picker SHALL be keyboard operable and expose an accessible name.
9. WHEN the user re-selects the currently selected Replay, THE Viz_App SHALL leave the Current_Time, playback state and URL unchanged.

### Requirement 13: Leaderboard

**User Story:** As a scout, I want to rank linemen by SYS against their position, so that I can compare protectors fairly.

#### Acceptance Criteria

1. THE Leaderboard SHALL include only players with `snaps ≥ minSnaps` (default 150) and sort them by `sys25` ascending, then by `name`, then by `nflId`.
2. THE Leaderboard SHALL show columns in the order: rank (1..n of the displayed order), Player (name and team), Pos, Snaps, SYS@2.5 (1 decimal), SYS at end (1 decimal), Percentile (integer), vs position avg (distribution marker bar) and Tier.
3. THE Leaderboard SHALL show Tier as a text label and a distinct colour per Tier.
4. WHEN the user activates a position chip (All OL, Tackles, Guards, Centers), THE Leaderboard SHALL show only players of that position combined with the search filter, set `aria-pressed="true"` on the active chip and `aria-pressed="false"` on the others.
5. WHEN the user types in the search field, THE Leaderboard SHALL show only players whose name or team contains the trimmed search text case-insensitively, combined with the active position chip, and treat empty trimmed text as no filter.
6. WHEN the filters leave zero Displayed_Rows, THE Leaderboard SHALL hide all rows and show "No linemen match this filter", keeping the active chip and search text.
7. WHEN the user activates a Leaderboard row by click, Enter or Space, THE Viz_App SHALL open the Player_Panel for that player.
8. THE Leaderboard rows SHALL be reachable with the Tab key.
9. WHEN the Leaderboard first renders, THE Leaderboard SHALL have the All OL chip active and the search field empty.
10. THE search field SHALL accept at most 50 characters and expose an accessible label.

### Requirement 14: Player panel

**User Story:** As a coach, I want a per-player view with his weekly trend and worst rep, so that I know which snap to pull up on film.

#### Acceptance Criteria

1. WHEN the Player_Panel opens, THE Player_Panel SHALL show the player's name, team, position, snaps, sys25 (1 decimal), percentile (integer), Tier text, position average (1 decimal) and signed difference from the position average (1 decimal), all matching the originating Leaderboard row.
2. WHERE the player has `byWeek` data, THE Player_Panel SHALL show a SYS-by-week chart with points in week order, a reference line at the position average and a text alternative listing each week's value.
3. WHERE the player has no `byWeek` data, THE Player_Panel SHALL show "Weekly data unavailable".
4. WHERE the player has `worstRep` data, THE Player_Panel SHALL show the worst rep's week, full description and sys25.
5. WHERE the player has no `worstRep` data, THE Player_Panel SHALL show "No worst rep recorded" and show neither the "Watch this rep" control nor "Replay not in showcase set".
6. WHEN the worst rep's `gameId` and `playId` match a loaded Replay, THE Player_Panel SHALL show a "Watch this rep" control operable by click, Enter and Space.
7. WHEN the user activates "Watch this rep", THE Viz_App SHALL close the Player_Panel, select the matching Replay in the Play_Picker at `t = 0` and scroll the Field_View fully into view.
8. IF the worst rep matches no Replay or `replays.json` failed to load, THEN THE Player_Panel SHALL show "Replay not in showcase set" and leave the Play_Picker unchanged.
9. WHEN the Player_Panel opens, THE Player_Panel SHALL move focus to the close control and trap focus inside the Player_Panel.
10. WHEN the user presses Escape or activates the close control, THE Player_Panel SHALL close and return focus to the originating Leaderboard row with the filters unchanged.

### Requirement 15: Validation section ("Does it work?")

**User Story:** As a judge, I want evidence that SYS measures something real, so that I trust the metric.

#### Acceptance Criteria

1. THE Validation_Section SHALL render each `headlines` entry in file order with the value as the primary number, the unit next to the value, the label as caption and the note below, omitting optional elements that are absent.
2. THE Validation_Section SHALL render each `charts` entry in file order as an SVG chart of the declared type plotting every point, with the title as a heading, both axis labels, a legend when the chart has 2 or more series, and the caption.
3. THE Validation_Section SHALL give each chart SVG an accessible name equal to the title and an accessible description equal to the caption, or to the axis labels and series names when the caption is absent.
4. WHILE `validation.json` has `stub` set to `true`, THE Validation_Section SHALL display the label "Placeholder · awaiting Workstream B results" on every headline and chart.
5. WHILE `validation.json` has `stub` absent or `false`, THE Validation_Section SHALL display no placeholder label.
6. IF `validation.json` fails to load or validate, THEN THE Validation_Section SHALL show an error state naming `validation.json`, confined to the Validation_Section.
7. WHEN a chart series has an empty `points` array, THE Validation_Section SHALL show the chart title, axis labels and caption plus the message "No data points".

### Requirement 16: Audience angles and Broadcast mode

**User Story:** As a coach, scout or broadcaster, I want a section addressed to my job, so that I see immediately how to use the map.

#### Acceptance Criteria

1. THE Viz_App SHALL include an Audience_Angles section with exactly three cards in the order Coach ("which lineman and which rep to review on film"), Scout ("rank vs position and percentile") and Broadcaster ("pocket-shrinking overlay on the replay"), each with a heading, a 1–2 sentence description and one action control operable by click, Enter and Space.
2. WHEN the user activates the Coach card action and at least one Displayed_Row exists, THE Viz_App SHALL scroll to the Leaderboard and open the Player_Panel of the Displayed_Row with the highest sys25, ties broken by displayed order.
3. WHEN the user activates the Coach card action and zero Displayed_Rows exist, THE Viz_App SHALL scroll to the Leaderboard, open no Player_Panel and show a message that no linemen are displayed.
4. WHEN the user activates the Scout card action, THE Viz_App SHALL scroll to the Leaderboard and focus the search field without changing its text.
5. WHEN the user activates the Broadcaster card action, THE Viz_App SHALL scroll to the Field_View and enter Broadcast_Mode.
6. WHEN the user activates the Broadcast_Mode toggle on the stage while Broadcast_Mode is inactive, THE Field_View SHALL enter Broadcast_Mode at the same Current_Time and playback state and set the toggle `aria-pressed="true"`.
7. WHILE Broadcast_Mode is active, THE Field_View SHALL draw the Pocket_Remaining region as a single filled shape with an outline of at least 3:1 contrast against the field and the lost region in the charged blocker colours without cell borders.
8. WHILE Broadcast_Mode is active, THE Field_View SHALL draw, updated every Frame, an on-canvas Pocket_Remaining number in yd² to 1 decimal at 48 CSS px or larger and the name of the Leading_Blocker.
9. WHILE Broadcast_Mode is active and every Blocker_SYS is 0, THE Field_View SHALL display "No area charged yet" in place of the Leading_Blocker name.
10. WHEN the user deactivates Broadcast_Mode, THE Field_View SHALL return to the grid rendering at the same Current_Time and playback state and set the toggle `aria-pressed="false"`.

### Requirement 17: Naming and copy

**User Story:** As the team, I want the product consistently called the Pocket Accountability Map, so that the pitch avoids "blame" language.

#### Acceptance Criteria

1. THE Viz_App SHALL set the document title to exactly "Pocket Accountability Map" and render exactly one h1 with that text.
2. THE Viz_App SHALL contain no text matching the case-insensitive pattern "blame" in rendered text, the document title, `alt`, `title`, `aria-label`, `aria-description` and `placeholder` attributes, canvas text, the Sparkline, the Tooltip, the Player_Panel and Broadcast_Mode, excluding source identifiers, code comments and `web/reference/mockup.html`.
3. WHEN all three data requests have settled and any successfully loaded file has `stub` equal to `true` or a `stub` value other than boolean `true`, boolean `false` or absent, THE Viz_App SHALL show the Mockup_Tag in the header.
4. WHEN all three data requests have settled and every successfully loaded file has `stub` absent or `false`, THE Viz_App SHALL hide the Mockup_Tag visually and from assistive technologies.
5. IF all three data requests have settled and no file loaded successfully, THEN THE Viz_App SHALL show the Mockup_Tag.

### Requirement 18: Theming and responsive layout

**User Story:** As a viewer on any device, I want the page to look right in light or dark mode and on my phone, so that the demo works anywhere.

#### Acceptance Criteria

1. WHILE the `data-theme` attribute is absent from the root element, THE Viz_App SHALL apply the light theme for `prefers-color-scheme: light` or no preference and the dark theme for `prefers-color-scheme: dark`.
2. WHERE the `data-theme` attribute on the root element is "light" or "dark", THE Viz_App SHALL apply that theme, including to the Field_View canvas, Sparkline, SYS_Bars and Blocker_Palette, in place of the system preference.
3. THE Viz_App SHALL provide one theme toggle control operable by mouse, touch, Enter and Space, with an accessible name stating the theme it switches to.
4. WHEN the user activates the theme toggle, THE Viz_App SHALL set `data-theme` to the opposite of the current theme and re-render within 200 ms without reload, preserving the Current_Time, playback state and selected Replay.
5. WHILE `data-theme` is absent, WHEN the system colour scheme changes, THE Viz_App SHALL switch theme within 1 s, preserving the Current_Time, playback state and selected Replay.
6. WHILE the viewport width is 360 px or greater, THE Viz_App SHALL display all sections without horizontal page scrolling and fit the Field_View to its container at the 24/14 aspect ratio.
7. WHILE the viewport width is below 600 px, THE Leaderboard SHALL keep the rank, Player, SYS@2.5 and Tier columns visible and scroll the remaining columns within the table container only.

### Requirement 19: Accessibility

**User Story:** As a keyboard or screen-reader user, I want to operate and understand the replay, so that the visualisation is usable without a mouse or colour vision.

#### Acceptance Criteria

1. WHILE focus is on the Field_View or the Slider, WHEN the user presses Space, THE Playback_Controls SHALL toggle play/pause, restarting from the Snap_Frame when paused on the last Frame.
2. WHILE focus is on the Field_View or the Slider, WHEN the user presses Left or Right Arrow without Shift, THE Playback_Controls SHALL pause and step the current Frame by −0.1 s or +0.1 s, clamped to the first and last Frame without wrapping.
3. WHILE focus is on the Field_View or the Slider, WHEN the user presses Home or End, THE Playback_Controls SHALL pause and jump to the first or last Frame.
4. THE Slider SHALL expose `aria-valuetext` of "<t> seconds" with `t` to 1 decimal, followed by ", <event label>" when the current Frame matches an event (e.g. "1.6 seconds, RT beaten").
5. THE Field_View SHALL expose an accessible name that includes the selected Replay's situation text.
6. WHEN playback pauses or the current Frame matches an event, THE Live_Region SHALL announce Pocket_Remaining (1 decimal), the current `t`, the Leading_Blocker's name and the Leading_Blocker's Blocker_SYS (1 decimal).
7. WHILE playback is running, THE Live_Region SHALL make no announcement for Frames that match no event.
8. THE Viz_App SHALL give every icon-only control, the Play_Picker, the search field and each position chip an accessible name stating the action or filter (e.g. "Play", "Filter by position: C").
9. THE Viz_App SHALL convey blocker identity, split charges, UNBLOCKED and Tier through text labels or patterns that remain identifiable in greyscale.
10. WHILE `prefers-reduced-motion: reduce` is active, THE Viz_App SHALL start no playback without user action, disable smooth scrolling and animated transitions, and keep manual stepping available.
11. THE Viz_App SHALL meet a contrast ratio of at least 4.5:1 for body text and 3:1 for large text (≥ 18.66 px bold or ≥ 24 px) against its background in both themes, verified by an automated contrast check (full WCAG conformance requires manual review with assistive technologies).
12. WHILE the Tooltip is shown for the Selected_Grid_Point, THE Viz_App SHALL expose the Tooltip text to assistive technologies via the Field_View accessible description or the Live_Region.
13. THE Viz_App SHALL show a visible focus indicator with at least 3:1 contrast on every focusable control.
14. THE Viz_App SHALL order keyboard focus as Play_Picker, Field_View, Playback_Controls, Rail, then Leaderboard controls.

### Requirement 20: Cross-view consistency

**User Story:** As a presenter, I want the slider, bars and tooltip to agree on every showcase play, so that no judge catches a mismatch.

#### Acceptance Criteria

1. WHEN the current Frame changes by Slider, playback, the Replay button or the Play_Picker, THE Viz_App SHALL derive the Field_View cell colours, SYS_Bars values, hero number, Sparkline cursor and Tooltip text from one SYS_Engine result for a single Frame index of the selected Replay.
2. FOR ALL Replays and Frames, THE SYS_Bars value of each blocker SHALL equal that blocker's Blocker_SYS within 1e-6 yd², computed as the sum over attributed rushers of Charged_Area divided by N, with UNBLOCKED receiving the full Charged_Area.
3. FOR ALL Replays and Frames, the sum of all SYS_Bars values SHALL equal the sum of Charged_Area over all rushers within 1e-6 yd².
4. FOR ALL Replays and Frames, THE hero number SHALL equal (Grid_Point count − Lost_Point count) × 0.0625 at the displayed precision.
5. FOR ALL Replays, Frames and Grid_Points, THE Tooltip SHALL name the same Owner and blocker(s) whose colour fills the Grid_Point, and for clean Grid_Points SHALL display the Requirement 11 "Clean pocket" text naming no blocker.
6. FOR ALL Replays, the automated test suite SHALL scrub to each Frame index k from 0 to the last Frame and verify that the Slider value, the clock text (k × 0.1 to 1 decimal), the Sparkline cursor and the SYS_Bars values all refer to Frame k.
7. WHEN the selected Replay changes, THE Viz_App SHALL reset every view to the new Replay's Snap_Frame within one render cycle with no values from the previous Replay displayed.
8. IF the SYS_Engine fails for a Frame, THEN THE Viz_App SHALL keep all views on the last successfully computed Frame, leave the Slider unchanged and show an error naming the Replay and Frame index.

### Requirement 21: Automated tests

**User Story:** As the Workstream C developer, I want automated tests for the metric and the data validation, so that data drops from Workstream A do not silently break the page.

#### Acceptance Criteria

1. WHEN `npm test` is executed in `web/`, THE test suite SHALL run Vitest once and exit with code 0 when all tests pass and a non-zero code when any test fails.
2. THE test suite SHALL include fast-check property tests with at least 100 cases each for conservation within 1e-9 (7.6), bounds (7.7), even split (7.4), UNBLOCKED routing (7.5) and determinism (7.11).
3. THE property test generators SHALL produce Replays with 1–80 Frames, 1–7 rushers and exactly one QB.
4. THE test suite SHALL include an example test reproducing the Mockup Replay sack-frame figures within the ranges of Requirement 6.7.
5. THE test suite SHALL verify that every Stub_Data file passes the Schema_Validator with zero errors.
6. THE test suite SHALL verify that inputs with a missing field, a wrong type, an unknown assignment `nflId`, non-monotonic Frames, wrong-step Frames, zero QBs or multiple QBs each produce at least one error with a JSON path and no typed value.
7. THE test suite SHALL fail, naming the Replay and blocker, when a SYS_Engine sys25 differs from a provided `sys` value by more than 0.5 yd².
8. FOR ALL valid Replay objects, serialising with `JSON.stringify`, parsing with `JSON.parse` and validating with the Schema_Validator SHALL produce zero errors and an object deep-equal to the original (round-trip property).

### Requirement 22: Demo script

**User Story:** As the presenter, I want a 2-minute demo script, so that the pitch is rehearsed and fits the time slot.

#### Acceptance Criteria

1. THE Demo_Script SHALL be a Markdown file at `web/DEMO_SCRIPT.md`.
2. THE Demo_Script SHALL contain 250 to 320 spoken words, excluding headings, timestamps and on-screen action lines.
3. THE Demo_Script SHALL be divided into 5 to 8 contiguous segments timestamped in m:ss from 0:00 to 2:00, each lasting 0:10 to 0:40.
4. THE Demo_Script SHALL cover, in order, the SYS definition with the sys25 headline at 2.5 s, one replay walkthrough, the Coach angle, the Scout angle, the Broadcaster angle, the "Does it work?" evidence and a closing line.
5. THE Demo_Script SHALL list, for each segment, at least one on-screen action naming a control or section and its state.
6. THE Demo_Script SHALL use "Pocket Accountability Map" and contain no occurrence of "Pocket Blame Map".
7. THE Demo_Script SHALL identify the walkthrough play by its Play_Picker label from a Replay in the shipped `replays.json`.
8. THE Demo_Script SHALL quote only numbers that match the shipped data or are marked as placeholders.

### Requirement 23: Repository collaboration constraints

**User Story:** As a teammate working in parallel with agents, I want Workstream C isolated in its own folder and branch, so that Workstreams A and B are never disrupted.

#### Acceptance Criteria

1. THE Viz_App SHALL keep all Workstream C files (source, Stub_Data, Stub_Generator, Mockup copy, build configuration and Demo_Script) inside the top-level `web/` folder.
2. THE Path_Check SHALL list only paths under `web/` and `.kiro/specs/pocket-accountability-viz/`.
3. THE Workstream C developer SHALL commit on the Working_Branch, one requirement or fix per commit, with a commit message first line of at most 72 characters.
4. WHEN pushing the Working_Branch, THE Workstream C developer SHALL first fetch `origin/main`, rebase onto the fetched `origin/main` and re-run the Path_Check.
5. IF a rebase conflict occurs in a path outside `web/` and `.kiro/specs/pocket-accountability-viz/`, THEN THE Workstream C developer SHALL resolve the conflict to the exact `origin/main` version.
6. IF the build or tests fail after a rebase, THEN THE Workstream C developer SHALL fix the failure within `web/` only and push nothing until the build and tests pass.
7. THE Workstream C developer SHALL open pull requests from the Working_Branch into `main` and leave approval and merging to the repository owners.
8. THE Workstream C developer SHALL push only to the Working_Branch, with no push to `main` and no force push to any Shared_Branch.
9. WHEN rewriting already-pushed Working_Branch history, THE Workstream C developer SHALL use only `git push --force-with-lease`.
10. THE Workstream C commits SHALL include Workstream A and B JSON outputs only as stub-flagged files or unmodified copies inside `web/`, leaving the originals unmodified.
11. THE Viz_App SHALL be Vercel-ready as a static build with `web/` as project root, build command `npm run build` and output directory `dist`.
12. THE Workstream C developer SHALL leave Vercel project linking and deployment to a later step after all three workstreams finish.
