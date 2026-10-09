"""Pick a handful of showcase plays for the Pocket Accountability replay page.

pick_showcase(bp) reads only the blocker_plays.csv dataframe and returns a
deterministic list of (gameId:int, playId:int, tag:str) tuples, choosing plays
that read well in a replay:

  * sack_culprit_confirmed - a sack where the PFF-charged blocker clearly owns
    the pocket collapse (highest sys_peak, big margin over #2).
  * sack_hidden_culprit    - a sack where a DIFFERENT blocker (not the one PFF
    charged, not UNBLOCKED) has a much larger sys_peak than the charged blocker.
  * clean_pocket           - a non-sack play >= 3.5 s with the lowest total
    sys25 across blockers and essentially no UNBLOCKED surrender.
  * stunt                  - a play with a 'SW' (switch) blocker and meaningful
    SYS (total sys_peak > 10).
  * unblocked (optional)   - a play where UNBLOCKED has the largest sys_peak.

Picks prefer a 3.0-5.5 s window (frames 30-55) and rely on sys_peak / sys25
rather than the unreliable sys_end (which degenerates on sacks). Every pick is
validated by actually calling replays.export_replay; non-computable candidates
are skipped in favour of the next best one.
"""
import os
import pandas as pd

from compute import OUT

# Preferred replay duration: 3.0-5.5 s at 10 Hz.
FRAME_LO, FRAME_HI = 30, 55


def _play_frames(g):
    return int(g.frames.iloc[0])


def _good_duration(g):
    return FRAME_LO <= _play_frames(g) <= FRAME_HI


def _blockers(g):
    """Real charged blocker rows (not UNBLOCKED, not helpers)."""
    return g[~g.is_unblocked & ~g.is_helper]


def _unblocked(g):
    return g[g.is_unblocked]


def _is_sack(g):
    return bool((g.pff_sackAllowed == 1).any())


def _candidates(bp):
    """Yield (gameId, playId, group) grouped once, in deterministic order."""
    for (gid, pid), g in bp.groupby(['gameId', 'playId'], sort=True):
        yield int(gid), int(pid), g


def _sack_culprit_confirmed(bp, _meta_ok):
    """Sack where the PFF-charged blocker has the top sys_peak by a big margin."""
    scored = []
    for gid, pid, g in _candidates(bp):
        if not _is_sack(g) or not _good_duration(g):
            continue
        blk = _blockers(g)
        if len(blk) < 2:
            continue
        charged = blk[blk.pff_sackAllowed == 1]
        if charged.empty:
            continue
        ordered = blk.sort_values('sys_peak', ascending=False)
        top = ordered.iloc[0]
        if top.pff_sackAllowed != 1:
            continue  # charged blocker is not the top-SYS blocker
        second = ordered.iloc[1].sys_peak
        margin = float(top.sys_peak) - float(second)
        # require a clear, large margin and a genuinely active play
        if top.sys_peak < 8 or margin < 5:
            continue
        scored.append((margin, float(top.sys_peak), gid, pid))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2], t[3]))
    for _margin, _peak, gid, pid in scored:
        if _meta_ok(gid, pid):
            return (gid, pid, 'sack_culprit_confirmed')
    return None


def _sack_hidden_culprit(bp, _meta_ok):
    """Sack where a non-charged, non-UNBLOCKED blocker dwarfs the PFF-charged one."""
    scored = []
    for gid, pid, g in _candidates(bp):
        if not _is_sack(g) or not _good_duration(g):
            continue
        blk = _blockers(g)
        charged = blk[blk.pff_sackAllowed == 1]
        others = blk[blk.pff_sackAllowed != 1]
        if charged.empty or others.empty:
            continue
        charged_peak = float(charged.sys_peak.max())
        hidden = others.sort_values('sys_peak', ascending=False).iloc[0]
        hidden_peak = float(hidden.sys_peak)
        margin = hidden_peak - charged_peak
        # hidden blocker must clearly beat the charged one and be meaningful
        if hidden_peak < 8 or margin < 5:
            continue
        scored.append((margin, hidden_peak, gid, pid))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2], t[3]))
    for _margin, _peak, gid, pid in scored:
        if _meta_ok(gid, pid):
            return (gid, pid, 'sack_hidden_culprit')
    return None


def _clean_pocket(bp, _meta_ok):
    """Non-sack, >= 3.5 s, lowest total blocker sys25 and ~0 UNBLOCKED."""
    scored = []
    for gid, pid, g in _candidates(bp):
        if _is_sack(g):
            continue
        frames = _play_frames(g)
        if frames < 35 or frames > FRAME_HI:
            continue
        blk = _blockers(g)
        if blk.empty or blk.sys25.isna().any():
            continue
        unb = _unblocked(g)
        unb_peak = float(unb.sys_peak.max()) if not unb.empty else 0.0
        if unb_peak > 1.0:  # essentially no unblocked surrender
            continue
        total_sys25 = float(blk.sys25.sum())
        scored.append((total_sys25, unb_peak, gid, pid))
    scored.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    for _tot, _unb, gid, pid in scored:
        if _meta_ok(gid, pid):
            return (gid, pid, 'clean_pocket')
    return None


def _stunt(bp, _meta_ok):
    """Play with a 'SW' block type and meaningful SYS (total sys_peak > 10)."""
    scored = []
    for gid, pid, g in _candidates(bp):
        if not _good_duration(g):
            continue
        blk = _blockers(g)
        if blk.empty or not (blk.pff_blockType == 'SW').any():
            continue
        total_peak = float(blk.sys_peak.sum())
        if total_peak <= 10:
            continue
        scored.append((total_peak, gid, pid))
    # highest total SYS first (most visually interesting switch)
    scored.sort(key=lambda t: (-t[0], t[1], t[2]))
    for _tot, gid, pid in scored:
        if _meta_ok(gid, pid):
            return (gid, pid, 'stunt')
    return None


def _unblocked_pick(bp, _meta_ok):
    """Play where UNBLOCKED has the largest sys_peak on the play."""
    scored = []
    for gid, pid, g in _candidates(bp):
        if not _good_duration(g):
            continue
        unb = _unblocked(g)
        if unb.empty:
            continue
        unb_peak = float(unb.sys_peak.max())
        blk = _blockers(g)
        blk_peak = float(blk.sys_peak.max()) if not blk.empty else 0.0
        if unb_peak <= blk_peak or unb_peak < 8:
            continue
        margin = unb_peak - blk_peak
        scored.append((margin, unb_peak, gid, pid))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2], t[3]))
    for _margin, _peak, gid, pid in scored:
        if _meta_ok(gid, pid):
            return (gid, pid, 'unblocked')
    return None


def pick_showcase(bp):
    """Return a deterministic list of (gameId, playId, tag) showcase picks.

    Each pick is validated by calling replays.export_replay so that only
    computable plays are returned. Candidates are tried best-first and the
    first computable one wins; if a category has no computable candidate it is
    simply omitted.
    """
    import replays  # imported here to avoid a circular import at module load

    meta = replays.Meta()
    used = set()

    def _meta_ok(gid, pid):
        if (gid, pid) in used:
            return False
        try:
            replays.export_replay(gid, pid, meta=meta)
        except Exception:
            return False
        used.add((gid, pid))
        return True

    picks = []
    for picker in (_sack_culprit_confirmed, _sack_hidden_culprit,
                   _clean_pocket, _stunt, _unblocked_pick):
        p = picker(bp, _meta_ok)
        if p is not None:
            picks.append(p)
    return picks


def _describe(bp, gid, pid, tag):
    g = bp[(bp.gameId == gid) & (bp.playId == pid)]
    blk = _blockers(g)
    unb = _unblocked(g)
    frames = _play_frames(g)
    lines = [f'{tag}: {gid}:{pid}  frames={frames} (~{frames/10:.1f}s)']
    if tag == 'sack_culprit_confirmed':
        ordered = blk.sort_values('sys_peak', ascending=False)
        top = ordered.iloc[0]
        second = ordered.iloc[1]
        lines.append(f'  PFF-charged culprit {top.displayName} ({top.pff_positionLinedUp}) '
                     f'is top sys_peak={top.sys_peak:.2f} vs #2 '
                     f'{second.displayName} {second.sys_peak:.2f} '
                     f'(margin {top.sys_peak - second.sys_peak:.2f}), sys25={top.sys25:.2f}')
    elif tag == 'sack_hidden_culprit':
        charged = blk[blk.pff_sackAllowed == 1].iloc[0]
        others = blk[blk.pff_sackAllowed != 1].sort_values('sys_peak', ascending=False)
        hidden = others.iloc[0]
        lines.append(f'  PFF charged {charged.displayName} ({charged.pff_positionLinedUp}) '
                     f'sys_peak={charged.sys_peak:.2f}, but hidden culprit '
                     f'{hidden.displayName} ({hidden.pff_positionLinedUp}) '
                     f'sys_peak={hidden.sys_peak:.2f} '
                     f'(margin {hidden.sys_peak - charged.sys_peak:.2f})')
    elif tag == 'clean_pocket':
        unb_peak = float(unb.sys_peak.max()) if not unb.empty else 0.0
        lines.append(f'  non-sack, total blocker sys25={blk.sys25.sum():.2f}, '
                     f'UNBLOCKED peak={unb_peak:.2f} (clean)')
    elif tag == 'stunt':
        sw = blk[blk.pff_blockType == 'SW']
        names = ', '.join(f'{r.displayName}({r.pff_positionLinedUp})' for _, r in sw.iterrows())
        lines.append(f'  SW blocker(s): {names}; total sys_peak={blk.sys_peak.sum():.2f}')
    elif tag == 'unblocked':
        blk_peak = float(blk.sys_peak.max()) if not blk.empty else 0.0
        lines.append(f'  UNBLOCKED sys_peak={unb.sys_peak.max():.2f} vs best blocker '
                     f'{blk_peak:.2f}')
    desc = g.iloc[0]
    return '\n'.join(lines)


def main():
    bp = pd.read_csv(os.path.join(OUT, 'blocker_plays.csv'))
    picks = pick_showcase(bp)
    print(f'picked {len(picks)} showcase plays\n')
    for gid, pid, tag in picks:
        print(_describe(bp, gid, pid, tag))
        print()


if __name__ == '__main__':
    main()
