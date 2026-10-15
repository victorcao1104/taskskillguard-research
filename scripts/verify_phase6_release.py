"""Offline reproduction and integrity gate; no API, Docker or real corpus access."""
import argparse
import json
import sys
from phase6_common import ROOT,sha,jb,rb,read_rows,cases,immutable
sys.path.insert(0,str(ROOT/'src'))
from tsg.budget_v4 import BudgetV4
from tsg.protocol_v6 import parse_record
from run_phase6 import CAP
from run_phase5 import price_job


def verify(require_manifest=True):
    base=json.loads((ROOT/'results/phase6/provenance/baseline.json').read_text())
    for p,h in base['files'].items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('BASELINE_CHANGED:'+p)
    frozen=json.loads((ROOT/'results/phase6/provenance/freeze.json').read_text())
    for p,h in frozen['source_sha256'].items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('FROZEN_SOURCE_CHANGED:'+p)
    old=(ROOT/'results/phase5/api/budget.jsonl').read_bytes()
    if not (ROOT/'results/phase6/api/budget.jsonl').read_bytes().startswith(old):raise ValueError('LEDGER_PREFIX_CHANGED')
    budget=BudgetV4(ROOT/'results/phase6/api/budget.jsonl',CAP)
    if budget.total_cost>CAP:raise ValueError('BUDGET_EXCEEDED')
    jobs=read_rows(ROOT/'results/phase6/acquisition/jobs.jsonl')
    obs=read_rows(ROOT/'results/phase6/api/observations.jsonl');index={r['job_id']:r for r in obs}
    if len(jobs)!=336 or len(obs)!=336 or set(index)!={j['job_id'] for j in jobs}:raise ValueError('INCOMPLETE_MODEL_GRID')
    manifest=json.loads((ROOT/'results/phase6/acquisition/manifest.json').read_text())
    if sha(rb(jobs))!=manifest['jobs_sha256']:raise ValueError('ACQUISITION_GRID_CHANGED')
    for j in jobs:
        r=index[j['job_id']];raw=json.loads((ROOT/r['raw_ref']).read_text(encoding='utf-8'))
        expected=price_job(j)['expected_request_hash']
        if expected!=r['request_hash'] or expected!=raw['request_hash']:raise ValueError('REQUEST_HASH_MISMATCH')
        if 'request' in raw:
            if sha(json.dumps({'request':raw['request'],'replicate':raw['replicate']},sort_keys=True,ensure_ascii=False).encode())!=expected:raise ValueError('RAW_REQUEST_CHANGED')
        if parse_record(raw,j['ids'])!=r['parsed']:raise ValueError('PROTOCOL_REPARSE_MISMATCH')
    from tsg.runtime_v6 import execute
    from tsg.truth_v6 import evaluate_case
    truths=read_rows(ROOT/'results/phase6/first/truth.jsonl')
    if [evaluate_case(c) for c in cases()]!=truths:raise ValueError('TRUTH_REPRODUCTION_MISMATCH')
    totals={}
    for track,n in [('recovery',2304),('integrated',1440)]:
        grid=read_rows(ROOT/f'results/phase6/{track}/jobs.jsonl')
        vm=read_rows(ROOT/f'results/phase6/{track}/vm_results.jsonl')
        container=read_rows(ROOT/f'results/phase6/{track}/container_results.jsonl')
        if len(grid)!=n or len(vm)!=n or container!=vm:raise ValueError('EXECUTION_GRID_MISMATCH:'+track)
        for j,r in zip(grid,vm):
            if r['runner_status']!='completed':raise ValueError('EXECUTION_RUNNER_ERROR')
            if execute(**j['args'])!=r['result']:raise ValueError('EXECUTION_REPRODUCTION_MISMATCH')
            if r['result']['unauthorized_effects'] or r['result']['charged_calls']>j['args']['quota']:raise ValueError('RUNTIME_INVARIANT_FAILED')
        totals[track]=n
    from run_phase6_challenge import checkfreeze,cases as challenge_cases
    from tsg.selection_v6 import execute_selection
    checkfreeze()
    supp=ROOT/'results/phase6/challenge'
    if not (supp/'api/budget.jsonl').read_bytes().startswith((ROOT/'results/phase6/api/budget.jsonl').read_bytes()):raise ValueError('CHALLENGE_LEDGER_PREFIX_CHANGED')
    latest=BudgetV4(supp/'api/budget.jsonl',CAP)
    if latest.total_cost>CAP:raise ValueError('LATEST_BUDGET_EXCEEDED')
    sjobs=read_rows(supp/'acquisition/jobs.jsonl');sobs=read_rows(supp/'api/observations.jsonl')
    if sha(rb(sjobs))!=json.loads((supp/'acquisition/manifest.json').read_text())['jobs_sha256']:raise ValueError('CHALLENGE_ACQUISITION_CHANGED')
    sindex={r['job_id']:r for r in sobs}
    if len(sjobs)!=96 or len(sobs)!=96 or set(sindex)!={j['job_id'] for j in sjobs}:raise ValueError('CHALLENGE_MODEL_GRID_INCOMPLETE')
    for j in sjobs:
        r=sindex[j['job_id']];raw=json.loads((ROOT/r['raw_ref']).read_text(encoding='utf-8'))
        expected=price_job(j)['expected_request_hash']
        if expected!=r['request_hash'] or expected!=raw['request_hash']:raise ValueError('CHALLENGE_REQUEST_HASH_MISMATCH')
        if 'request' in raw and sha(json.dumps({'request':raw['request'],'replicate':raw['replicate']},sort_keys=True,ensure_ascii=False).encode())!=expected:raise ValueError('CHALLENGE_RAW_CHANGED')
        if parse_record(raw,j['ids'])!=r['parsed']:raise ValueError('CHALLENGE_PROTOCOL_MISMATCH')
    if [evaluate_case(c) for c in challenge_cases()]!=read_rows(supp/'first/truth.jsonl'):raise ValueError('CHALLENGE_TRUTH_MISMATCH')
    for track,n in [('recovery',1152),('integrated',480)]:
        grid=read_rows(supp/track/'jobs.jsonl');vm=read_rows(supp/track/'vm_results.jsonl')
        if len(grid)!=n or len(vm)!=n or read_rows(supp/track/'container_results.jsonl')!=vm:raise ValueError('CHALLENGE_EXECUTION_GRID_MISMATCH')
        for j,r in zip(grid,vm):
            fn=execute_selection if j['args']['mode'] in ('first_feasible','search_equal') else execute
            if r['runner_status']!='completed' or fn(**j['args'])!=r['result']:raise ValueError('CHALLENGE_EXECUTION_REPRODUCTION_MISMATCH')
            if r['result']['unauthorized_effects'] or r['result']['charged_calls']>j['args']['quota']:raise ValueError('CHALLENGE_INVARIANT_FAILED')
        totals['challenge_'+track]=n
    release=ROOT/'results/phase6/provenance/release_hashes_v2.json'
    if require_manifest:
        hashes=json.loads(release.read_text())['files']
        for p,h in hashes.items():
            if sha((ROOT/p).read_bytes())!=h:raise ValueError('RELEASE_FILE_CHANGED:'+p)
    else:hashes={}
    return {'baseline_files_unchanged':len(base['files']),'frozen_files':len(frozen['source_sha256']),
            'conditions':totals,'model_conditions':len(jobs),'unique_requests':len({r['request_hash'] for r in obs}),
            'challenge_model_conditions':len(sjobs),'challenge_unique_requests':len({r['request_hash'] for r in sobs}),
            'cumulative_upper_usd':latest.total_cost,'remaining_usd':CAP-latest.total_cost,
            'release_files':len(hashes),'status':'pass'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze-release',action='store_true');a=p.parse_args()
    if a.freeze_release:
        audit=verify(False)
        base=json.loads((ROOT/'results/phase6/provenance/baseline.json').read_text())['files']
        paths=[]
        for directory in ('data/phase6','results/phase6'):
            paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file())
        for directory in ('src/tsg','scripts','tests','docs','.github/workflows'):
            paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and ('phase6' in p.name or '_v6' in p.name))
        paths.extend([ROOT/'PHASE6.md',ROOT/'docs/superpowers/plans/2026-10-16-phase6-synthetic.md'])
        excluded={'results/phase6/provenance/release_hashes_v2.json','results/phase6/provenance/release_verification_v2.json'}
        rels=sorted({p.relative_to(ROOT).as_posix() for p in paths if p.suffix!='.pyc'}-set(base)-excluded)
        immutable(ROOT/'results/phase6/provenance/release_hashes_v2.json',jb({'files':{p:sha((ROOT/p).read_bytes()) for p in rels},'count':len(rels)}))
    result=verify()
    if a.freeze_release:immutable(ROOT/'results/phase6/provenance/release_verification_v2.json',jb(result))
    print(json.dumps(result))
