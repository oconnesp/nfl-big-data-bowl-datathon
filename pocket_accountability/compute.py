"""Pocket Accountability Map: attribute lost pocket area to the blocker responsible.

Method (per frame, snap -> throw/sack/scramble):
  * Pocket disk = all points within R yards of the QB, sampled on a grid.
  * A grid point is "lost" when some pass rusher is closer to it than the QB is.
    It is lost to that (nearest) rusher.
  * Each rusher's lost area is measured relative to the snap frame (clipped >= 0),
    so alignment depth doesn't count against anyone.
  * That surrendered area is charged to the blocker(s) PFF lists as blocking the
    rusher (split evenly when doubled). Rushers nobody blocked go to "UNBLOCKED".

Outputs (in ./out):
  blocker_plays.csv  one row per blocker per play
  leaderboard.json   per-player season aggregates (OL only)
  replays.json       frame data for a few showcase plays
"""
import argparse, glob, json, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(HERE, 'out')
R = 5.0          # pocket radius (yd)
RES = 0.25       # grid spacing (yd)
T_STD = 25       # frames at 10 Hz -> 2.5 s "standard pocket time"
SNAP = {'ball_snap', 'autoevent_ballsnap'}
END = {'pass_forward', 'autoevent_passforward', 'qb_sack', 'qb_strip_sack', 'run',
       'pass_shovel', 'fumble', 'autoevent_passinterrupted'}

g = np.arange(-R, R + RES / 2, RES)
GX, GY = np.meshgrid(g, g)
mask = GX**2 + GY**2 <= R * R
GRID = np.stack([GX[mask], GY[mask]], 1)       # (P, 2) offsets from QB
CELL = RES * RES


def load_meta():
    pff = pd.read_csv(os.path.join(DATA, 'pffScoutingData.csv'))
    return pff


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


def process_file(path):
    pff = pd.read_csv(os.path.join(DATA, 'pffScoutingData.csv'))
    tr = pd.read_csv(path)
    gid = int(tr.gameId.iloc[0])
    pff = pff[pff.gameId == gid]
    rows = []
    for pid, df in tr.groupby('playId'):
        roles = pff[pff.playId == pid]
        qb = roles.loc[roles.pff_role == 'Pass', 'nflId']
        rushers = roles.loc[roles.pff_role == 'Pass Rush', 'nflId'].astype(int).tolist()
        blockers = roles[roles.pff_role == 'Pass Block']
        if len(qb) != 1 or not rushers:
            continue
        win = play_window(df)
        if win is None:
            continue
        s, e = win
        if e - s < 3:
            continue
        df = df[(df.frameId >= s) & (df.frameId <= e)]
        q = df[df.nflId == qb.iloc[0]].sort_values('frameId')[['x', 'y']].to_numpy()
        F = len(q)
        rx = []
        ok = []
        for r in rushers:
            a = df[df.nflId == r].sort_values('frameId')[['x', 'y']].to_numpy()
            if len(a) == F:
                rx.append(a); ok.append(r)
        if not ok or F != e - s + 1:
            continue
        rushers = ok
        Rz = np.stack(rx, 1)                                  # (F, K, 2)
        pts = q[:, None, :] + GRID[None, :, :]                # (F, P, 2)
        dq = np.linalg.norm(pts - q[:, None, :], axis=2)      # (F, P)
        dr = np.linalg.norm(pts[:, None, :, :] - Rz[:, :, None, :], axis=3)  # (F, K, P)
        near = dr.argmin(1)                                   # (F, P)
        lost = dr.min(1) < dq                                 # (F, P)
        K = len(rushers)
        area = np.zeros((F, K))
        for k in range(K):
            area[:, k] = ((near == k) & lost).sum(1) * CELL
        surr = np.clip(area - area[0], 0, None)               # (F, K)

        # rusher -> blockers
        bmap = {r: [] for r in rushers}
        for _, b in blockers.iterrows():
            t = b.pff_nflIdBlockedPlayer
            if pd.notna(t) and int(t) in bmap:
                bmap[int(t)].append(int(b.nflId))
        charge = {}
        for k, r in enumerate(rushers):
            who = bmap[r] or ['UNBLOCKED']
            for w in who:
                charge.setdefault(w, np.zeros(F))
                charge[w] += surr[:, k] / len(who)
        for _, b in blockers.iterrows():
            charge.setdefault(int(b.nflId), np.zeros(F))
        for w, c in charge.items():
            rows.append(dict(gameId=gid, playId=int(pid), nflId=w, frames=F,
                             sys25=float(c[T_STD]) if F > T_STD else np.nan,
                             sys_end=float(c[-1]), sys_peak=float(c.max()),
                             sys_mean=float(c.mean())))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=None, help='only the first N games (sorted)')
    ap.add_argument('--workers', type=int, default=7)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(DATA, 'tracking', 'tracking_*.csv')))
    if args.games:
        files = files[:args.games]
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(process_file, files)):
            rows += r
            print(f'{i+1}/{len(files)}', flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, 'blocker_plays.csv'), index=False)
    print(out.describe())


if __name__ == '__main__':
    main()
