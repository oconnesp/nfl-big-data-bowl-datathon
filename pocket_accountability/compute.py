"""Pocket Accountability Map: attribute lost pocket area to the blocker responsible.

Metric: Square Yards Surrendered (SYS).

Method (per 0.1 s frame, snap -> end of pocket phase):
  * Pocket disk = all points within R yards of the QB, sampled on a RES-yard grid.
  * A grid point is "lost" when some pass rusher is closer to it than the QB is.
    It is lost to that (nearest) rusher.
  * Each rusher's lost area is measured relative to the snap frame (clipped >= 0),
    so alignment depth doesn't count against anyone.
  * That surrendered area is charged to the blocker(s) PFF lists as blocking the
    rusher (split evenly when doubled). Rushers nobody blocked are charged to
    UNBLOCKED (nflId empty, is_unblocked=True).

Window: starts at the snap and ends at the first END event (throw, sack, strip sack,
shovel, fumble, interrupted pass) -- or at 'run', i.e. a QB scramble. Once the QB
leaves the pocket there is no pocket to protect, so scrambles end the window.

Integrity rules:
  * A play is dropped entirely if the QB or ANY rusher is missing a frame in the
    window. (Dropping only the rusher would hand his space to the next-nearest
    rusher and charge the wrong blocker.) Drops are counted by reason.
  * Blockers with no rusher charged to them (PFF lists no blocked player, or one
    who is not a pass rusher on the play) are kept with SYS 0 but flagged
    is_helper=True, so they can be excluded from averages.

Outputs (in ./out):
  blocker_plays.csv  one row per blocker per play (+ UNBLOCKED rows)
  drop_report.json   plays seen / kept / dropped by reason
"""
import argparse, glob, json, os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(HERE, 'out')
R = 5.0          # pocket radius (yd)
RES = 0.25       # grid spacing (yd)
CELL = RES * RES
T_STD = 25       # frames at 10 Hz -> 2.5 s "standard pocket time"
SNAP = {'ball_snap', 'autoevent_ballsnap'}
END = {'pass_forward', 'autoevent_passforward', 'qb_sack', 'qb_strip_sack', 'run',
       'pass_shovel', 'fumble', 'autoevent_passinterrupted'}
DROP_REASONS = ('no_pff', 'no_qb', 'no_rushers', 'no_snap', 'too_short', 'missing_frames')
PFF_COLS = ['pff_positionLinedUp', 'pff_blockType', 'pff_sackAllowed', 'pff_hitAllowed',
            'pff_hurryAllowed', 'pff_beatenByDefender']


@lru_cache(maxsize=None)
def grid(radius):
    """(P, 2) offsets from the QB covering the pocket disk."""
    g = np.arange(-radius, radius + RES / 2, RES)
    gx, gy = np.meshgrid(g, g)
    m = gx**2 + gy**2 <= radius * radius
    return np.stack([gx[m], gy[m]], 1)


def read(name):
    return pd.read_csv(os.path.join(DATA, name))


def tracking_path(gid):
    return os.path.join(DATA, 'tracking', f'tracking_{gid}.csv')


def play_window(df):
    """Return (snap_frame, end_frame) or None."""
    ev = df.loc[df.event.notna() & (df.event != 'None'), ['frameId', 'event']].drop_duplicates()
    snaps = ev.loc[ev.event.isin(SNAP), 'frameId']
    if snaps.empty:
        return None
    s = snaps.min()
    ends = ev.loc[ev.event.isin(END) & (ev.frameId > s), 'frameId']
    e = ends.min() if not ends.empty else df.frameId.max()
    return int(s), int(e)


def _track(df, nid, F):
    """(F, 2) x/y of one player over the window, or None if any frame is missing."""
    sub = df[df.nflId == nid].sort_values('frameId')
    if len(sub) != F or sub.frameId.nunique() != F:
        return None
    return sub[['x', 'y']].to_numpy()


def compute_play(df, roles, radius=R):
    """SYS for one play.

    df: tracking rows for the play; roles: PFF rows for the play.
    Returns (result, None) on success or (None, drop_reason).
    """
    if roles.empty:
        return None, 'no_pff'
    qb = roles.loc[roles.pff_role == 'Pass', 'nflId']
    if len(qb) != 1:
        return None, 'no_qb'
    rushers = roles.loc[roles.pff_role == 'Pass Rush', 'nflId'].astype(int).tolist()
    if not rushers:
        return None, 'no_rushers'
    win = play_window(df)
    if win is None:
        return None, 'no_snap'
    s, e = win
    if e - s < 3:
        return None, 'too_short'
    df = df[(df.frameId >= s) & (df.frameId <= e)]
    F = e - s + 1
    qbid = int(qb.iloc[0])
    q = _track(df, qbid, F)
    rx = [_track(df, r, F) for r in rushers]
    if q is None or any(a is None for a in rx):
        return None, 'missing_frames'

    G = grid(radius)
    Rz = np.stack(rx, 1)                                  # (F, K, 2)
    pts = q[:, None, :] + G[None, :, :]                   # (F, P, 2)
    dq = np.linalg.norm(pts - q[:, None, :], axis=2)      # (F, P)
    dr = np.linalg.norm(pts[:, None, :, :] - Rz[:, :, None, :], axis=3)  # (F, K, P)
    near = dr.argmin(1)                                   # (F, P)
    lost = dr.min(1) < dq                                 # (F, P)
    K = len(rushers)
    area = np.zeros((F, K))
    for k in range(K):
        area[:, k] = ((near == k) & lost).sum(1) * CELL
    surr = np.clip(area - area[0], 0, None)               # (F, K)
    pocket = (~lost).sum(1) * CELL                        # QB-controlled area (F,)

    blockers = roles[roles.pff_role == 'Pass Block']
    bmap = {r: [] for r in rushers}
    helpers = set()
    for _, b in blockers.iterrows():
        t = b.pff_nflIdBlockedPlayer
        if pd.notna(t) and int(t) in bmap:
            bmap[int(t)].append(int(b.nflId))
        else:
            helpers.add(int(b.nflId))
    charge = {}
    for k, r in enumerate(rushers):
        who = bmap[r] or ['UNBLOCKED']
        for w in who:
            charge.setdefault(w, np.zeros(F))
            charge[w] += surr[:, k] / len(who)
    for b in blockers.nflId.astype(int):
        charge.setdefault(int(b), np.zeros(F))
    return dict(s=s, e=e, F=F, qb=qbid, rushers=rushers, blockers=blockers.nflId.astype(int).tolist(),
                q=q, Rz=Rz, surr=surr, pocket=pocket, charge=charge, bmap=bmap,
                helpers=helpers), None


def process_file(job):
    path, radius = job
    pff = read('pffScoutingData.csv')
    tr = pd.read_csv(path)
    gid = int(tr.gameId.iloc[0])
    pff = pff[pff.gameId == gid]
    rows, reasons, seen = [], Counter(), 0
    for pid, df in tr.groupby('playId'):
        seen += 1
        res, why = compute_play(df, pff[pff.playId == pid], radius)
        if res is None:
            reasons[why] += 1
            continue
        team = df.groupby('nflId').team.first()
        off_team = team.get(res['qb'])
        for w, c in res['charge'].items():
            unb = w == 'UNBLOCKED'
            rows.append(dict(gameId=gid, playId=int(pid), nflId=np.nan if unb else w,
                             is_unblocked=unb, is_helper=(not unb) and w in res['helpers'],
                             team=off_team if unb else team.get(w), frames=res['F'],
                             sys25=float(c[T_STD]) if res['F'] > T_STD else np.nan,
                             sys_end=float(c[-1]), sys_peak=float(c.max()),
                             sys_mean=float(c.mean())))
    return rows, reasons, seen


def enrich(out):
    """Add player name/position, PFF block info + allowed flags, and week."""
    n0 = len(out)
    out['nflId'] = out.nflId.astype('Int64')
    players = read('players.csv')[['nflId', 'displayName', 'officialPosition']]
    pff = read('pffScoutingData.csv')[['gameId', 'playId', 'nflId'] + PFF_COLS]
    games = read('games.csv')[['gameId', 'week']]
    players['nflId'] = players.nflId.astype('Int64')
    pff['nflId'] = pff.nflId.astype('Int64')
    out = out.merge(players, on='nflId', how='left', validate='many_to_one')
    out = out.merge(pff, on=['gameId', 'playId', 'nflId'], how='left', validate='many_to_one')
    out = out.merge(games, on='gameId', how='left', validate='many_to_one')
    assert len(out) == n0, 'join changed row count'
    return out


def run(games=None, workers=7, radius=R, out_csv=None, report=True):
    files = sorted(glob.glob(os.path.join(DATA, 'tracking', 'tracking_*.csv')))
    if games:
        files = files[:games]
    rows, reasons, seen = [], Counter(), 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, (r, why, n) in enumerate(ex.map(process_file, [(f, radius) for f in files])):
            rows += r
            reasons += why
            seen += n
            print(f'{i+1}/{len(files)}', end='\r', flush=True)
    print()
    out = enrich(pd.DataFrame(rows))
    out_csv = out_csv or os.path.join(OUT, 'blocker_plays.csv')
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    out.to_csv(out_csv, index=False)
    kept = out[['gameId', 'playId']].drop_duplicates().shape[0]
    rep = dict(radius=radius, games=len(files), plays_seen=seen, plays_kept=kept,
               dropped={k: int(reasons.get(k, 0)) for k in DROP_REASONS},
               rows=len(out), helper_rows=int(out.is_helper.sum()),
               unblocked_rows=int(out.is_unblocked.sum()))
    assert kept + sum(rep['dropped'].values()) == seen
    if report:
        with open(os.path.join(os.path.dirname(out_csv), 'drop_report.json'), 'w') as f:
            json.dump(rep, f, indent=2)
    print(json.dumps(rep, indent=2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=None, help='only the first N games (sorted)')
    ap.add_argument('--workers', type=int, default=7)
    ap.add_argument('--radius', type=float, default=R, help='pocket radius in yards')
    ap.add_argument('--out', default=None, help='output CSV path (default out/blocker_plays.csv)')
    a = ap.parse_args()
    run(a.games, a.workers, a.radius, a.out, report=a.out is None)


if __name__ == '__main__':
    main()
