"""Additive reporting audit: normal original execution, never a label-based gate."""
import json
from gr14.campaign import STUDY,grid,save_result
from gr14.data import make_case,inputs_for,FAMILIES
from gr14.verify import prefix,evaluate
from gr14.runtime import execute
from gr14.evaluation import assess
from gr14.compiler import compile_program
from gr14.provider import immutable

def original(case,phase):
    records=[];cost={}
    for ins in inputs_for(case,phase):
        for committed in ([True,False] if case['condition'] in ('unknown_query','unknown_no_query') else [True]):
            for secret in ('A','B'):
                p=prefix(case,ins,secret,committed)
                # Fixture with no original execution must actually execute, not be granted a pass.
                if p['cost']['executions']==0:p=execute(case['skill']['compute']+'\n'+case['skill']['effects'],p['world'],case['task'])
                s=assess(case,p['world'],ins);s['safe_complete']=s['safe_complete'] and p['stop'] is None
                for k,v in p['cost'].items():cost[k]=cost.get(k,0)+v
                records.append({'seed':ins['seed'],'world':{'secret':secret,'committed':committed},'score':s,'stop':p['stop']})
    return {'all_safe_complete':all(r['score']['safe_complete'] for r in records),'any_safe_complete':any(r['score']['safe_complete'] for r in records),'worlds':len(records),'cost':cost,'records':records}

def main():
    cases={c['case_id']:c for campaign in ('main','combined') for c,_,_,_ in grid(campaign)}
    audit={}
    for cid,c in cases.items():
        audit[cid]=original(c,'final')
    immutable(STUDY/'reports/original_execution_audit.json',{'label':'post-acquisition additive original-execution audit; no new model acquisition', 'cases':audit})
    for fam in FAMILIES:
        for con in ('guard_mix','cache_destroy'):
            c=make_case(fam,con)
            for method in ('compiler','compiler_fresh','source_state'):
                path=STUDY/'results/combined_controls'/f"{c['case_id']}--{method}.json"
                if path.exists():continue
                if method=='source_state':
                    from gr14.recovery import transform_compute
                    p={'compute':transform_compute(c['skill']['compute'],c['task'])['code'],'effects':'pass'}
                else:p=compile_program(c['task'],reuse=method!='compiler_fresh')
                final=evaluate(p,c,inputs_for(c,'final'),state=method=='source_state')
                stress=evaluate(p,c,inputs_for(c,'stress'),state=method=='source_state')
                save_result(path,{'case_id':c['case_id'],'family':fam,'condition':con,'expected_status':c['expected_status'],'method':method,'selected':p,'final':final,'stress':stress})
        print(json.dumps({'combined_control_family':fam}),flush=True)
    print(json.dumps({'original_complete_cases':[k for k,v in audit.items() if v['all_safe_complete']],'mixed_gate_cases':[k for k,v in audit.items() if v['any_safe_complete'] and not v['all_safe_complete']]}))
if __name__=='__main__':main()
