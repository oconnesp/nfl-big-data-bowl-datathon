"""Export frame-by-frame replays for the Pocket Accountability page.

Coordinates are normalised so every play looks the same on screen:
  * offense always moves "up"; the line of scrimmage is up = 0
  * up     = yards up-field from the ball at the snap (negative = backfield)
  * across = yards to the offense's RIGHT of the ball at the snap
             (so screen-x = across, screen-y = up, viewed from behind the QB)

Usage:
  python replays.py                       # auto-pick showcase plays
  python replays.py --plays 2021090900:97,2021091200:1234
"""
import argparse, json, os
import numpy as np
import pandas as pd
from compute import OUT, R, T_STD, compute_play, read, tracking_path

FPS = 10


def _num(v):
    """JSON-safe scalar."""
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


class Meta:
    """Lazy-loaded static tables shared across exports."""
    def __init__(self):
        self.pff = read('pffScoutingData.csv')
        self.players = read('players.csv').set_index('nflId')
        self.plays = read('plays.csv').set_index(['gameId', 'playId'])
        self._tr = {}

    def tracking(self, gid):
        if gid not in self._tr:
            self._tr = {gid: pd.read_csv(tracking_path(gid))}   # keep one game cached
        return self._tr[gid]


def export_replay(gid, pid, radius=R, meta=None):
    meta = meta or Meta()
    df = meta.tracking(gid)
    df = df[df.playId == pid]
    roles = meta.pff[(meta.pff.gameId == gid) & (meta.pff.playId == pid)]
    res, why = compute_play(df, roles, radius)
    if res is None:
        raise ValueError(f'{gid}:{pid} not computable ({why})')
    s, e = res['s'], res['e']
    w = df[(df.frameId >= s) & (df.frameId <= e)]
    left = w.playDirection.iloc[0] == 'left'
    ball = w[(w.team == 'football') & (w.frameId == s)][['x', 'y']].to_numpy()[0]

    def norm(xy):
        xy = np.asarray(xy, float)
        x, y = xy[..., 0], xy[..., 1]
        bx, by = ball
        if left:
            x, y, bx, by = 120 - x, 53.3 - y, 120 - bx, 53.3 - by
        return np.stack([by - y, x - bx], -1)          # (across, up)

    ids = {'QB': [res['qb']], 'BLOCK': res['blockers'], 'RUSH': res['rushers']}
    jersey = w.groupby('nflId').jerseyNumber.first()
    players = []
    for side, lst in ids.items():
        for n in lst:
            p = meta.players.loc[n] if n in meta.players.index else None
            players.append(dict(nflId=int(n), side=side,
                                name=None if p is None else p.displayName,
                                position=None if p is None else p.officialPosition,
                                jersey=_num(jersey.get(n)),
                                lined_up=_num(roles.loc[roles.nflId == n, 'pff_positionLinedUp'].iloc[0])))
    allowed = {}
    for _, b in roles[roles.pff_role == 'Pass Block'].iterrows():
        tags = [k for k, c in [('sack', 'pff_sackAllowed'), ('hit', 'pff_hitAllowed'),
                               ('hurry', 'pff_hurryAllowed'), ('beaten', 'pff_beatenByDefender')]
                if b.get(c) == 1]
        if tags:
            allowed[str(int(b.nflId))] = tags

    # positions per frame for every listed player
    tracks = {}
    for n in ids['BLOCK']:
        sub = w[w.nflId == n].sort_values('frameId')
        if len(sub) == res['F']:
            tracks[n] = norm(sub[['x', 'y']].to_numpy())
    tracks[res['qb']] = norm(res['q'])
    for k, n in enumerate(res['rushers']):
        tracks[n] = norm(res['Rz'][:, k])
    bt = w[w.team == 'football'].sort_values('frameId')
    ball_tr = norm(bt[['x', 'y']].to_numpy()) if len(bt) == res['F'] else None

    frames = []
    for i in range(res['F']):
        fr = dict(t=round(i / FPS, 1),
                  pos={str(n): [round(float(a[i, 0]), 2), round(float(a[i, 1]), 2)]
                       for n, a in tracks.items()},
                  sys={str(k): round(float(c[i]), 2) for k, c in res['charge'].items()},
                  pocket=round(float(res['pocket'][i]), 2))
        if ball_tr is not None:
            fr['ball'] = [round(float(ball_tr[i, 0]), 2), round(float(ball_tr[i, 1]), 2)]
        frames.append(fr)

    pl = meta.plays.loc[(gid, pid)]
    m = dict(gameId=int(gid), playId=int(pid), quarter=_num(pl.quarter), down=_num(pl.down),
             yardsToGo=_num(pl.yardsToGo), gameClock=_num(pl.gameClock),
             possessionTeam=_num(pl.possessionTeam), defensiveTeam=_num(pl.defensiveTeam),
             playDescription=_num(pl.playDescription), passResult=_num(pl.passResult),
             dropBackType=_num(pl.dropBackType), fps=FPS, radius=radius,
             pocket_area_full=round(float(np.pi * radius * radius), 2), t_std=T_STD / FPS)
    return dict(meta=m, players=players,
                assign={str(r): [str(b) for b in bl] or ['UNBLOCKED'] for r, bl in res['bmap'].items()},
                helpers=[str(h) for h in sorted(res['helpers'])],
                pff_allowed=allowed, frames=frames)


def stub_pick(bp):
    """First play where a blocker was charged with a sack by PFF."""
    s = bp[bp.pff_sackAllowed == 1].sort_values(['gameId', 'playId']).iloc[0]
    return [(int(s.gameId), int(s.playId), 'sack')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plays', default=None, help='comma list of gameId:playId')
    ap.add_argument('--stub', action='store_true', help='export a single sack play')
    a = ap.parse_args()
    bp = pd.read_csv(os.path.join(OUT, 'blocker_plays.csv'))
    if a.plays:
        picks = [(int(g), int(p), 'custom') for g, p in (x.split(':') for x in a.plays.split(','))]
    elif a.stub:
        picks = stub_pick(bp)
    else:
        from showcase import pick_showcase
        picks = pick_showcase(bp)
    meta = Meta()
    out = []
    for g, p, tag in sorted(picks, key=lambda t: t[0]):
        r = export_replay(g, p, meta=meta)
        r['meta']['showcase'] = tag
        out.append(r)
        print(f'{tag:>16}  {g}:{p}  frames={len(r["frames"])}  {r["meta"]["playDescription"][:70]}')
    with open(os.path.join(OUT, 'replays.json'), 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print('wrote', os.path.join(OUT, 'replays.json'))


if __name__ == '__main__':
    main()
