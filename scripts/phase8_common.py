"""Immutable Phase 8 input/provenance helpers, no experiment semantics."""
import json
from phase6_common import ROOT,sha,jb,rb,immutable,read_rows

CAP=29.551575125
MODELS=('gpt-6-luna','gpt-4.1-mini')


def cases():
    old=[{**c,'split':'regression'} for c in read_rows(ROOT/'data/phase7/heldout.jsonl')]
    return old+read_rows(ROOT/'data/phase8/heldout.jsonl')


def baseline():
    names=(ROOT/'work/phase8-baseline-names.txt').read_text(encoding='utf-8-sig').splitlines()
    value={'commit':'0f1aefcd6ed7986b0c4035be36f60967efab4a1c','count':len(names),
           'files':{n:sha((ROOT/n).read_bytes()) for n in names}}
    immutable(ROOT/'results/phase8/provenance/baseline.json',jb(value))
    return len(names)


def freeze(stage):
    patterns=('src/tsg/*.py','scripts/*.py','tests/*v8*.py','tests/*phase8*.py','configs/*requirements*.txt',
              'docs/phase8_design.md','docs/phase8_analysis_plan.md','docs/superpowers/plans/*phase8*.md')
    paths=[p for pat in patterns for p in ROOT.glob(pat) if p.is_file()]
    # Analysis implementation may finish while acquisition runs; its prospective
    # questions/estimands are frozen above. Freeze its bytes in final release.
    paths=[p for p in paths if p.name not in {'analyze_phase8.py','test_analysis_v8.py'}]
    if stage=='data': paths.extend(p for p in (ROOT/'data/phase8').rglob('*') if p.is_file())
    value={'stage':stage,'registration':'local prospective freeze, not external preregistration',
           'files':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(set(paths))}}
    immutable(ROOT/f'results/phase8/provenance/{stage}_freeze.json',jb(value))
    return len(value['files'])


def verify_freeze(stage='data'):
    value=json.loads((ROOT/f'results/phase8/provenance/{stage}_freeze.json').read_text())
    for p,h in value['files'].items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('FROZEN_CHANGED:'+p)
    return value


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['baseline','production','data']);a=p.parse_args()
    print(json.dumps({'action':a.action,'files':baseline() if a.action=='baseline' else freeze(a.action)}),flush=True)
