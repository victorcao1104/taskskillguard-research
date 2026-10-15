"""Offline reproduction and byte preservation; never calls provider or Docker."""
import argparse
import json
import sys
from phase7_common import ROOT,cases,read_rows,sha,jb,rb,immutable,verify_freeze
sys.path.insert(0,str(ROOT/'src'))
from run_phase7 import CAP
from run_phase5 import price_job
from tsg.budget_v4 import BudgetV4
from tsg.protocol_v7 import parse_record
from tsg.evidence_v7 import check

def verify(manifest=True):
    baseline=json.loads((ROOT/'results/phase7/provenance/baseline.json').read_text())
    for p,h in baseline['files'].items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('OLD_FILE_CHANGED:'+p)
    from run_phase7_v2 import amendment
    amendment()
    frozen=verify_freeze();cs={c['case_id']:c for c in cases()}
    prefix=(ROOT/'results/phase6/challenge/api/budget.jsonl').read_bytes()
    ledger=ROOT/'results/phase7/api/budget.jsonl'
    if not ledger.read_bytes().startswith(prefix):raise ValueError('LEDGER_PREFIX_CHANGED')
    budget=BudgetV4(ledger,CAP)
    if budget.total_cost>CAP:raise ValueError('BUDGET_EXCEEDED')
    jobs=read_rows(ROOT/'results/phase7/acquisition/jobs.jsonl');obs=read_rows(ROOT/'results/phase7/api/observations.jsonl')
    index={r['job_id']:r for r in obs}
    if len(jobs)!=480 or len(obs)!=480 or set(index)!={j['job_id'] for j in jobs}:raise ValueError('INCOMPLETE_MODEL_GRID')
    acquisition=json.loads((ROOT/'results/phase7/acquisition/manifest.json').read_text())
    if sha(rb(jobs))!=acquisition['jobs_sha256']:raise ValueError('GRID_HASH_CHANGED')
    for j in jobs:
        r=index[j['job_id']];raw=json.loads((ROOT/r['raw_ref']).read_text(encoding='utf-8'))
        expected=price_job(j)['expected_request_hash']
        if expected!=r['request_hash'] or expected!=raw['request_hash']:raise ValueError('REQUEST_HASH_CHANGED')
        if 'request' in raw and sha(json.dumps({'request':raw['request'],'replicate':raw['replicate']},sort_keys=True,ensure_ascii=False).encode())!=expected:
            raise ValueError('RAW_REQUEST_CHANGED')
        if parse_record(raw,j['ids'],j['view'])!=r['parsed']:raise ValueError('PARSE_MISMATCH')
        if j['view']=='B2' and check(cs[j['case_id']],r['parsed'].get('prediction'))!=r['certificate']:raise ValueError('CERTIFICATE_MISMATCH')
    from experiment_phase7 import recovery_jobs,integrated_jobs
    from experiment_phase7_v2 import semantics
    semantics()
    from tsg.recovery_v7 import execute
    totals={}
    for track, builder in [('recovery',recovery_jobs),('integrated',integrated_jobs)]:
        grid=read_rows(ROOT/f'results/phase7/{track}/jobs.jsonl');vm=read_rows(ROOT/f'results/phase7/{track}/vm_results.jsonl')
        if grid!=builder() or len(vm)!=len(grid):raise ValueError('EXECUTION_GRID_CHANGED')
        if vm!=read_rows(ROOT/f'results/phase7/{track}/container_results.jsonl'):raise ValueError('CONTAINER_MISMATCH')
        for j,r in zip(grid,vm):
            if r['runner_status']!='completed' or execute(**j['args'])!=r['result']:raise ValueError('EXECUTION_REPRODUCTION_MISMATCH')
            v=r['result']
            if v['unauthorized_effects'] or v['duplicate_effects'] or v['charged_calls']>j['args']['quota'] or v['attempts']>4:
                raise ValueError('SAFETY_INVARIANT_FAILED')
        totals[track]=len(vm)
    from analyze_phase7 import main as analyze_saved
    analyze_saved([])
    hashes={}
    if manifest:
        hashes=json.loads((ROOT/'results/phase7/provenance/release_hashes.json').read_text())['files']
        for p,h in hashes.items():
            if sha((ROOT/p).read_bytes())!=h:raise ValueError('RELEASE_HASH_CHANGED:'+p)
    return {'status':'pass','baseline_files_unchanged':len(baseline['files']),'frozen_files':len(frozen['source_sha256']),
            'model_conditions':len(obs),'unique_requests':len({r['request_hash'] for r in obs}),
            'executions':totals,'cumulative_upper_usd':budget.total_cost,'remaining_usd':CAP-budget.total_cost,'release_files':len(hashes)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze-release',action='store_true');a=p.parse_args()
    if a.freeze_release:
        verify(False)
        paths=[]
        for directory in ('data/phase7','results/phase7'):
            paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file())
        for directory in ('src/tsg','scripts','tests','docs','.github/workflows'):
            paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and ('phase7' in p.name or '_v7' in p.name) and '__pycache__' not in p.parts)
        paths.append(ROOT/'PHASE7.md')
        excluded={'results/phase7/provenance/release_hashes.json','results/phase7/provenance/release_verification.json'}
        files={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(set(paths)) if p.relative_to(ROOT).as_posix() not in excluded}
        immutable(ROOT/'results/phase7/provenance/release_hashes.json',jb({'files':files,'count':len(files)}))
    audit=verify();immutable(ROOT/'results/phase7/provenance/release_verification.json',jb(audit));print(json.dumps(audit),flush=True)
