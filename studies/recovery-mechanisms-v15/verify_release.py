"""Check preserved evidence, complete grids, budget and publication hygiene."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

import strict_state
import transport_recovery
from rm15.provider import Provider

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
BASELINE='74a06d2f3345ed8e2eb7768d36ba66d2e9ae7688'


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_bytes())
def gz(path):return json.loads(gzip.decompress(path.read_bytes()))


def main():
    strict_state.check_freeze();recovery=transport_recovery.check()
    amendment=read(ROOT/'provenance/runtime_error_amendment.json')
    for name,expected_hash in amendment['files'].items():assert sha((ROOT/name).read_bytes())==expected_hash
    expected={j['id'] for j in strict_state.jobs()}
    corrected={r['job']['id']:r for r in map(gz,(ROOT/'results/strict_state_recovered/episodes').glob('*.json.gz'))}
    assert set(corrected)==expected
    original=transport_recovery.originals()
    assert len(list((ROOT/'results/episodes').glob('formal--*.json.gz')))==864
    assert len(list((ROOT/'results/episodes').glob('pilot*.json.gz')))==88
    for name,record in corrected.items():
        if name not in recovery['affected_ids']:assert record==original[name]
        else:assert record['acquisition_recovery']['reason']=='transport_error'
    outside=subprocess.check_output(['git','diff','--name-only',BASELINE,'--','.',':!studies/recovery-mechanisms-v15'],cwd=REPO,text=True).splitlines()
    assert not outside, 'OLD_TRACKED_FILES_CHANGED'
    old=(REPO/'studies/goal-recovery-v14/api/budget.jsonl').read_bytes()
    ledger=(ROOT/'api/budget.jsonl').read_bytes();assert ledger.startswith(old)
    old_entries={r['reservation_id']:r for r in map(json.loads,old.decode().splitlines())}
    latest={r['reservation_id']:r for r in map(json.loads,ledger.decode().splitlines())}
    exposure=sum(r.get('cost_usd',r['reserved_usd']) for r in latest.values())
    inherited=sum(r.get('cost_usd',r['reserved_usd']) for r in old_entries.values())
    new=[r for key,r in latest.items() if key not in old_entries]
    provider=Provider(ROOT,live=False);assert abs(exposure-provider.exposure)<1e-8
    assert exposure<=provider.budget.limit
    requests=list((ROOT/'api/requests').glob('*.json'));hashes=[];raw_counts=collections.Counter();campaigns=collections.Counter()
    for path in requests:
        request=read(path);fingerprint=request['expected_request_hash'];hashes.append(fingerprint)
        assert path.stem==request['job_id']
        raw=read(ROOT/'api/raw'/(fingerprint+'.json'))
        assert raw['request_hash']==fingerprint
        raw_counts[raw['status']]+=1;campaigns[request['job_id'].split('--')[0]]+=1
        assert raw['reservation_id'] in latest
        dispatch=read(ROOT/'api/dispatch'/(request['job_id']+'.json'))
        assert fingerprint in json.dumps(dispatch)
    assert len(hashes)==len(set(hashes)), 'DUPLICATE_REQUEST_FINGERPRINT'
    # A format scan is an additional hygiene check, not a proof of absence of all secrets.
    hits=[];scanned=0
    for path in ROOT.rglob('*'):
        if not path.is_file() or any(part in ('__pycache__','.pytest_cache') for part in path.parts):continue
        if path.suffix not in ('.json','.jsonl','.py','.md','.txt','.csv'):continue
        data=path.read_bytes();scanned+=1
        if re.search(rb'(?:sk-proj-|sk-svcacct-|ghp_|github_pat_)[A-Za-z0-9_-]{32,}',data):hits.append(str(path.relative_to(ROOT)))
    assert not hits, 'CREDENTIAL_FORMAT_HIT'
    primary=read(ROOT/'reports/replay_verification.json');strict=read(ROOT/'reports/strict_replay_verification.json')
    assert primary['episodes']==864 and strict['episodes']==512
    report={'baseline_commit':BASELINE,'primary_freeze_commit':'333d55cca','strict_freeze_commit':'2a6a87bfd','environment_recovery_freeze_commit':'d3d46c656',
        'formal_episodes':864,'strict_first_acquisition_episodes':512,'strict_recovered_episodes':512,'environment_reacquired_episodes':len(recovery['affected_ids']),'pilot_episodes':88,
        'main_world_replays':primary['world_replays'],'strict_world_replays':strict['world_replays'],'replay_network_requests':0,
        'old_tracked_files_preserved':True,'frozen_code_verified':True,'old_ledger_prefix_preserved':True,'old_ledger_sha256':sha(old),'ledger_sha256':sha(ledger),
        'inherited_exposure_usd':inherited,'cumulative_exposure_usd':exposure,'cap_usd':provider.budget.limit,'new_exposure_usd':exposure-inherited,'remaining_upper_usd':provider.budget.limit-exposure,
        'new_settled_usage_upper_usd':sum(r.get('cost_usd',0) for r in new if r['status']=='settled'),
        'new_unsettled_reservation_upper_usd':sum(r['reserved_usd'] for r in new if r['status']!='settled'),
        'new_unsettled_reservation_count':sum(r['status']!='settled' for r in new),'invoice':False,
        'request_files':len(requests),'request_prefix_counts':dict(campaigns),'raw_status_counts':dict(raw_counts),'unique_request_fingerprints':True,
        'credential_format_scan_files':scanned,'credential_format_hits':0,'scan_limitation':'Known credential formats only; not a general sensitivity classifier',
        'real_skills_used':False,'human_annotations_used':False}
    (ROOT/'reports/final_integrity.json').write_bytes((json.dumps(report,sort_keys=True,indent=2)+'\n').encode())
    print(json.dumps(report))


if __name__=='__main__':main()
