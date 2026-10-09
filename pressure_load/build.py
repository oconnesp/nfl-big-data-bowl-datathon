"""Snap-alignment Threat Load for offensive linemen.

Threat_i = sum_d P(rush_d) * w_di * q_d
  P(rush_d): out-of-fold model of whether defender d rushes, from snap alignment only
  w_di     : share of defender d that falls on lineman i (Gaussian on lateral offset, sigma fit
             so that PFF's actual blocker gets the most weight)
  q_d      : defender's pass-rush pressure rate, leave-one-week-out, beta-binomial shrunk
"""
import numpy as np, pandas as pd, sys
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

D = sys.argv[1] if len(sys.argv) > 1 else '.'
OUT = sys.argv[2] if len(sys.argv) > 2 else '.'
snap = pd.read_csv(f'{D}/pressure_load/work/snap.csv')
pff = pd.read_csv(f'{D}/data/pffScoutingData.csv')
plays = pd.read_csv(f'{D}/data/plays.csv')
players = pd.read_csv(f'{D}/data/players.csv')
games = pd.read_csv(f'{D}/data/games.csv')[['gameId', 'week']]
K = ['gameId', 'playId']
OL = ['LT', 'LG', 'C', 'RG', 'RT']

# ---------- normalise: offense attacks +x, LOS at x=0, ball at y=0 ----------
L = snap.playDirection == 'left'
snap['o'] = np.where(L, (snap.o + 180) % 360, snap.o)
snap['dir'] = np.where(L, (snap.dir + 180) % 360, snap.dir)
snap['x'] = np.where(L, 120 - snap.x, snap.x)
snap['y'] = np.where(L, 160 / 3 - snap.y, snap.y)
ball = snap[snap.team == 'football'][K + ['x', 'y']].rename(columns={'x': 'bx', 'y': 'by'})
snap = snap[snap.team != 'football'].merge(ball, on=K)
snap['X'] = snap.x - snap.bx          # + = downfield (defense side)
snap['Y'] = snap.y - snap.by          # lateral; offense's left is +Y when facing +x

pl = plays.merge(games, on='gameId')
snap = snap.merge(pl[K + ['possessionTeam', 'week']], on=K)
snap = snap.merge(pff[K + ['nflId', 'pff_role', 'pff_positionLinedUp']], on=K + ['nflId'], how='left')
snap = snap.merge(players[['nflId', 'officialPosition', 'displayName']], on='nflId', how='left')

off = snap[snap.team == snap.possessionTeam]
dfn = snap[snap.team != snap.possessionTeam].copy()

# OL positions per play (need all 5)
olpos = off[off.pff_positionLinedUp.isin(OL)].pivot_table(index=K, columns='pff_positionLinedUp', values='Y')
olpos = olpos.dropna()[OL]
print('plays with full OL at snap:', len(olpos))
ext = off[off.pff_role.isin(['Pass Block', 'Pass Route'])].copy()
# in-line / backfield potential helpers: TE or RB/FB within 8 yd laterally and behind LOS
ext = ext[ext.officialPosition.isin(['TE', 'RB', 'FB'])]

# ---------- defender features (alignment only) ----------
dfn = dfn.merge(olpos.reset_index(), on=K)
Ys = dfn[OL].values
dfn['lat'] = dfn.Y.abs()
dfn['depth'] = dfn.X
dfn['out_tackle'] = np.where(dfn.Y >= 0, dfn.Y - dfn.LT, dfn.RT - dfn.Y)   # + = outside the tackle
dfn['d_ol'] = np.abs(Ys - dfn.Y.values[:, None]).min(1)
# facing the offense? o is in degrees; 270 deg = facing -x in this frame (NGS convention: 0 = +y)
dfn['face_off'] = np.cos(np.deg2rad(dfn.o - 270))
dfn['speed'] = dfn.s
dfn['n_box'] = dfn.groupby(K).depth.transform(lambda d: (d < 5).sum())
dfn['rank_lat'] = dfn.groupby(K).lat.rank()
pos_map = {'DE': 0, 'DT': 1, 'NT': 1, 'OLB': 2, 'ILB': 3, 'MLB': 3, 'LB': 3, 'CB': 4, 'SS': 5, 'FS': 5, 'DB': 4}
dfn['posc'] = dfn.officialPosition.map(pos_map).fillna(4)
dfn = dfn.merge(pl[K + ['down', 'yardsToGo']], on=K)
dfn['rush'] = (dfn.pff_role == 'Pass Rush').astype(int)

F = ['depth', 'lat', 'out_tackle', 'd_ol', 'face_off', 'speed', 'n_box', 'rank_lat', 'posc', 'down', 'yardsToGo']
dfn['p_rush'] = np.nan
for w in sorted(dfn.week.unique()):            # leave-one-week-out
    tr, te = dfn.week != w, dfn.week == w
    m = HistGradientBoostingClassifier(random_state=0, max_iter=300, learning_rate=0.05, categorical_features=[F.index('posc')])
    m.fit(dfn.loc[tr, F], dfn.loc[tr, 'rush'])
    dfn.loc[te, 'p_rush'] = m.predict_proba(dfn.loc[te, F])[:, 1]
auc_rush = roc_auc_score(dfn.rush, dfn.p_rush)
exp_vs_act = dfn.groupby(K).agg(e=('p_rush', 'sum'), a=('rush', 'sum'))
print(f'P(rush) AUC={auc_rush:.3f}  per-play rushers: mean exp {exp_vs_act.e.mean():.2f} act {exp_vs_act.a.mean():.2f}  corr {exp_vs_act.corr().iloc[0,1]:.2f}')

# ---------- rusher quality q_d: leave-one-week-out shrunk pressure rate ----------
r = pff[pff.pff_role == 'Pass Rush'].merge(games.merge(plays[K].drop_duplicates()[['gameId']].drop_duplicates()), on='gameId')
r['pr'] = r[['pff_hit', 'pff_hurry', 'pff_sack']].fillna(0).max(1)
wk = r.groupby(['nflId', 'week']).agg(n=('pr', 'size'), k=('pr', 'sum')).reset_index()
tot = wk.groupby('nflId')[['n', 'k']].sum()
mu = tot.k.sum() / tot.n.sum()
# method-of-moments beta prior strength from players with >=50 rushes
big = tot[tot.n >= 50]; rate = big.k / big.n
var_b = max(rate.var() - (mu * (1 - mu) / big.n).mean(), 1e-5)
kappa = mu * (1 - mu) / var_b - 1
print(f'rusher pressure rate prior: mu={mu:.3f} kappa={kappa:.0f}')
q = []
for w in sorted(dfn.week.unique()):
    o = wk[wk.week != w].groupby('nflId')[['n', 'k']].sum()
    qq = (o.k + kappa * mu) / (o.n + kappa)
    q.append(pd.DataFrame({'nflId': qq.index, 'week': w, 'q': qq.values}))
q = pd.concat(q)
dfn = dfn.merge(q, on=['nflId', 'week'], how='left')
dfn['q'] = dfn.q.fillna(mu) / mu              # 1.0 = league-average rusher

# ---------- assignment weights w_di: tune sigma on PFF's actual blocker ----------
blk = pff[pff.pff_positionLinedUp.isin(OL) & pff.pff_nflIdBlockedPlayer.notna()][K + ['pff_positionLinedUp', 'pff_nflIdBlockedPlayer']]
blk = blk.rename(columns={'pff_nflIdBlockedPlayer': 'nflId', 'pff_positionLinedUp': 'blocker'})
blk = blk.drop_duplicates(K + ['nflId'], keep=False)            # single OL blocker only
chk = dfn.merge(blk, on=K + ['nflId'])
dY = chk[OL].values - chk.Y.values[:, None]
tgt = chk.blocker.map({p: i for i, p in enumerate(OL)}).values
best = None
for sig in [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 4]:
    W = np.exp(-dY ** 2 / (2 * sig ** 2)); W /= W.sum(1, keepdims=True)
    ll = np.log(np.clip(W[np.arange(len(W)), tgt], 1e-9, 1)).mean()
    acc = (W.argmax(1) == tgt).mean()
    print(f'  sigma={sig:<5} loglik={ll:.3f} top-1 acc={acc:.3f}')
    if best is None or ll > best[1]: best = (sig, ll, acc)
SIG = best[0]; print('chosen sigma', SIG, f'(PFF blocker is top-weighted {best[2]:.0%} of the time)')

dY = dfn[OL].values - dfn.Y.values[:, None]
W = np.exp(-dY ** 2 / (2 * SIG ** 2)); W /= W.sum(1, keepdims=True)
contrib = W * (dfn.p_rush * dfn.q).values[:, None]
cnt = W * dfn.p_rush.values[:, None]
for i, p in enumerate(OL):
    dfn['T_' + p] = contrib[:, i]; dfn['N_' + p] = cnt[:, i]
T = dfn.groupby(K)[['T_' + p for p in OL] + ['N_' + p for p in OL] + ['p_rush']].sum()
dfn.to_csv(f'{OUT}/defenders_snap.csv', index=False)

# ---------- long format: one row per OL per play ----------
rows = []
for p in OL:
    t = T[['T_' + p, 'N_' + p]].rename(columns={'T_' + p: 'threat', 'N_' + p: 'exp_rushers'}).reset_index()
    t['pos'] = p; rows.append(t)
lt = pd.concat(rows).merge(T[['p_rush']].rename(columns={'p_rush': 'exp_rush_total'}).reset_index(), on=K)

# help on each side: TE/RB/FB that ended up pass blocking (offense's choice, not the lineman's)
offh = off[off.pff_role == 'Pass Block'][~off.pff_positionLinedUp.isin(OL)]
offh = offh.assign(side=np.where(offh.Y >= 0, 'L', 'R'))
help_ = offh.groupby(K + ['side']).size().unstack(fill_value=0).reindex(columns=['L', 'R'], fill_value=0)
lt = lt.merge(help_.reset_index(), on=K, how='left').fillna({'L': 0, 'R': 0})
lt['help_side'] = np.where(lt.pos.isin(['LT', 'LG']), lt.L, np.where(lt.pos.isin(['RT', 'RG']), lt.R, (lt.L + lt.R) / 2))
lt = lt.drop(columns=['L', 'R'])

o5 = pff[pff.pff_positionLinedUp.isin(OL)].copy()
o5['press'] = o5[['pff_hitAllowed', 'pff_hurryAllowed', 'pff_sackAllowed']].fillna(0).max(1)
o5['beaten'] = o5.pff_beatenByDefender.fillna(0)
o5['double'] = o5.groupby(K + ['pff_nflIdBlockedPlayer']).nflId.transform('size').where(o5.pff_nflIdBlockedPlayer.notna(), 0) > 1
lt = lt.merge(o5[K + ['nflId', 'pff_positionLinedUp', 'press', 'beaten', 'double', 'pff_blockType']].rename(columns={'pff_positionLinedUp': 'pos'}), on=K + ['pos'])
lt = lt.merge(pl[K + ['week', 'possessionTeam', 'defensiveTeam', 'down', 'yardsToGo', 'dropBackType', 'pff_playAction', 'passResult', 'defendersInBox']], on=K)
lt = lt.merge(players[['nflId', 'displayName']], on='nflId', how='left')
lt.to_csv(f'{OUT}/ol_plays.csv', index=False)
print('OL-play rows:', len(lt), ' pressure-allowed rate:', round(lt.press.mean(), 4))
