"""Offline verification of inherited bytes, requests, parser results and executions."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.reasoning_v5 import parse_record
from tsg.budget_v4 import BudgetV4
from tsg.recovery_v5 import load_preserved, build_grid
from prepare_phase4 import sha, json_bytes, immutable
from run_phase5 import CAP, price_job, read_rows

def verify_job(job, observation, raw):
    expected=price_job(job)['expected_request_hash']
    if any(h!=expected for h in (job['expected_request_hash'],observation['request_hash'],raw['request_hash'])):
        raise ValueError('JOB_HASH_MISMATCH')
    if 'request' in raw:
        digest=sha(json.dumps({'request':raw['request'],'replicate':raw['replicate']},sort_keys=True,ensure_ascii=False).encode())
        if digest!=expected: raise ValueError('RAW_REQUEST_HASH_MISMATCH')
    elif raw['status']!='interrupted_unknown':
        raise ValueError('RAW_REQUEST_MISSING')
    checked=parse_record(raw,job['ids'])
    for key in ('protocol_valid','diagnostic_codes','judgments','by_id'):
        if checked.get(key)!=observation['parsed'].get(key):
            raise ValueError('PARSED_RESPONSE_MISMATCH:'+key)
    return True

def _read(path): return json.loads(path.read_text(encoding='utf-8'))

def verify(root=ROOT, *, require_release_hashes=True):
    root=Path(root)
    baseline=_read(root/'results/phase5/provenance/baseline.json')
    for path,digest in baseline['files'].items():
        if sha((root/path).read_bytes())!=digest: raise ValueError('INHERITED_FILE_CHANGED:'+path)
    acq=root/'results/phase5/acquisition_v2'
    manifest=_read(acq/'manifest.json')
    if sha((acq/'jobs.jsonl').read_bytes())!=manifest['jobs_sha256']: raise ValueError('JOB_GRID_CHANGED')
    for p,h in manifest['source_sha256'].items():
        if sha((root/p).read_bytes())!=h: raise ValueError('ACQUISITION_SOURCE_CHANGED:'+p)
    jobs=read_rows(acq/'jobs.jsonl'); obs=read_rows(root/'results/phase5/api/observations.jsonl')
    index={o['job_id']:o for o in obs}
    if len(jobs)!=588 or len(obs)!=588 or set(index)!={j['job_id'] for j in jobs}: raise ValueError('INCOMPLETE_API_GRID')
    dispatches=[_read(p) for p in (root/'results/phase5/api/dispatch').glob('*.json')]
    marker_hashes={d['request_hash'] for d in dispatches}
    for job in jobs:
        observation=index[job['job_id']]
        raw=_read(root/observation['raw_ref'])
        verify_job(job,observation,raw)
        if _read(root/f'results/phase5/api/jobs/{job["job_id"]}.json')!=observation: raise ValueError('WRAPPER_AGGREGATE_MISMATCH')
        # Identical auto/oracle payloads share one raw response/cache entry.
        # At least one durable dispatch marker must establish that raw attempt.
        if job['expected_request_hash'] not in marker_hashes: raise ValueError('DISPATCH_MARKER_MISSING')
    follow=root/'results/phase5_q017'
    follow_manifest=_read(follow/'acquisition/manifest.json')
    if sha((follow/'acquisition/jobs.jsonl').read_bytes())!=follow_manifest['jobs_sha256']:
        raise ValueError('FOLLOWUP_GRID_CHANGED')
    for path,h in follow_manifest['source_sha256'].items():
        if sha((root/path).read_bytes())!=h: raise ValueError('FOLLOWUP_SOURCE_CHANGED:'+path)
    follow_jobs=read_rows(follow/'acquisition/jobs.jsonl')
    follow_obs=read_rows(follow/'api/observations.jsonl'); follow_index={o['job_id']:o for o in follow_obs}
    follow_markers={_read(p)['request_hash'] for p in (follow/'api/dispatch').glob('*.json')}
    if len(follow_jobs)!=30 or len(follow_obs)!=30 or set(follow_index)!={j['job_id'] for j in follow_jobs}:
        raise ValueError('INCOMPLETE_FOLLOWUP_GRID')
    for job in follow_jobs:
        observation=follow_index[job['job_id']]
        verify_job(job,observation,_read(root/observation['raw_ref']))
        if job['expected_request_hash'] not in follow_markers: raise ValueError('FOLLOWUP_DISPATCH_MARKER_MISSING')
        if _read(follow/f'api/jobs/{job["job_id"]}.json')!=observation: raise ValueError('FOLLOWUP_WRAPPER_MISMATCH')
    ledger=root/'results/phase5/api/budget.jsonl'
    old=(root/'results/phase4/api/budget.jsonl').read_bytes()
    if not ledger.read_bytes().startswith(old): raise ValueError('BUDGET_PREFIX_CHANGED')
    budget=BudgetV4(ledger,CAP)
    if budget.total_cost>CAP: raise ValueError('BUDGET_EXCEEDED')
    old_budget=BudgetV4(root/'results/phase4/api/budget.jsonl',CAP)
    if len(set(budget.entries)-set(old_budget.entries))!=534: raise ValueError('UNIQUE_RESERVATION_COUNT_MISMATCH')
    recovery=root/'results/phase5/recovery_primary'
    frozen=_read(recovery/'frozen_grid.json'); runs=_read(recovery/'runs.json')
    run_index={r['run_id']:r for r in runs}; grid=build_grid()
    if len(runs)!=180 or set(run_index)!={j['run_id'] for j in grid}: raise ValueError('INCOMPLETE_RECOVERY_GRID')
    evidence={j['run_id']:j['evidence_directory'] for j in frozen['jobs']}
    for job in grid:
        saved=load_preserved(job,recovery/evidence[job['run_id']])
        if saved!=run_index[job['run_id']]: raise ValueError('RECOVERY_RESCORE_OR_HASH_MISMATCH')
    packet=root/'data/phase5/human_review'
    a,b=read_rows(packet/'rater_A_v2.jsonl'),read_rows(packet/'rater_B_v2.jsonl')
    if len(a)!=832 or a!=b or len({r['review_id'] for r in a})!=832: raise ValueError('HUMAN_PACKET_MISMATCH')
    if any(r['labels'] or r['notes'] for r in a): raise ValueError('HUMAN_LABELS_NOT_BLANK')
    packaging=_read(packet/'omitted_files_packaging.json')
    compressed=(packet/'omitted_files.jsonl.gz').read_bytes()
    omission_bytes=gzip.decompress(compressed)
    if sha(compressed)!=packaging['compressed_sha256'] or sha(omission_bytes)!=packaging['uncompressed_sha256']:
        raise ValueError('OMISSION_PACKAGING_HASH_MISMATCH')
    if len(omission_bytes.splitlines())!=2447: raise ValueError('OMISSION_MANIFEST_MISMATCH')
    if (packet/'omitted_files.jsonl').exists() and (packet/'omitted_files.jsonl').read_bytes()!=omission_bytes:
        raise ValueError('OMISSION_LOCAL_BYTES_MISMATCH')
    hashes=root/'results/phase5/provenance/release_hashes.json'
    checked_new=0
    if hashes.exists():
        for path,h in _read(hashes)['files'].items():
            if sha((root/path).read_bytes())!=h: raise ValueError('RELEASE_HASH_MISMATCH:'+path)
            checked_new+=1
    elif require_release_hashes:
        raise ValueError('RELEASE_HASH_MANIFEST_MISSING')
    return {'inherited_files_unchanged':len(baseline['files']),'new_files_verified':checked_new,
            'api_records_rehashed_reparsed':len(jobs),'separate_followup_records_rehashed_reparsed':len(follow_jobs),
            'main_unique_request_hashes':len({j['expected_request_hash'] for j in jobs}),
            'followup_unique_request_hashes':len({j['expected_request_hash'] for j in follow_jobs}),
            'recovery_records_rehashed_rescored':180,
            'human_items_per_rater':832,'human_labels':0,'cumulative_upper_usd':budget.total_cost,
            'cap_usd':CAP,'remaining_usd':CAP-budget.total_cost,'verified':True}

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--pre-release',action='store_true')
    parser.add_argument('--save',action='store_true'); args=parser.parse_args()
    report=verify(require_release_hashes=not args.pre_release)
    if args.save: immutable(ROOT/'results/phase5/provenance/release_verification.json',json_bytes(report))
    print(json.dumps(report),flush=True)
