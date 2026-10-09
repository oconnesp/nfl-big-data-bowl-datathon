"""Run the whole Pocket Accountability pipeline in order.

Stages (each a separate process, same interpreter, this folder as cwd):

  1. compute.py     - build out/blocker_plays.csv (accepts --games N)
  2. checks.py      - sanity report on the CSV
  3. leaderboard.py - aggregate blocker/team leaderboards
  4. replays.py     - export out/replays.json for the showcase plays
  5. checks.py      - re-run so the replay check now covers every showcase play

The pipeline stops at the first stage that exits non-zero.

Usage:
  python run_all.py            # full run
  python run_all.py --games 4  # pass --games 4 through to compute.py
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run_stage(script, extra_args=None):
    """Run one pipeline stage; return True on success (exit 0)."""
    cmd = [sys.executable, os.path.join(HERE, script)]
    if extra_args:
        cmd += extra_args
    print(f'\n=== {script} {" ".join(extra_args or [])} ===', flush=True)
    result = subprocess.run(cmd, cwd=HERE)
    return result.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=None,
                    help='only the first N games (passed through to compute.py)')
    a = ap.parse_args()

    compute_args = ['--games', str(a.games)] if a.games is not None else None

    # (script, extra_args) in run order.
    stages = [
        ('compute.py', compute_args),
        ('checks.py', None),
        ('leaderboard.py', None),
        ('replays.py', None),
        ('checks.py', None),  # re-run: replays.json now exists, so its check runs
    ]

    for script, extra_args in stages:
        if not run_stage(script, extra_args):
            print(f'\nFAILED at {script}; stopping.', file=sys.stderr)
            return 1

    print('\nAll stages completed successfully.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
