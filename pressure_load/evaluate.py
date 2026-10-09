"""Does Threat Load predict pressure allowed? Build xP and Pressure Over Expected; test stability."""
import numpy as np, pandas as pd, sys, json
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
lt = pd.read_csv(f'{OUT}/ol_plays.csv')
res = {}

def auc(y, s): return roc_auc_score(y, s)

# 1. raw threat load
res['auc_threat_all'] = auc(lt.press, lt.threat)
res['auc_threat_within_pos'] = {p: auc(g.press, g.threat) for p, g in lt.groupby('pos')}
res['auc_exp_rushers'] = auc(lt.press, lt.exp_rushers)
res['auc_box_baseline'] = auc(lt.press, lt.defendersInBox.fillna(lt.defendersInBox.median()))
lt['tq'] = pd.qcut(lt.threat, 5, labels=['Q1 lightest', 'Q2', 'Q3', 'Q4', 'Q5 heaviest'])
res['press_by_threat_quintile'] = lt.groupby('tq', observed=True).press.mean().round(4).to_dict()

# 2. xP model: only things outside the lineman's control
lt['tackle'] = lt.pos.isin(['LT', 'RT']).astype(int)
lt['guard'] = lt.pos.isin(['LG', 'RG']).astype(int)
lt['dbt'] = lt.dropBackType.astype('category').cat.codes
lt['pa'] = lt.pff_playAction.fillna(0)
lt['threat_others'] = lt.groupby(['gameId', 'playId']).threat.transform('sum') - lt.threat
F = ['threat', 'exp_rushers', 'exp_rush_total', 'threat_others', 'help_side', 'tackle', 'guard', 'down', 'yardsToGo', 'dbt', 'pa']
lt['xP'] = np.nan; lt['xP_base'] = np.nan
for w in sorted(lt.week.unique()):
    tr, te = lt.week != w, lt.week == w
    m = HistGradientBoostingClassifier(random_state=0, max_iter=200, learning_rate=0.04, max_depth=4, min_samples_leaf=200, l2_regularization=1.0)
    m.fit(lt.loc[tr, F], lt.loc[tr, 'press'])
    lt.loc[te, 'xP'] = m.predict_proba(lt.loc[te, F])[:, 1]
    # baseline: position + situation only, no alignment
    Fb = ['tackle', 'guard', 'down', 'yardsToGo', 'dbt', 'pa']
    b = HistGradientBoostingClassifier(random_state=0, max_iter=200, learning_rate=0.04, max_depth=3, min_samples_leaf=200)
    b.fit(lt.loc[tr, Fb], lt.loc[tr, 'press'])
    lt.loc[te, 'xP_base'] = b.predict_proba(lt.loc[te, Fb])[:, 1]
res['auc_xP'] = auc(lt.press, lt.xP)
res['auc_xP_baseline_pos_situation'] = auc(lt.press, lt.xP_base)
res['brier_xP'] = brier_score_loss(lt.press, lt.xP); res['brier_base'] = brier_score_loss(lt.press, lt.xP_base)
res['calib_xP_deciles'] = lt.groupby(pd.qcut(lt.xP, 10, labels=False)).agg(pred=('xP', 'mean'), act=('press', 'mean')).round(4).to_dict('list')

# 3. Pressure Over Expected per lineman + split-half stability (odd/even week)
lt['poe'] = lt.press - lt.xP
lt['half'] = lt.week % 2
def stab(col, min_n=100):
    g = lt.groupby(['nflId', 'half'])[col].agg(['mean', 'size']).unstack()
    g = g[(g['size'][0] >= min_n / 2) & (g['size'][1] >= min_n / 2)]
    return g['mean'][0].corr(g['mean'][1]), len(g)
res['stability_raw_pressure_rate'] = stab('press')
res['stability_POE'] = stab('poe')
res['stability_avg_threat_faced'] = stab('threat')

agg = lt.groupby(['nflId', 'displayName']).agg(
    team=('possessionTeam', lambda s: s.mode()[0]), pos=('pos', lambda s: s.mode()[0]),
    snaps=('press', 'size'), pressures=('press', 'sum'), xpress=('xP', 'sum'),
    threat=('threat', 'mean'), help=('help_side', 'mean')).reset_index()
agg['press_rate'] = agg.pressures / agg.snaps
agg['xpress_rate'] = agg.xpress / agg.snaps
agg['poe_per100'] = 100 * (agg.pressures - agg.xpress) / agg.snaps
agg['threat_pct'] = agg.groupby(agg.pos.str[-1].map({'T': 'T', 'G': 'G', 'C': 'C'})).threat.rank(pct=True)
q = agg[agg.snaps >= 150].copy()
res['n_qualified'] = len(q)
# who moves most when you adjust for difficulty
q['rank_raw'] = q.press_rate.rank(); q['rank_adj'] = q.poe_per100.rank()
q['shift'] = q.rank_raw - q.rank_adj
res['most_unfairly_blamed'] = q.nlargest(5, 'shift')[['displayName', 'team', 'pos', 'snaps', 'press_rate', 'xpress_rate', 'poe_per100', 'threat']].round(3).to_dict('records')
res['flattered_by_easy_jobs'] = q.nsmallest(5, 'shift')[['displayName', 'team', 'pos', 'snaps', 'press_rate', 'xpress_rate', 'poe_per100', 'threat']].round(3).to_dict('records')
res['heaviest_load'] = q.nlargest(8, 'threat')[['displayName', 'team', 'pos', 'snaps', 'threat', 'press_rate', 'poe_per100']].round(3).to_dict('records')
res['best_poe'] = q.nsmallest(8, 'poe_per100')[['displayName', 'team', 'pos', 'snaps', 'press_rate', 'xpress_rate', 'poe_per100']].round(3).to_dict('records')
res['worst_poe'] = q.nlargest(8, 'poe_per100')[['displayName', 'team', 'pos', 'snaps', 'press_rate', 'xpress_rate', 'poe_per100']].round(3).to_dict('records')
res['raw_vs_adj_rank_spearman'] = q.press_rate.corr(q.poe_per100, method='spearman')
res['threat_by_pos'] = lt.groupby('pos').threat.mean().round(3).to_dict()
res['threat_double_vs_single'] = lt.groupby('double').threat.mean().round(3).to_dict()

lt.to_csv(f'{OUT}/ol_plays_scored.csv', index=False)
agg['qualified_150'] = agg.snaps >= 150
agg = agg.round({'xpress': 2, 'threat': 3, 'help': 2, 'press_rate': 4, 'xpress_rate': 4, 'poe_per100': 2, 'threat_pct': 2})
agg.sort_values(['qualified_150', 'poe_per100'], ascending=[False, True]).to_csv(f'{OUT}/ol_leaderboard.csv', index=False)
print(json.dumps(res, indent=1, default=str))
