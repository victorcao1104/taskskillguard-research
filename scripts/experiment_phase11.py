"""Frozen deterministic grids; no API and no reference-derived selector input."""
import argparse
from collections import Counter
from copy import deepcopy
import json
import sys
from phase11_common import ROOT,jb,rb,immutable,read_rows,write_chunks,read_chunks,verify_freeze,sha
sys.path.insert(0,str(ROOT/'src'))
from tsg.certificate_v11 import (CertificateSession,make_reader,run_policy,choose_query,
    verify_certificate,audit_run,public_case)
from tsg.commit_v11 import execute_certified
from tsg.runtime_v6 import parse_source
from tsg.recovery_v10 import execute as previous_execute

POLICIES=('original_first','route_cover','observe_cover','random')
BUDGETS=(2,4,8,12,'full')
FAULTS=('none','ambiguous_after','terminal_noncommit','pending','unavailable','stale',
    'wrong_signature','pending_absent','second_ambiguous_after','second_terminal_noncommit',
    'emit_ambiguous_after','emit_terminal_noncommit')
RECOVERY=('strict_stop','terminal_status','same_id_dedup')

def selected_cases():
    held=read_rows(ROOT/'data/phase11/heldout.jsonl')+read_rows(ROOT/'data/phase11/challenge.jsonl')
    scale=read_rows(ROOT/'data/phase11/scaling.jsonl') if (ROOT/'data/phase11/scaling.jsonl').exists() else []
    return held,scale

def metadata(c):return {k:c[k] for k in ('case_id','family','split')}

def policy_record(c,w,policy,budget,stop):
    limit=budget if budget!='full' else len(c['worlds'])*(len(c['routes'])+1)+len(c.get('observable_files',[]))+len(c.get('observable_grants',[]))
    r=run_policy(c,w,lambda s:choose_query(s,policy,seed=11101),budget=limit,stop=stop)
    cert=r['certificate'];valid=(verify_certificate(c,r['observations'],cert) if cert['status'] in ('certified','infeasible') else None)
    if valid is False:raise AssertionError('CERTIFICATE_VERIFICATION_FAILED')
    execution=(execute_certified(public_case(c),cert['route'],w) if cert['status']=='certified' else None)
    if execution is not None and not execution['authorized_goal']:raise AssertionError('CERTIFIED_FAULTFREE_FAILURE')
    return {**metadata(c),'world_index':w,'policy':policy,'budget':budget,'stop':stop,
        'certificate_verified':valid,'result':r,'execution':execution}

def deterministic():
    held,scale=selected_cases();semantics=[];policies=[];recovery=[];previous=[]
    for c in held+scale:
        programs=[parse_source(c['source']),*c['routes']]
        for w,world in enumerate(c['worlds']):
            for ri,program in enumerate(programs):
                audit=audit_run(program,world,c['goal'],32)
                execution=execute_certified(public_case(c),ri,w)
                if (audit['files'],audit['emits'],audit['safe_success'],audit['charged_calls'],audit['receipt_reuses']) != (
                    execution['files'],execution['emits'],execution['authorized_goal'],execution['charged_calls'],execution['receipt_reuses']):
                    raise AssertionError('QUERY_EXECUTOR_SEMANTICS_MISMATCH')
                semantics.append({**metadata(c),'world_index':w,'route':ri,'audit':audit,'execution':execution})
            for policy in POLICIES:
                for budget in BUDGETS:
                    for stop in (False,True):policies.append(policy_record(c,w,policy,budget,stop))
            if c in scale:continue
            # Full public-information heuristic supplies a verified route; no truth.
            full=policy_record(c,w,'observe_cover','full',True)
            cert=full['result']['certificate']
            previous.append({**metadata(c),'world_index':w,'old_runtime':previous_execute(c,world_index=w,
                planning_budget=512,observation_budget=2,quota=32,observation_mode='goal'),
                'new_runtime':full['execution'],'new_acquisition':full['result']})
            for fault in FAULTS:
                for policy in RECOVERY:
                    for sb in (0,1):
                        run=(execute_certified(public_case(c),cert['route'],w,fault,policy,32,sb)
                             if cert['status']=='certified' else None)
                        if run is not None and (run['duplicate_effects'] or run['unauthorized_effects'] or run['charged_calls']>32):
                            raise AssertionError('RECOVERY_INVARIANT')
                        recovery.append({**metadata(c),'world_index':w,'fault':fault,'policy':policy,'status_budget':sb,
                            'certificate_status':cert['status'],'route':cert['route'],'result':run})
        print(json.dumps({'deterministic_case':c['case_id'],'policy_rows':len(policies),'recovery_rows':len(recovery)}),flush=True)
    for name,rows in [('semantics',semantics),('policies',policies),('recovery',recovery),('previous',previous)]:
        write_chunks(f'results/phase11/{name}',rows)
    summary={'heldout_cases':len(held),'families':len({c['family'] for c in held}),'scaling_cases':len(scale),
        'semantic_pairs':len(semantics),'policy_conditions':len(policies),'recovery_conditions':len(recovery),
        'previous_contract_comparisons':len(previous),'note':'rows are dependent conditions, not independent samples'}
    immutable(ROOT/'results/phase11/deterministic_summary.json',jb(summary));return summary

def integrated():
    held,_=selected_cases();cs={c['case_id']:c for c in held}
    streams=read_rows(ROOT/'results/phase11/api/observations.jsonl');rows=[];prefix=[]
    for stream in streams:
        c=cs[stream['case_id']];w=stream['world_index']
        for budget in (2,4,8,12):
            s=CertificateSession(c,make_reader(c,w));first=None
            for q in stream['order'][:budget]:
                s.consume(q);cert=s.check()
                if cert['status']!='unknown' and first is None:first={**cert,'query_count':s.result()['query_count']}
            cert=s.check()
            if cert['status'] in ('certified','infeasible') and not verify_certificate(c,s.observations,cert):raise AssertionError('MODEL_CERT_INVALID')
            for fault in ('none','ambiguous_after','terminal_noncommit','pending_absent'):
                for policy in ('strict_stop','terminal_status','same_id_dedup'):
                    run=execute_certified(public_case(c),cert['route'],w,fault,policy) if cert['status']=='certified' else None
                    if run is not None and (run['duplicate_effects'] or run['unauthorized_effects']):raise AssertionError('MODEL_RUNTIME_UNSAFE')
                    rows.append({**metadata(c),'stream_id':stream['stream_id'],'model':stream['model'],
                        'view':stream['view'],'stop':stream['stop'],'world_index':w,'budget':budget,
                        'fault':fault,'policy':policy,'acquired_queries':s.result()['query_count'],
                        'certificate':cert,'result':run})
            if first and first['status']=='certified':
                a=execute_certified(public_case(c),first['route'],w)
                b=execute_certified(public_case(c),cert['route'],w) if cert['status']=='certified' else None
                if not a['authorized_goal'] or not b or not b['authorized_goal']:raise AssertionError('WITNESS_NOT_PRESERVED')
                prefix.append({**metadata(c),'stream_id':stream['stream_id'],'budget':budget,
                    'queries':s.result()['query_count'],'earliest_queries':first['query_count'],
                    'first_route':first['route'],'later_route':cert['route'],
                    'both_faultfree_success':True,'trace_equal':a==b,
                    'claim':'offline matched-prefix witness preservation, not API invoice savings'})
    write_chunks('results/phase11/integrated',rows);write_chunks('results/phase11/matched_prefix',prefix)
    summary={'integrated_rows':len(rows),'matched_prefix_rows':len(prefix)}
    immutable(ROOT/'results/phase11/integrated_summary.json',jb(summary));return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['deterministic','integrated']);a=p.parse_args()
    verify_freeze();print(json.dumps(deterministic() if a.stage=='deterministic' else integrated()),flush=True)
