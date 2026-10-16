"""Append-only Phase 11 provenance and shared deterministic serialization."""
import json
from phase10_common import write_chunks, read_chunks
from phase6_common import ROOT, sha, jb, rb, immutable, read_rows

BASE = 'caf5ee5430e011044c478ec8fed7013545978922'
CAP = 29.551575125
CAMPAIGN_CAP = 8.0
MODELS = ('gpt-6-luna', 'gpt-4.1-mini')

def baseline():
    names=(ROOT/'work/phase11-baseline-names.txt').read_text(encoding='utf-8-sig').splitlines()
    value={'commit':BASE,'count':len(names),'files':{n:sha((ROOT/n).read_bytes()) for n in names}}
    immutable(ROOT/'results/phase11/provenance/baseline.json',jb(value))
    immutable(ROOT/'results/phase11/provenance/archive.json',jb({
        'commit':BASE,'tag':'archive-phase10-20261017',
        'tag_object':'ae5cbc189542349900a66427e7ab0b1a8b7f039f','remote_peeled_verified':True,
        'repository':'https://github.com/victorcao1104/taskskillguard-research','private':True}))
    return value['count']

def freeze(stage):
    if stage=='data':verify_freeze('production')
    required=('src/tsg/certificate_v11.py','src/tsg/commit_v11.py','src/tsg/protocol_v11.py',
        'scripts/run_phase11.py','scripts/experiment_phase11.py','docs/phase11_design.md',
        'docs/phase11_theory.md','docs/phase11_analysis_plan.md','tests/test_acquisition_v11.py',
        'tests/test_certificate_theorems_v11.py')
    for name in required:
        if not (ROOT/name).is_file():raise ValueError('REQUIRED_FREEZE_FILE_MISSING:'+name)
    patterns=('src/tsg/*_v11.py','scripts/phase11_common.py','scripts/run_phase11.py',
        'scripts/experiment_phase11.py','tests/test_certificate_v11.py','tests/test_protocol_v11.py',
        'tests/test_commit_v11.py','tests/test_certificate_theorems_v11.py','tests/test_acquisition_v11.py',
        'docs/phase11_design.md','docs/phase11_theory.md','docs/phase11_analysis_plan.md',
        'docs/phase11_protocol.md','docs/phase11_commit.md','docs/superpowers/plans/*phase11*.md')
    paths={p for pat in patterns for p in ROOT.glob(pat) if p.is_file()}
    paths.update((ROOT/'src/tsg').glob('*.py'))
    if stage=='data':
        paths.add(ROOT/'scripts/build_phase11_heldout.py')
        paths.add(ROOT/'scripts/build_phase11_challenge.py')
        paths.update(p for p in (ROOT/'data/phase11').rglob('*') if p.is_file())
    value={'stage':stage,'registration':'local prospective freeze, not external preregistration',
        'files':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(paths)}}
    immutable(ROOT/f'results/phase11/provenance/{stage}_freeze.json',jb(value))
    return len(paths)

def verify_freeze(stage='data'):
    v=json.loads((ROOT/f'results/phase11/provenance/{stage}_freeze.json').read_text(encoding='utf-8'))
    for p,h in v['files'].items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('FROZEN_CHANGED:'+p)
    return v

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['baseline','production','data'])
    a=p.parse_args();print(json.dumps({'stage':a.stage,'files':baseline() if a.stage=='baseline' else freeze(a.stage)}))
