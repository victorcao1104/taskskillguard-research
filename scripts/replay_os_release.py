"""Fresh local Docker replication using saved contracts; never calls a model."""
import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_os_e2e_phase2 import execute, ContainerSandbox


def destination(root, target):
    root, target = Path(root).resolve(), Path(target).resolve()
    allowed = root / 'work'
    if target == allowed or not target.is_relative_to(allowed):
        raise ValueError('Fresh replication destination must be a child of repository work/')
    if target.exists():
        raise ValueError('Destination already exists; choose a new run directory')
    return target


def jobs(tasks, contracts, output):
    result = []
    for case in tasks:
        for guard in (False, True):
            for replicate in (0, 1):
                result.append((case,'oracle_correct_policy',None,{},guard,replicate,output))
                for contract in contracts:
                    if contract['case_id'] == case['case_id']:
                        result.append((case,'LLM_generated_mixed' if contract['mixed'] else 'LLM_generated_separated',contract['model'],contract,guard,replicate,output))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--image', required=True, help='An existing locally built trusted research image; no automatic pull')
    parser.add_argument('--case', action='append', dest='cases')
    parser.add_argument('--oracle-only', action='store_true')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    output = destination(ROOT, args.out)
    sandbox = ContainerSandbox(image=args.image)
    inspected = sandbox.command('image','inspect',args.image,'--format','{{.Id}}')
    if inspected.returncode:
        raise ValueError('Local image unavailable; build the documented trusted Dockerfile first')
    image_id = inspected.stdout.decode().strip()
    tasks = json.loads((ROOT / 'results/phase2/os_e2e/frozen_tasks.json').read_text(encoding='utf-8'))
    if args.cases:
        available = {c['case_id'] for c in tasks}
        if set(args.cases) - available:
            raise ValueError('Unknown case id')
        tasks = [c for c in tasks if c['case_id'] in args.cases]
    contracts = [] if args.oracle_only else [json.loads(s) for s in (ROOT / 'results/phase2/os_e2e/contracts.jsonl').read_text(encoding='utf-8').splitlines()]
    grid = jobs(tasks, contracts, output)
    output.mkdir(parents=True)
    freeze = {'timestamp_utc':datetime.now(timezone.utc).isoformat(), 'image_id':image_id, 'tasks':tasks,
              'expected_runs':len(grid), 'contracts_sha256':hashlib.sha256((ROOT / 'results/phase2/os_e2e/contracts.jsonl').read_bytes()).hexdigest(),
              'code_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'scripts/run_os_e2e_phase2.py',ROOT/'src/tsg/os_sandbox.py']},
              'interpretation':'New container observations with reused saved model contracts. Rebuilt image may differ from historical image; do not merge into published denominators.'}
    (output / 'replication_manifest.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(args.workers,4))) as pool:
        futures = [pool.submit(execute,*job,image=image_id) for job in grid]
        for future in concurrent.futures.as_completed(futures):
            records.append(future.result())
            (output / 'runs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
    print(json.dumps({'output':str(output.relative_to(ROOT)), 'runs':len(records),
                      'executed':sum(r['result']['status']=='executed' for r in records),'api_calls':0,
                      'task_goal_success':sum(r['task_oracle_goal_satisfied'] is True for r in records),
                      'unauthorized_observed':sum(r['unauthorized_execution'] is True for r in records)}))


if __name__ == '__main__':
    main()
