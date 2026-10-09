"""Task 6: radius sensitivity for the Pocket Accountability Map.

Compares per-lineman SYS leaderboards computed at pocket radius R=4, R=5, R=6.
R=5 is the production run (out/blocker_plays.csv); R=4 and R=6 are the
sensitivity runs in out/sens/.

For each radius we build a per-player mean of sys25 (and sys_peak) using the
leaderboard filter:
    officialPosition in {T, G, C}, not is_helper, not is_unblocked, sys25 notna.
Players are kept if they have >= MIN_SNAPS such snaps in the R=5 file
(fallback 100 if fewer than 60 linemen qualify at 150).

We report Spearman rho (pandas .corr(method='spearman')) between R4-vs-R5 and
R6-vs-R5 for mean sys25 and mean sys_peak, overall and per position, plus the
top-10 / bottom-10 overlap. Decision rule: keep R=5 unless any overall sys25
rho < 0.85.

Writes out/sensitivity.json and prints a compact table.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
LINE_POS = {'T', 'G', 'C'}
MIN_SNAPS = 150
MIN_SNAPS_FALLBACK = 100
MIN_LINEMEN = 60
RHO_THRESHOLD = 0.85

PATHS = {
    'R4': os.path.join(OUT, 'sens', 'bp_r4.csv'),
    'R5': os.path.join(OUT, 'blocker_plays.csv'),
    'R6': os.path.join(OUT, 'sens', 'bp_r6.csv'),
}


def leaderboard_rows(df):
    """Rows passing the leaderboard filter."""
    m = (
        df.officialPosition.isin(LINE_POS)
        & ~df.is_helper.astype(bool)
        & ~df.is_unblocked.astype(bool)
        & df.sys25.notna()
    )
    return df[m]


def per_player(df):
    """Per-player mean sys25 / sys_peak + position + snap count."""
    lb = leaderboard_rows(df)
    g = lb.groupby('nflId')
    out = pd.DataFrame({
        'mean_sys25': g.sys25.mean(),
        'mean_sys_peak': g.sys_peak.mean(),
        'snaps': g.size(),
        'officialPosition': g.officialPosition.first(),
        'displayName': g.displayName.first(),
    })
    return out


def spearman(a, b):
    """Spearman rho between two aligned Series (shared index only).

    Spearman's rho is the Pearson correlation of the (average-tie) ranks, which
    is exactly what pandas' .corr(method='spearman') computes -- but that path
    imports scipy, which is not installed here. Ranking then taking Pearson
    (.corr(method='pearson'), the default, pure-pandas) is identical.
    """
    j = pd.concat([a, b], axis=1, join='inner').dropna()
    if len(j) < 3:
        return None
    ra = j.iloc[:, 0].rank(method='average')
    rb = j.iloc[:, 1].rank(method='average')
    return float(ra.corr(rb))


def overlap(ref, cmp, metric, n, largest):
    """Fraction + ids overlap of the n-largest/smallest players by `metric`."""
    r = (ref[metric].nlargest(n) if largest else ref[metric].nsmallest(n)).index
    c = (cmp[metric].nlargest(n) if largest else cmp[metric].nsmallest(n)).index
    inter = set(r) & set(c)
    return len(inter) / n, sorted(int(x) for x in inter)


def main():
    frames = {k: pd.read_csv(p) for k, p in PATHS.items()}
    pp = {k: per_player(df) for k, df in frames.items()}

    # Qualifying set defined on the R=5 file.
    ref = pp['R5']
    min_snaps = MIN_SNAPS
    qual=ref[ref.snaps >= min_snaps]
    if qual.officialPosition.isin(LINE_POS).sum() < MIN_LINEMEN:
        min_snaps = MIN_SNAPS_FALLBACK
        qual = ref[ref.snaps >= min_snaps]
    keep = qual.index

    n_players = int(len(keep))
    n_by_pos = {p: int((qual.officialPosition == p).sum()) for p in sorted(LINE_POS)}

    # Restrict every radius' per-player table to the qualifying set.
    q = {k: pp[k].reindex(keep) for k in pp}
    pos5 = q['R5'].officialPosition

    results = {'metrics': {}}
    table_rows = []
    overall_sys25_rhos = []

    for metric in ('mean_sys25', 'mean_sys_peak'):
        mres = {}
        for cmp_key in ('R4', 'R6'):
            entry = {}
            # overall
            rho_all = spearman(q[cmp_key][metric], q['R5'][metric])
            entry['overall'] = rho_all
            if metric == 'mean_sys25' and rho_all is not None:
                overall_sys25_rhos.append(rho_all)
            # per position
            bypos = {}
            for p in sorted(LINE_POS):
                idx = pos5[pos5 == p].index
                bypos[p] = spearman(
                    q[cmp_key].loc[idx, metric], q['R5'].loc[idx, metric]
                )
            entry['by_position'] = bypos
            # top/bottom-10 overlap (vs R5), by this metric
            top_frac, top_ids = overlap(q['R5'], q[cmp_key], metric, 10, largest=True)
            bot_frac, bot_ids = overlap(q['R5'], q[cmp_key], metric, 10, largest=False)
            entry['top10_overlap'] = top_frac
            entry['top10_shared_ids'] = top_ids
            entry['bottom10_overlap'] = bot_frac
            entry['bottom10_shared_ids'] = bot_ids
            mres[cmp_key] = entry
            table_rows.append((
                metric, cmp_key, rho_all, bypos['T'], bypos['G'], bypos['C'],
                top_frac, bot_frac,
            ))
        results['metrics'][metric] = mres

    min_overall_sys25 = min(overall_sys25_rhos) if overall_sys25_rhos else None
    keep_r5 = (min_overall_sys25 is not None) and (min_overall_sys25 >= RHO_THRESHOLD)
    decision = (
        f"KEEP R=5 (all overall sys25 rho >= {RHO_THRESHOLD}; "
        f"min={min_overall_sys25:.4f})"
        if keep_r5 else
        f"REVISIT radius (an overall sys25 rho < {RHO_THRESHOLD}; "
        f"min={min_overall_sys25:.4f})"
    )

    payload = {
        'min_snaps': min_snaps,
        'min_snaps_fallback_used': min_snaps == MIN_SNAPS_FALLBACK,
        'rho_threshold': RHO_THRESHOLD,
        'n_players': n_players,
        'n_by_position': n_by_pos,
        'rows_per_radius': {k: int(len(frames[k])) for k in frames},
        'min_overall_sys25_rho': min_overall_sys25,
        'keep_r5': bool(keep_r5),
        'decision': decision,
        'metrics': results['metrics'],
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'sensitivity.json'), 'w') as f:
        json.dump(payload, f, indent=2)

    # ---- printed table ----
    def fmt(x):
        return ' n/a ' if x is None else f'{x:5.3f}'

    print(f'\nRadius sensitivity  (qualifying linemen: n={n_players}, '
          f'min_snaps={min_snaps})')
    print(f'  by position: T={n_by_pos["T"]}  G={n_by_pos["G"]}  C={n_by_pos["C"]}')
    print(f'  rows/radius: ' +
          '  '.join(f'{k}={len(frames[k])}' for k in ('R4', 'R5', 'R6')))
    print()
    header = (f'{"metric":<14}{"cmp":<5}{"overall":>9}{"T":>7}{"G":>7}{"C":>7}'
              f'{"top10":>8}{"bot10":>8}')
    print(header)
    print('-' * len(header))
    for metric, cmp_key, ov, t, g, c, top, bot in table_rows:
        print(f'{metric:<14}{cmp_key:<5}{fmt(ov):>9}{fmt(t):>7}{fmt(g):>7}'
              f'{fmt(c):>7}{top:>8.2f}{bot:>8.2f}')
    print()
    print(f'Min overall sys25 rho = {fmt(min_overall_sys25)}  '
          f'(threshold {RHO_THRESHOLD})')
    print(f'DECISION: {decision}')
    print(f'\nWrote {os.path.join("out", "sensitivity.json")}')


if __name__ == '__main__':
    main()
