"""Immutable Phase 10 provenance; old results are never rewritten."""
import json
from phase6_common import ROOT, sha, jb, rb, immutable, read_rows

CAP = 29.551575125
CAMPAIGN_CAP = 6.0
MODELS = ('gpt-6-luna', 'gpt-4.1-mini')
BASE = '738c1dbe60a42c941662878e849a9432d4543c86'


def write_chunks(directory, rows, size=500):
    directory = ROOT / directory
    for i, start in enumerate(range(0, len(rows), size), 1):
        immutable(directory / f'{i:04}.jsonl', rb(rows[start:start+size]))
    immutable(directory / 'manifest.json', jb({'rows': len(rows), 'chunks': (len(rows)+size-1)//size,
              'sha256': sha(rb(rows)), 'chunk_size': size}))


def read_chunks(directory):
    directory = ROOT / directory
    manifest = json.loads((directory / 'manifest.json').read_text())
    rows = [r for i in range(1, manifest['chunks']+1) for r in read_rows(directory / f'{i:04}.jsonl')]
    assert len(rows) == manifest['rows'] and sha(rb(rows)) == manifest['sha256']
    return rows


def cases():
    return [{**c, 'split': 'regression'} for phase in (7, 8, 9)
            for c in read_rows(ROOT / f'data/phase{phase}/heldout.jsonl')] + read_rows(ROOT / 'data/phase10/heldout.jsonl')


def baseline():
    names = (ROOT / 'work/phase10-baseline-names.txt').read_text(encoding='utf-8-sig').splitlines()
    hashes = {}
    for i, n in enumerate(names, 1):
        hashes[n] = sha((ROOT / n).read_bytes())
        if i % 4000 == 0: print(json.dumps({'baseline_hashed': i}), flush=True)
    value = {'commit': BASE, 'tag': 'archive-phase9-20261016', 'count': len(names), 'files': hashes}
    immutable(ROOT / 'results/phase10/provenance/baseline.json', jb(value))
    immutable(ROOT / 'results/phase10/provenance/archive.json', jb({
        'commit': BASE, 'tag': 'archive-phase9-20261016',
        'tag_object': 'f725cada2933f92906ff4e805e68bbb7666ac509', 'remote_verified': True,
        'repository': 'https://github.com/victorcao1104/taskskillguard-research', 'private': True}))
    return len(names)


def freeze(stage):
    if stage == 'data': verify_freeze('production')
    pats = ('src/tsg/*.py', 'scripts/*phase10*.py', 'tests/*v10*.py',
            'docs/phase10_design.md', 'docs/phase10_protocol.md', 'docs/phase10_recovery.md',
            'docs/superpowers/plans/*phase10*.md')
    excluded = {'build_phase10_heldout.py', 'test_reference_v10.py', 'analyze_phase10.py',
                'plot_phase10.py', 'verify_phase10.py', 'test_analysis_v10.py'}
    paths = {p for pat in pats for p in ROOT.glob(pat) if p.is_file() and p.name not in excluded}
    if stage == 'data':
        paths.add(ROOT / 'scripts/build_phase10_heldout.py')
        paths.update(p for p in (ROOT / 'data/phase10').rglob('*') if p.is_file())
    value = {'stage': stage, 'registration': 'local prospective freeze; not external preregistration',
             'files': {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(paths)}}
    immutable(ROOT / f'results/phase10/provenance/{stage}_freeze.json', jb(value))
    return len(value['files'])


def verify_freeze(stage='data'):
    value = json.loads((ROOT / f'results/phase10/provenance/{stage}_freeze.json').read_text())
    for path, digest in value['files'].items():
        if sha((ROOT / path).read_bytes()) != digest: raise ValueError('FROZEN_CHANGED:' + path)
    return value


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('stage', choices=['baseline','production','data'])
    a=p.parse_args();print(json.dumps({'stage':a.stage,'files':baseline() if a.stage=='baseline' else freeze(a.stage)}),flush=True)
