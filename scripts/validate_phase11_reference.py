"""Independent finite-reference agreement after production/data freeze."""
import json
import sys
from phase11_common import ROOT,jb,rb,sha,immutable,read_rows,verify_freeze
sys.path.insert(0,str(ROOT/'src'))
from tsg.certificate_v11 import audit_run,public_case
from tsg.commit_v11 import execute_certified
from tsg.runtime_v6 import parse_source

def normalize_error(value):
    return 'unbound_variable' if isinstance(value,str) and value.startswith('unbound_variable:') else value

def validate(normalize_errors=False):
    verify_freeze();records=[];mismatches=[]
    out=ROOT/'results/phase11/reference'/('normalized' if normalize_errors else '')
    normalized_errors=0
    for cohort,cfile,rfile in [('heldout','heldout.jsonl','reference.jsonl'),
        ('challenge','challenge.jsonl','reference_challenge.jsonl'),('scaling','scaling.jsonl','reference_scaling.jsonl')]:
        cases=read_rows(ROOT/'data/phase11'/cfile);refs={r['case_id']:r for r in read_rows(ROOT/'data/phase11'/rfile)}
        for c in cases:
            programs=[parse_source(c['source']),*c['routes']]
            assert programs[0]==c['program'],'SOURCE_REFERENCE_AST_MISMATCH'
            for w,world in enumerate(c['worlds']):
                for route,p in enumerate(programs):
                    ref=refs[c['case_id']]['executions'][w][route];audit=audit_run(p,world,c['goal'],32)
                    runtime=execute_certified(public_case(c),route,w)
                    common=('files','emits','goal','safe_success','charged_calls','receipt_reuses')
                    fields=[k for k in common if ref[k]!=audit[k]]
                    ref_error=normalize_error(ref['error']) if normalize_errors else ref['error']
                    normalized_errors+=int(ref_error!=ref['error'])
                    if ref_error!=audit['error']:fields.append('error')
                    if ref['steps_entered']!=audit['interpreter_steps']:fields.append('interpreter_steps')
                    tkeys=('id','op','resource','value','authorized','key','charged','committed','status')
                    norm=lambda trace:[{k:e[k] for k in tkeys} for e in trace]
                    if norm(ref['trace'])!=norm(audit['trace']):fields.append('normalized_trace')
                    expected_error=ref_error or (None if ref['goal'] else 'goal_unmet')
                    if runtime['failure_reason']!=expected_error:fields.append('runtime_failure_reason')
                    for k,rk in [('files','files'),('emits','emits'),('safe_success','authorized_goal'),
                                 ('charged_calls','charged_calls'),('receipt_reuses','receipt_reuses')]:
                        if ref[k]!=runtime[rk]:fields.append('runtime_'+rk)
                    row={'case_id':c['case_id'],'family':c['family'],'split':cohort,'world':w,'route':route,
                         'matches':not fields,'different_fields':fields,'reference_sha256':sha(jb(ref)),
                         'audit_sha256':sha(jb(audit)),'runtime_sha256':sha(jb(runtime))}
                    records.append(row)
                    if fields:mismatches.append({**row,'reference':ref,'audit':audit,'runtime':runtime})
    immutable(out/'agreement.jsonl',rb(records))
    summary={'comparisons':len(records),'matching':sum(r['matches'] for r in records),
        'mismatches':len(mismatches),'normalized_error_records':normalized_errors,
        'error_normalization':('reference unbound_variable:<name> maps to unbound_variable; ' if normalize_errors else '')+
            'completed program with false goal maps to runtime goal_unmet',
        'trace_normalization':'independent common event fields; production route/attempt annotations excluded'}
    # Keep the already retained initial summary's original schema unchanged.
    if not normalize_errors:summary.pop('normalized_error_records')
    immutable(out/'agreement_summary.json',jb(summary))
    if mismatches:
        immutable(out/'mismatches.json',jb(mismatches))
        raise AssertionError(json.dumps(summary))
    return summary

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--normalize-errors',action='store_true');a=p.parse_args()
    print(json.dumps(validate(a.normalize_errors)),flush=True)
