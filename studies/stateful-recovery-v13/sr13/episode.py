"""Bounded proposals with common validation and complete attempt retention."""
from time import perf_counter,thread_time
from .protocol import payload,ABLATIONS
from .construct import construct
from .verify import check,evaluate
from .engine import start_meter


def run_episode(case,method,validation_inputs,final_inputs,propose,*,max_candidates=3):
    start=perf_counter();cpu_start=thread_time();meter=start_meter();attempts=[];calls=0;accepted=False;deployed=[];termination='CANDIDATE_BUDGET'
    full=method=='contract' or method in ABLATIONS
    for iteration in range(max_candidates):
        construction_time=0;prompt=None
        if full and iteration==0:
            parsed={'status':'candidate','program':case['skill'],'reason':'source-derived bootstrap'}
        else:
            prompt=payload(case,validation_inputs[0],method,attempts,iteration)
            parsed=propose(prompt,iteration);calls+=1
        if parsed['status']!='candidate':
            termination=parsed.get('reason',parsed['status']) if parsed['status']=='invalid' else parsed['status']
            attempts.append({'iteration':iteration,'proposed':parsed.get('program'),'status':parsed['status'],
                             'reason':parsed.get('reason'),'request':parsed.get('request')})
            break
        original=parsed['program'];p=original;construction=None
        if full:
            t0=perf_counter()
            try:
                construction=construct(p,case,validation_inputs[0],omit=ABLATIONS.get(method));p=construction['program']
            except (KeyError,TypeError,ValueError,RecursionError,IndexError) as exc:
                construction={'error':type(exc).__name__}
            construction_time=perf_counter()-t0
        validation=check(p,case,validation_inputs)
        attempts.append({'iteration':iteration,'proposed':original,'program':p,'validation':validation,
                         'construction':construction,'construction_seconds':construction_time,
                         'request':parsed.get('request'),'reason':parsed.get('reason'),'status':'candidate'})
        if validation['accepted']:
            accepted=True;deployed=p;termination='ACCEPTED';break
    search_cost=dict(meter);search_seconds=perf_counter()-start;cpu_seconds=thread_time()-cpu_start
    evaluated=evaluate(deployed,case,final_inputs)
    return {'case_id':case['case_id'],'family':case['family'],'attack':case.get('attack','unit'),
            'method':method,'attempts':attempts,'model_calls':calls,'accepted':accepted,
            'deployed_program':deployed,'termination':termination,'evaluation':evaluated,
            'validator_steps':sum(a.get('validation',{}).get('steps',0) for a in attempts),
            'validator_world_runs':sum(a.get('validation',{}).get('world_runs',0) for a in attempts),
            'construction_seconds':sum(a.get('construction_seconds',0) for a in attempts),
            'search_cost':search_cost,'search_seconds':search_seconds,'search_cpu_seconds':cpu_seconds,
            'final_evaluation_cost':{k:meter[k]-search_cost[k] for k in meter},'elapsed_seconds':perf_counter()-start}
