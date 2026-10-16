"""Immutable Phase 9 evidence helpers; no experiment semantics."""
import json
from phase6_common import ROOT, sha, jb, rb, immutable, read_rows

CAP = 29.551575125
MODELS = ('gpt-6-luna', 'gpt-4.1-mini')
BASE = '93eda0d23236912671c7b309eb78e7c80fd20db1'


def cases():
    old = [{**c, 'split': 'regression'} for phase in (7, 8)
           for c in read_rows(ROOT / f'data/phase{phase}/heldout.jsonl')]
    return old + read_rows(ROOT / 'data/phase9/heldout.jsonl')


def baseline():
    names = (ROOT / 'work/phase9-baseline-names.txt').read_text(encoding='utf-8-sig').splitlines()
    hashes = {}
    for i, name in enumerate(names, 1):
        hashes[name] = sha((ROOT / name).read_bytes())
        if i % 3000 == 0:
            print(json.dumps({'baseline_hashed': i, 'total': len(names)}), flush=True)
    result = {'commit': BASE, 'tag': 'archive-phase8-20261016', 'count': len(names), 'files': hashes}
    immutable(ROOT / 'results/phase9/provenance/baseline.json', jb(result))
    return len(names)


def freeze(stage):
    if stage == 'data':
        verify_freeze('production')
    patterns = ('src/tsg/*.py', 'scripts/*phase9*.py', 'tests/*v9*.py',
                'docs/phase9_design.md', 'docs/phase9_analysis_plan.md',
                'docs/phase9_protocol.md', 'docs/phase9_recovery.md', 'docs/superpowers/plans/*phase9*.md')
    paths = {p for pat in patterns for p in ROOT.glob(pat) if p.is_file()}
    paths = {p for p in paths if p.name not in {'build_phase9_heldout.py', 'test_reference_v9.py',
             'analyze_phase9.py', 'plot_phase9.py', 'verify_phase9.py', 'test_analysis_v9.py'}}
    if stage == 'data':
        paths.update(p for p in (ROOT / 'data/phase9').rglob('*') if p.is_file())
        paths.add(ROOT / 'scripts/build_phase9_heldout.py')
    value = {'stage': stage, 'registration': 'local prospective freeze, not external preregistration',
             'files': {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(paths)}}
    immutable(ROOT / f'results/phase9/provenance/{stage}_freeze.json', jb(value))
    return len(value['files'])


def verify_freeze(stage='data'):
    value = json.loads((ROOT / f'results/phase9/provenance/{stage}_freeze.json').read_text())
    for p, h in value['files'].items():
        if sha((ROOT / p).read_bytes()) != h:
            raise ValueError('FROZEN_CHANGED:' + p)
    return value


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['baseline', 'production', 'data'])
    args = p.parse_args()
    print(json.dumps({'stage': args.stage, 'files': baseline() if args.stage == 'baseline' else freeze(args.stage)}), flush=True)
