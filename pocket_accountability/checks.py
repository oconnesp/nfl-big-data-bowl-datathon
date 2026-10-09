"""Sanity report for blocker_plays.csv (+ replays.json if present).

Hard checks (fail -> exit code 1):
  * every SYS value >= 0
  * per play, total SYS at a single frame (sys25, sys_end) <= full disk area
  * replays.json last-frame SYS == CSV sys_end
Reported, not enforced:
  * how often SYS falls back from its peak (rusher gave ground back)
  * attribution: on plays where PFF charged a blocker with a sack/hit/hurry/beaten,
    how often is that blocker the top-SYS blocker on the play (vs. chance), and
    AUC of SYS for flagged vs. unflagged blocker rows.
Writes out/checks_report.txt.
"""
import json, math, os, sys
import numpy as np
import pandas as pd
from compute import OUT

METRICS = ['sys25', 'sys_peak', 'sys_end']
FLAGS = {'sack': 'pff_sackAllowed', 'hit': 'pff_hitAllowed', 'hurry': 'pff_hurryAllowed',
         'beaten': 'pff_beatenByDefender'}


def auc(pos, neg):
    """P(random flagged row > random unflagged row), ties count half (Mann-Whitney)."""
    x = pd.concat([pos, neg]).rank()
    n1, n0 = len(pos), len(neg)
    return (x.iloc[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def attribution(bp, flag, metric):
    b = bp[~bp.is_unblocked & bp[metric].notna()]
    hit, chance, n = 0, 0.0, 0
    for _, g in b.groupby(['gameId', 'playId']):
        f = g[g[flag] == 1]
        if f.empty:
            continue
        n += 1
        top = g[metric].max()
        if top > 0 and f[metric].max() == top:
            hit += 1
        chance += len(f) / len(g)
    return n, hit / n if n else math.nan, chance / n if n else math.nan


def main():
    bp = pd.read_csv(os.path.join(OUT, 'blocker_plays.csv'))
    lines, fails = [], []
    say = lines.append
    disk = math.pi * json.load(open(os.path.join(OUT, 'drop_report.json')))['radius'] ** 2

    say(f'rows={len(bp)}  plays={bp[["gameId","playId"]].drop_duplicates().shape[0]}  '
        f'helper={bp.is_helper.mean():.1%}  unblocked rows={int(bp.is_unblocked.sum())}')
    say(open(os.path.join(OUT, 'drop_report.json')).read().replace('\n', ' '))

    # hard checks
    neg = (bp[['sys25', 'sys_end', 'sys_peak', 'sys_mean']] < 0).sum().sum()
    say(f'[{"PASS" if neg == 0 else "FAIL"}] negative SYS values: {neg}')
    if neg:
        fails.append('negative')
    for m in ['sys25', 'sys_end']:
        tot = bp.groupby(['gameId', 'playId'])[m].sum()
        over = int((tot > disk + 1e-6).sum())
        say(f'[{"PASS" if over == 0 else "FAIL"}] plays with total {m} > disk {disk:.1f}: {over} '
            f'(max total {tot.max():.1f})')
        if over:
            fails.append(m)
    rp = os.path.join(OUT, 'replays.json')
    if os.path.exists(rp):
        bad = 0
        reps = json.load(open(rp))
        for r in reps:
            m = r['meta']
            sub = bp[(bp.gameId == m['gameId']) & (bp.playId == m['playId'])]
            last = r['frames'][-1]['sys']
            for _, x in sub.iterrows():
                k = 'UNBLOCKED' if x.is_unblocked else str(int(x.nflId))
                bad += abs(last.get(k, -1) - x.sys_end) > 0.01
        say(f'[{"PASS" if bad == 0 else "FAIL"}] replays.json ({len(reps)} plays) last-frame SYS vs CSV mismatches: {bad}')
        if bad:
            fails.append('replays')

    # reported
    act = bp[bp.sys_peak > 0.5]
    fell = (act.sys_peak - act.sys_end > 0.5).mean()
    say(f'[INFO] of blocker rows with peak SYS > 0.5, {fell:.1%} end > 0.5 yd² below their peak')

    say('\nATTRIBUTION: is the PFF-flagged blocker the top-SYS blocker on the play?')
    say(f'{"flag":8}{"metric":10}{"plays":>7}{"top-SYS":>9}{"chance":>8}{"AUC":>7}')
    blk = bp[~bp.is_unblocked & ~bp.is_helper]
    weak = []
    for name, col in FLAGS.items():
        for m in METRICS:
            n, rate, ch = attribution(bp, col, m)
            b = blk[blk[m].notna()]
            a = auc(b.loc[b[col] == 1, m], b.loc[b[col] != 1, m])
            say(f'{name:8}{m:10}{n:7d}{rate:9.1%}{ch:8.1%}{a:7.3f}')
            if name == 'sack' and rate < 0.5:
                weak.append(f'{m} {rate:.0%}')
    if weak:
        say(f'[WARN] sack attribution below 50% for: {", ".join(weak)}')

    say('\nEXAMPLE SACK PLAYS (hand check):')
    sacks = bp[bp.pff_sackAllowed == 1][['gameId', 'playId']].drop_duplicates()
    for _, k in sacks.sample(3, random_state=1).iterrows():
        g = bp[(bp.gameId == k.gameId) & (bp.playId == k.playId)]
        say(f'-- {k.gameId}:{k.playId}')
        for _, x in g.sort_values('sys_peak', ascending=False).iterrows():
            nm = 'UNBLOCKED' if x.is_unblocked else f'{x.displayName} ({x.pff_positionLinedUp})'
            tag = ' <-- PFF sack' if x.pff_sackAllowed == 1 else (' [helper]' if x.is_helper else '')
            say(f'   {nm:32} sys25={x.sys25:6.2f} peak={x.sys_peak:6.2f} end={x.sys_end:6.2f}{tag}')

    say(f'\nRESULT: {"FAIL " + ",".join(fails) if fails else "ALL HARD CHECKS PASS"}')
    txt = '\n'.join(lines)
    print(txt)
    open(os.path.join(OUT, 'checks_report.txt'), 'w', encoding='utf-8').write(txt + '\n')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
