"""Freeze or execute phase-five matched integrated recovery conditions."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from tsg.recovery_v5 import (PINNED_IMAGE, build_grid, canonical, digest, load_preserved,
                             ordered_parallel_jobs, request_hash, run_container,
                             save_terminal_failure, summarize, worker_source)


def immutable(path, value):
    data = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('PRESERVED_OUTPUT_MISMATCH: ' + str(path))
    else:
        path.write_bytes(data)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'results/phase5/recovery')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--plan-only', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Reuse every preserved outcome, including failures; never retry a condition')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=3)
    parser.add_argument('--docker', default='docker')
    args = parser.parse_args(argv)
    grid = build_grid()
    manifest = {'version': 'finite-integrated-recovery-v5', 'pinned_image': PINNED_IMAGE,
                'planned_container_runs': len(grid), 'execution_workers': args.workers,
                'source_sha256': {name: digest((ROOT / name).read_bytes()) for name in
                                  ('src/tsg/recovery_v5.py', 'scripts/run_recovery_phase5.py', 'src/tsg/replay_v4.py')},
                'jobs': [{**j, 'request_sha256': request_hash(j),
                          'evidence_directory': 'runs/' + request_hash(j)[:16],
                          'worker_sha256': digest(worker_source(j).encode('utf-8'))} for j in grid],
                'scope': 'Fixed trusted gateway; no corpus execution, external network, API, host mounts, or arbitrary-code containment claim.'}
    immutable(args.out / 'frozen_grid.json', manifest)
    print(json.dumps({'planned_container_runs': len(grid), 'execute': args.execute}), flush=True)
    if not args.execute:
        return 0
    # A failed image preflight becomes one explicit outcome per planned condition.
    # No image pulls, alternate images, host execution fallback, or hidden retries.
    preflight_error = None
    try:
        inspected = subprocess.run([args.docker, 'image', 'inspect', PINNED_IMAGE, '--format', '{{.Id}}'],
                                   capture_output=True, timeout=20, check=False)
        if inspected.returncode or inspected.stdout.decode().strip() != PINNED_IMAGE:
            preflight_error = 'Pinned image unavailable: ' + inspected.stderr.decode(errors='replace')[:1000]
    except (OSError, subprocess.TimeoutExpired) as error:
        preflight_error = str(error)

    def execute_job(job):
        # Compact deterministic names also fit Windows' common path limits.
        directory = args.out / 'runs' / request_hash(job)[:16]
        if directory.exists():
            if not args.resume:
                raise ValueError('Existing run requires --resume: ' + job['run_id'])
            if (directory / 'result.json').exists():
                return load_preserved(job, directory)
            # A previously started condition may have performed effects before
            # interruption. Preserve those files and never execute it again.
            return save_terminal_failure(job, directory, 'interrupted_unknown', 'Pre-existing incomplete evidence; no retry')
        if preflight_error:
            return save_terminal_failure(job, directory, 'image_preflight_failed', preflight_error)
        return run_container(job, directory, docker=args.docker)

    rows = []
    for index, result in enumerate(ordered_parallel_jobs(grid, execute_job, workers=args.workers), 1):
        rows.append(result)
        print(json.dumps({'completed': index, 'total': len(grid), 'run_id': result['run_id'],
                          'status': result['status'], 'GoalSat': result.get('GoalSat')}), flush=True)
    summary = summarize(rows)
    summary['grid_complete'] = len(rows) == len(grid) and {r['run_id'] for r in rows} == {j['run_id'] for j in grid}
    immutable(args.out / 'runs.json', rows)
    immutable(args.out / 'summary.json', summary)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
