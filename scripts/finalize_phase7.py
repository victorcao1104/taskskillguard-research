"""Rebuild aggregate artifacts from complete saved jobs, with no provider calls."""
from collections import Counter
import json
import sys
from phase7_common import ROOT,cases,read_rows,sha,jb,rb,immutable,verify_freeze
sys.path.insert(0,str(ROOT/'src'))
from tsg.budget_v7_locked import BudgetV7Locked
from tsg.protocol_v7 import parse_record
from tsg.evidence_v7 import check
from run_phase7 import CAP
from run_phase7_v2 import amendment

def finalize():
    verify_freeze();amendment()
    cs={c['case_id']:c for c in cases()}
    jobs=read_rows(ROOT/'results/phase7/acquisition/jobs.jsonl');api=ROOT/'results/phase7/api'
    if len(jobs)!=480:raise ValueError('UNEXPECTED_JOB_COUNT')
    rows=[]
    for j in jobs:
        row=json.loads((api/'jobs'/f'{j["job_id"]}.json').read_text(encoding='utf-8'))
        raw=json.loads((ROOT/row['raw_ref']).read_text(encoding='utf-8'))
        if row['request_hash']!=j['expected_request_hash'] or raw['request_hash']!=row['request_hash']:raise ValueError('HASH_MISMATCH')
        if parse_record(raw,j['ids'],j['view'])!=row['parsed']:raise ValueError('PARSE_MISMATCH')
        if j['view']=='B2' and check(cs[j['case_id']],row['parsed'].get('prediction'))!=row['certificate']:raise ValueError('CERTIFICATE_MISMATCH')
        rows.append(row)
    rows.sort(key=lambda r:r['job_id']);immutable(api/'observations.jsonl',rb(rows))
    budget=BudgetV7Locked(api/'budget.jsonl',CAP)
    summary={'planned':len(jobs),'completed':len(rows),'valid':sum(r['parsed']['protocol_valid'] for r in rows),
             'statuses':dict(Counter(r['raw_status'] for r in rows)),'cumulative_upper_usd':budget.total_cost,
             'remaining_usd':CAP-budget.total_cost,'cap_usd':CAP}
    immutable(api/'summary.json',jb(summary))
    immutable(api/'offline_finalization.json',jb({'method':'all saved jobs revalidated, no provider access',
        'job_count':len(jobs),'additional_requests':0,'ledger_sha256':sha((api/'budget.jsonl').read_bytes())}))
    print(json.dumps(summary),flush=True)

if __name__=='__main__':finalize()
