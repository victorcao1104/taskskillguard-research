"""Freeze and optionally execute the finite phase-four Replay/enforcement grid."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from tsg.replay_v4 import (PINNED_IMAGE, build_cases, build_grid, compare_triad,
                           ordered_parallel_jobs, run_container, summarize, worker_source)


def immutable(path, value):
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('PRESERVED_OUTPUT_MISMATCH: ' + str(path))
    else:
        path.write_bytes(data)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'results/phase4/replay')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--plan-only', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Reuse preserved observations without retrying failures')
    parser.add_argument('--docker', default='docker')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=3,
                        help='Independent concurrent containers, from 1 to 4 (default 3)')
    args = parser.parse_args(argv)
    grid = build_grid()
    manifest = {'version': 'finite-replay-v4', 'pinned_image': PINNED_IMAGE,
                'planned_routes': 174, 'planned_container_runs': 173,
                'execution_workers': args.workers,
                'arms': dict(Counter(j['arm'] for j in grid)),
                'tasks_are': 'researcher-authored synthetic controls, not real user grants',
                'jobs': [{**j, 'worker_sha256': hashlib.sha256(worker_source(j).encode('utf-8')).hexdigest()}
                         for j in grid],
                'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                  for name in ('src/tsg/replay_v4.py', 'scripts/run_replay_phase4.py')},
                'scope': 'Fresh nonroot network-isolated container for every existing route; no corpus code, API, host mounts or credentials.'}
    immutable(args.out / 'frozen_grid.json', manifest)
    print(json.dumps({'planned_routes': 174, 'planned_container_runs': 173, 'execute': args.execute}), flush=True)
    if not args.execute:
        return
    inspected = subprocess.run([args.docker, 'image', 'inspect', PINNED_IMAGE, '--format', '{{.Id}}'],
                               capture_output=True, timeout=20, check=False)
    if inspected.returncode or inspected.stdout.decode().strip() != PINNED_IMAGE:
        raise RuntimeError('Pinned Docker image is unavailable; no alternate image or host fallback permitted')
    frozen_jobs = {j['run_id']: j for j in manifest['jobs']}

    def execute_job(job):
        directory = args.out / 'runs' / job['run_id']
        saved = directory / 'result.json'
        if saved.exists() and args.resume:
            result = json.loads(saved.read_text(encoding='utf-8'))
            if json.loads((directory / 'job.json').read_text(encoding='utf-8')) != job:
                raise ValueError('preserved job mismatch')
            if job['case']['reference_route'] != 'missing' or job['route'] != 'reference':
                if result.get('worker_sha256') != frozen_jobs[job['run_id']]['worker_sha256']:
                    raise ValueError('preserved worker hash mismatch')
        else:
            result = run_container(job, directory, docker=args.docker)
        return {**result, **{k: job[k] for k in ('run_id', 'arm', 'route', 'contract', 'ceiling', 'lease_state')},
                'case_id': job['case']['case_id']}

    rows = []
    for index, result in enumerate(ordered_parallel_jobs(grid, execute_job, workers=args.workers), 1):
        rows.append(result)
        print(json.dumps({'completed': index, 'total': len(grid), 'run_id': result['run_id'],
                          'status': result['status'], 'GoalSat': result.get('GoalSat')}), flush=True)
    by_case = {case['case_id']: {r['route']: r for r in rows if r['arm'] == 'replay'
                               and r['case_id'] == case['case_id']} for case in build_cases()}
    comparisons = [compare_triad(c, by_case[c['case_id']]['original'], by_case[c['case_id']]['neutralized'],
                                 by_case[c['case_id']]['reference']) for c in build_cases()]
    summary = summarize(rows, comparisons)
    summary['by_arm'] = {arm: summarize([r for r in rows if r['arm'] == arm], [])
                         for arm in ('replay', 'enforcement')}
    summary['grid_complete'] = len(rows) == 174 and {r['run_id'] for r in rows} == {j['run_id'] for j in grid}
    immutable(args.out / 'runs.json', rows)
    immutable(args.out / 'comparisons.json', comparisons)
    immutable(args.out / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
