"""Frozen grids, provenance, and history-preserving phase-three I/O."""
import hashlib
import itertools
import json
import subprocess
from pathlib import Path
from .trusted_planner_v2 import task_spec

MODELS = ('gpt-6-luna', 'gpt-4.1-mini')
BASELINE = '91d368833b298a558ea70778100a27ba038c3527'


def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]


def write_rows(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
    temporary.replace(path)


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protocol_jobs(cases):
    unique = {}
    for case in cases:
        if case['split'] == 'development':
            unique.setdefault(json.dumps(task_spec(case), sort_keys=True), case)
    jobs = []
    for index, case in enumerate(unique.values()):
        for model, rep, mode, catalog in itertools.product(MODELS, (0, 1), ('json', 'strict'), ('unified', 'split')):
            jobs.append({'job_id':f'factorial-{index}-{model}-{rep}-{mode}-{catalog}',
                         'case':case, 'model':model, 'replicate':rep,
                         'protocol_mode':mode, 'catalog':catalog})
    return jobs


def synthesis_jobs(cases, track):
    return [{'job_id':f'{track}-{c["case_id"]}-{m}-{rep}', 'case':c, 'model':m,
             'replicate':rep, 'track':track}
            for c, m, rep in itertools.product(cases, MODELS, (0, 1))]


def fork_budget(source, target):
    """One new cumulative ledger; old bytes must remain an unchanged prefix."""
    source, target = Path(source), Path(target)
    baseline = source.read_bytes()
    if target.exists():
        if not target.read_bytes().startswith(baseline):
            raise ValueError('BUDGET_HISTORY_MISMATCH')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(baseline)
    return {'source_sha256':hashlib.sha256(baseline).hexdigest(), 'source_bytes':len(baseline)}


def baseline_manifest(root):
    root = Path(root)
    names = subprocess.check_output(['git', 'ls-tree', '-rz', '--name-only', BASELINE], cwd=root).decode().split('\0')
    return {'baseline_commit':BASELINE, 'files':[
        {'path':name, 'sha256':sha(root/name)} for name in names if name]}


def check_baseline(root, manifest):
    root = Path(root)
    return [r['path'] for r in manifest['files'] if not (root/r['path']).is_file() or sha(root/r['path']) != r['sha256']]


def freeze(root, *, stage='formal'):
    root = Path(root)
    paths = sorted(set(p for folder in ('src', 'scripts', 'tests') for p in (root/folder).rglob('*v3*.py'))
                   | set((root/'scripts').glob('*phase3*.py'))
                   | set((root/'data/phase3').rglob('*.jsonl'))
                   | {root/'docs/phase3_design.md',root/'docs/phase3_plan.md'})
    # Analysis implementation is independently release-hashed; acquisition and
    # execution cannot drift while it is developed against predeclared endpoints.
    paths = [p for p in paths if p.name not in {'analysis_v3.py','test_analysis_v3.py','analyze_phase3.py'}]
    return {'stage':stage, 'baseline_commit':BASELINE,
            'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'files_sha256':{p.relative_to(root).as_posix():sha(p) for p in paths},
            'models':list(MODELS), 'cumulative_budget_limit_usd':20,
            'prices_usd_per_million':{'gpt-6-luna':[0.10,0.50], 'gpt-4.1-mini':[0.40,1.60]},
            'pricing_verified_utc_date':'2026-10-15',
            'pricing_sources':['https://developers.openai.com/api/docs/pricing',
                               'https://developers.openai.com/api/docs/models/gpt-4.1-mini']}


def verify_freeze(root, manifest):
    return [p for p, digest in manifest['files_sha256'].items() if not (Path(root)/p).is_file() or sha(Path(root)/p) != digest]
