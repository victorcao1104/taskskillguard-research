"""Common trial bookkeeping; deterministic controls have no model access."""
from copy import deepcopy
from time import perf_counter,thread_time
from .contracts import snapshot
from .construct import construct,from_task
from .verify import check,evaluate
from .engine import start_meter

OFFLINE_METHODS=('stop','delete_continue','retry_original','goal_direct','catalogue_oracle','contract_source')


def resume_after(program,location):
    try:parts=location.split('.');index=int(parts[0])
    except (ValueError,AttributeError):return []
    if index>=len(program):return []
    tail=deepcopy(program[index+1:])
    if len(parts)>1:
        a=program[index]
        branch=parts[1] if parts[1] in {'then','else','body'} else 'body'
        body=a.get(branch,[])
        rest=parts[2:] if parts[1] in {'then','else','body'} else parts[1:]
        return resume_after(body,'.'.join(rest))+tail
    return tail


def offline_trial(method,case,validation_inputs,final_inputs,*,catalogue_program=None):
    start=perf_counter();cpu_start=thread_time();meter=start_meter();inputs=validation_inputs[0];details={}
    if method=='stop':p=[]
    elif method=='retry_original':p=deepcopy(case['skill'])
    elif method=='delete_continue':
        _,stop=snapshot(case,inputs)
        p=resume_after(case['skill'],stop.get('location','') if stop else '')
    elif method=='goal_direct':p=from_task(case,inputs)
    elif method=='catalogue_oracle':
        if catalogue_program is None:raise ValueError('PREPARED_CATALOGUE_REQUIRED')
        # A separately prepared task-specific answer; preparation cost is retained.
        p=deepcopy(catalogue_program)
    elif method=='contract_source':
        details=construct(case['skill'],case,inputs);p=details['program']
    else:raise ValueError('UNKNOWN_METHOD')
    validation=check(p,case,validation_inputs)
    validation_attempts=[validation]
    if not validation['accepted'] and method=='goal_direct':
        p=construct(from_task(case,inputs,state_aware=False),case,inputs,omit='residual')['program']
        validation=check(p,case,validation_inputs);validation_attempts.append(validation)
    deployed=p if validation['accepted'] else []
    search_cost=dict(meter);search_seconds=perf_counter()-start;cpu_seconds=thread_time()-cpu_start
    result={'method':method,'case_id':case['case_id'],'program':p,'validation':validation,
            'evaluation':evaluate(deployed,case,final_inputs),'accepted':validation['accepted'],'validation_attempts':validation_attempts,
            'deployed_program':deployed,'construction':details,
            'search_cost':search_cost,'search_seconds':search_seconds,'search_cpu_seconds':cpu_seconds,
            'final_evaluation_cost':{k:meter[k]-search_cost[k] for k in meter},
            'elapsed_seconds':perf_counter()-start,'model_calls':0}
    return result
