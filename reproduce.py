"""Read-only offline verification of every current-paper evidence cohort."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    steps = [
        ('Release inventory', ['verify_release.py']),
        ('Region outputs', ['scripts/paper2_conventional_comparison_v1/replay_physical.py']),
        ('Publication safety', ['scripts/paper2_conventional_comparison_v1/replay_safety.py']),
        ('Buffering and skipping', ['scripts/design_study_v1/replay.py']),
        ('Network widths', ['scripts/width_study_v1/replay.py']),
        ('Organization by skipping', ['scripts/organization_skipping_v1/replay.py']),
        ('Retained RTL probe', ['results/traversal_assessment_v1/simulate.py']),
        ('Physical output suppression', ['scripts/output_suppression_v1/replay.py']),
        ('Offline geometry and channel sparsity', ['scripts/interpretation_v1/analyze.py']),
        ('Table and replay tests', ['-m', 'pytest', '-p', 'no:cacheprovider', 'tests', '-q']),
        ('Unchanged release', ['verify_release.py']),
    ]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for name, arguments in steps:
        print('\n=== '+name+' ===', flush=True)
        subprocess.run([sys.executable, '-B', *arguments], cwd=ROOT, env=env,
                       check=True, timeout=900)
    print('CURRENT_PAPER_REPLAY_PASS', len(steps), 'checks', flush=True)


if __name__ == '__main__':
    main()
