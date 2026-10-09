"""Pocket Accountability Map: offensive-line leaderboard (Workstream 1, Task 7).

Reads out/blocker_plays.csv (one row per blocker per play) and writes
out/leaderboard.json ranking offensive linemen by Square Yards Surrendered at the
standard pocket time (sys25).

A "snap" is one qualified blocker-play row:
  officialPosition in {T, G, C}, not a helper, not unblocked, sys25 present.
`position` is the slot he most often lined up at (PFF pff_positionLinedUp: LT/RT -> T,
LG/RG -> G, C -> C); `official_position` is the roster label.

Lower sys25 is better (less pocket space surrendered). Players are ranked within
their own position; a 100 percentile means the best (lowest mean sys25) at the spot.

Run:  python leaderboard.py
"""
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
CSV = os.path.join(OUT, 'blocker_plays.csv')
DROP = os.path.join(OUT, 'drop_report.json')
LEADERBOARD = os.path.join(OUT, 'leaderboard.json')

POSITIONS = ['T', 'G', 'C']
SLOT = {'LT': 'T', 'RT': 'T', 'LG': 'G', 'RG': 'G', 'C': 'C'}
DEFAULT_MIN_SNAPS = 150
FALLBACK_MIN_SNAPS = 100
MIN_PLAYERS = 60
PERCENTILE_NOTE = ('0-100 within position; 100 = best (lowest mean sys25), '
                   '0 = worst (highest mean sys25).')


def load_qualified(csv_path=CSV):
    """Return the subset of rows that count as snaps."""
    df = pd.read_csv(csv_path)
    mask = (df.officialPosition.isin(POSITIONS)
            & (~df.is_helper.astype(bool))
            & (~df.is_unblocked.astype(bool))
            & df.sys25.notna())
    q = df[mask].copy()
    q['nflId'] = q.nflId.astype('int64')
    # Rank by where the player actually lined up (PFF), not his roster label:
    # e.g. a listed T who played RG all season is judged against guards.
    q['slot'] = q.pff_positionLinedUp.map(SLOT)
    return q


def choose_min_snaps(snaps_per_player):
    """Pick the snap cutoff, falling back to 100 if too few linemen qualify at 150."""
    n_at_default = int((snaps_per_player >= DEFAULT_MIN_SNAPS).sum())
    if n_at_default >= MIN_PLAYERS:
        reason = (f'{n_at_default} linemen have >= {DEFAULT_MIN_SNAPS} snaps '
                  f'(>= {MIN_PLAYERS} required), so the default cutoff holds.')
        return DEFAULT_MIN_SNAPS, reason
    reason = (f'Only {n_at_default} linemen have >= {DEFAULT_MIN_SNAPS} snaps '
              f'(< {MIN_PLAYERS} required); fell back to {FALLBACK_MIN_SNAPS}.')
    return FALLBACK_MIN_SNAPS, reason


def most_frequent(series):
    """Most common non-null value (first by count, deterministic on ties)."""
    vc = series.dropna().value_counts()
    return vc.index[0] if len(vc) else None


def r3(x):
    """Round to 3 dp, keeping None/NaN as None for clean JSON."""
    if x is None:
        return None
    x = float(x)
    if np.isnan(x):
        return None
    return round(x, 3)


def build_players(q, min_snaps):
    """Build per-player records for everyone who meets min_snaps."""
    counts = q.groupby('nflId').size()
    keep = counts[counts >= min_snaps].index
    qk = q[q.nflId.isin(keep)].copy()

    # Per-player raw aggregates.
    agg = qk.groupby('nflId').agg(
        snaps=('sys25', 'size'),
        sys25_mean=('sys25', 'mean'),
        sys_peak_mean=('sys_peak', 'mean'),
        sys_end_mean=('sys_end', 'mean'),
    )
    name = qk.groupby('nflId').displayName.apply(most_frequent)
    team = qk.groupby('nflId').team.apply(most_frequent)
    position = qk.groupby('nflId').slot.apply(most_frequent)
    agg['name'] = name
    agg['team'] = team
    agg['position'] = position
    agg['official_position'] = qk.groupby('nflId').officialPosition.apply(most_frequent)
    agg['lined_up'] = pd.Series(
        {nid: {k: int(v) for k, v in s.value_counts().items()}
         for nid, s in qk.groupby('nflId').pff_positionLinedUp})

    # Position averages over qualified players (mean of players' sys25_mean).
    pos_avg = agg.groupby('position').sys25_mean.mean()

    players = []
    for pos in POSITIONS:
        grp = agg[agg.position == pos].copy()
        if grp.empty:
            continue
        pa = float(pos_avg[pos])
        n = len(grp)
        # Rank by sys25_mean ascending (1 = best / lowest). Percentile: 100 = best.
        grp = grp.sort_values('sys25_mean')
        ranks = grp.sys25_mean.rank(method='average', ascending=True)
        if n > 1:
            pct = (n - ranks) / (n - 1) * 100.0
        else:
            pct = pd.Series(100.0, index=grp.index)
        # Terciles by position within sorted (best -> worst).
        order = np.arange(n)  # 0 = best after sort
        tiers = np.where(order < n / 3.0, 'Wall',
                         np.where(order < 2 * n / 3.0, 'Average', 'Leaky'))

        for i, (nid, row) in enumerate(grp.iterrows()):
            sub = qk[qk.nflId == nid]
            weekly = (sub.groupby('week').sys25.mean()
                      .round(3).to_dict())
            weekly = {str(int(w)): v for w, v in weekly.items()}
            pressures = int(sub.pff_sackAllowed.fillna(0).sum()
                            + sub.pff_hitAllowed.fillna(0).sum()
                            + sub.pff_hurryAllowed.fillna(0).sum())
            snaps = int(row.snaps)
            worst = sub.loc[sub.sys25.idxmax()]
            players.append(dict(
                nflId=int(nid),
                name=row['name'],
                team=row['team'],
                position=pos,
                official_position=row['official_position'],
                lined_up=row['lined_up'],
                snaps=snaps,
                sys25_mean=r3(row.sys25_mean),
                sys_peak_mean=r3(row.sys_peak_mean),
                sys_end_mean=r3(row.sys_end_mean),
                pos_avg=r3(pa),
                vs_avg=r3(row.sys25_mean - pa),
                percentile=r3(float(pct.loc[nid])),
                tier=str(tiers[i]),
                weekly=weekly,
                pressures_allowed=pressures,
                pressure_rate=r3(pressures / snaps),
                worst_rep=dict(gameId=int(worst.gameId),
                               playId=int(worst.playId),
                               sys25=r3(worst.sys25)),
            ))
    position_averages = {pos: r3(pos_avg[pos]) for pos in POSITIONS if pos in pos_avg.index}
    # Sort by position (T, G, C order) then sys25_mean ascending.
    pos_order = {p: i for i, p in enumerate(POSITIONS)}
    players.sort(key=lambda p: (pos_order[p['position']], p['sys25_mean']))
    return players, position_averages


def read_radius():
    with open(DROP) as f:
        return json.load(f).get('radius')


def write_json(players, position_averages, min_snaps, min_snaps_reason, radius):
    doc = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        radius=radius,
        metric='sys25',
        min_snaps=min_snaps,
        min_snaps_reason=min_snaps_reason,
        percentile_note=PERCENTILE_NOTE,
        position_averages=position_averages,
        players=players,
    )
    with open(LEADERBOARD, 'w') as f:
        json.dump(doc, f, separators=(',', ':'))
    return doc


# ----------------------------------------------------------------------------- #
# verification + reporting                                                       #
# ----------------------------------------------------------------------------- #
def print_distribution(q):
    counts = q.groupby('nflId').size()
    print('=== Snap-count distribution (qualified linemen) ===')
    print(counts.describe().to_string())
    print(f'  players with >=100 snaps: {int((counts >= 100).sum())}')
    print(f'  players with >=150 snaps: {int((counts >= 150).sum())}')
    print(f'  players with >=200 snaps: {int((counts >= 200).sum())}')
    print()
    return counts


def verify(players, q, min_snaps):
    print('=== Verification ===')
    ok = all(p['snaps'] >= min_snaps for p in players)
    print(f'all players meet min_snaps ({min_snaps}): {ok}')

    for pos in POSITIONS:
        pcts = [p['percentile'] for p in players if p['position'] == pos]
        if pcts:
            good = all(0.0 <= v <= 100.0 for v in pcts)
            print(f'  {pos}: percentiles in [0,100]: {good} '
                  f'(min={min(pcts)}, max={max(pcts)})')

    # Independent recompute of sys25_mean for two players, straight from the CSV.
    df = pd.read_csv(CSV)
    sample = [p['nflId'] for p in players[:2]]
    print('  independent sys25_mean recompute:')
    all_match = True
    for nid in sample:
        sub = df[(df.nflId == nid)
                 & (df.officialPosition.isin(POSITIONS))
                 & (~df.is_helper.astype(bool))
                 & (~df.is_unblocked.astype(bool))
                 & df.sys25.notna()]
        hand = round(float(sub.sys25.mean()), 3)
        stored = next(p['sys25_mean'] for p in players if p['nflId'] == nid)
        match = hand == stored
        all_match = all_match and match
        print(f'    nflId {nid}: hand={hand} stored={stored} match={match}')
    print(f'  both recomputes match: {all_match}')
    return ok, all_match


def print_tables(players):
    for pos in POSITIONS:
        grp = [p for p in players if p['position'] == pos]
        if not grp:
            continue
        grp_sorted = sorted(grp, key=lambda p: p['sys25_mean'])
        print(f'\n=== Position {pos} ({len(grp_sorted)} players) ===')
        hdr = f'{"name":<24}{"team":<5}{"snaps":>6}{"sys25_mean":>12}  tier'
        print('  TOP 5 (best, lowest sys25_mean):')
        print('  ' + hdr)
        for p in grp_sorted[:5]:
            print(f'  {p["name"]:<24}{p["team"]:<5}{p["snaps"]:>6}'
                  f'{p["sys25_mean"]:>12}  {p["tier"]}')
        print('  BOTTOM 5 (worst, highest sys25_mean):')
        print('  ' + hdr)
        for p in grp_sorted[-5:]:
            print(f'  {p["name"]:<24}{p["team"]:<5}{p["snaps"]:>6}'
                  f'{p["sys25_mean"]:>12}  {p["tier"]}')


def main():
    q = load_qualified()
    counts = print_distribution(q)
    min_snaps, reason = choose_min_snaps(counts)
    print(f'min_snaps = {min_snaps}')
    print(f'reason: {reason}\n')

    radius = read_radius()
    players, position_averages = build_players(q, min_snaps)
    write_json(players, position_averages, min_snaps, reason, radius)

    per_pos = {pos: sum(1 for p in players if p['position'] == pos) for pos in POSITIONS}
    print(f'players written: {len(players)}  per position: {per_pos}')
    print(f'position_averages: {position_averages}\n')

    ok, match = verify(players, q, min_snaps)
    print_tables(players)

    size = os.path.getsize(LEADERBOARD)
    print(f'\nleaderboard.json size: {size} bytes ({size / 1024:.1f} KB) '
          f'-- under 500 KB: {size < 500 * 1024}')
    return 0


if __name__ == '__main__':
    main()
