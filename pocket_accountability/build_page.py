"""Build the self-contained Pocket Accountability Map page.

Inlines out/replays.json (showcase plays), the worst reps of every 'Leaky' lineman,
out/leaderboard.json and headline validation numbers into page_template.html ->
pocket_accountability_map.html (opens straight from disk, no server needed).

Run after run_all.py:  python build_page.py
"""
import json, os
import pandas as pd
from compute import OUT
from checks import attribution, auc
from replays import Meta, export_replay

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, 'page_template.html')
PAGE = os.path.join(HERE, 'pocket_accountability_map.html')


def headline(bp):
    blk = bp[~bp.is_unblocked & ~bp.is_helper]
    out = {}
    for name, col, m in [('sack', 'pff_sackAllowed', 'sys_peak'), ('hurry', 'pff_hurryAllowed', 'sys_peak')]:
        n, rate, ch = attribution(bp, col, m)
        b = blk[blk[m].notna()]
        out[name] = dict(plays=n, top=round(rate, 3), chance=round(ch, 3),
                         auc=round(auc(b.loc[b[col] == 1, m], b.loc[b[col] != 1, m]), 3))
    sens = json.load(open(os.path.join(OUT, 'sensitivity.json')))
    out['rho'] = round(sens['min_overall_sys25_rho'], 3)
    drop = json.load(open(os.path.join(OUT, 'drop_report.json')))
    out['plays'] = drop['plays_kept']
    out['games'] = drop['games']
    out['rows'] = drop['rows']
    return out


def main():
    bp = pd.read_csv(os.path.join(OUT, 'blocker_plays.csv'))
    lb = json.load(open(os.path.join(OUT, 'leaderboard.json')))
    reps = json.load(open(os.path.join(OUT, 'replays.json')))
    have = {(r['meta']['gameId'], r['meta']['playId']) for r in reps}
    meta = Meta()
    worst = sorted({(p['worst_rep']['gameId'], p['worst_rep']['playId'], p['name'])
                    for p in lb['players'] if p['tier'] == 'Leaky'})
    for g, pid, name in worst:
        if (g, pid) in have:
            continue
        try:
            r = export_replay(g, pid, meta=meta)
        except ValueError as e:
            print('skip', e)
            continue
        r['meta']['showcase'] = 'worst_rep'
        r['meta']['worst_of'] = name
        reps.append(r)
        have.add((g, pid))
    data = dict(replays=reps, leaderboard=lb, stats=headline(bp))
    blob = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
    html = open(TEMPLATE, encoding='utf-8').read().replace('/*__DATA__*/null', blob)
    open(PAGE, 'w', encoding='utf-8').write(html)
    print(f'replays={len(reps)} players={len(lb["players"])} stats={data["stats"]}')
    print(f'wrote {PAGE} ({os.path.getsize(PAGE) / 1024:.0f} KB)')


if __name__ == '__main__':
    main()
