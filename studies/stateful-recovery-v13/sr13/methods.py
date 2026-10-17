"""Common trial bookkeeping; deterministic controls have no model access."""
from copy import deepcopy
from time import perf_counter
from .contracts import snapshot
from .construct import construct,from_task
from .verify import check,evaluate

OFFLINE_METHODS=('stop','delete_continue','retry_original','goal_direct','catalogue_oracle','contract_source')


def resume_after(program,location):
    try:parts=[int(x) for x in location.split('.')]
    except (ValueError,AttributeError):return []
    index=parts[0]
    if index>=len(program):return []
    tail=deepcopy(program[index+1:])
    if len(parts)>1:
        a=program[index]
        body=a.get('then',a.get('body',[]))
        return resume_after(body,'.'.join(map(str,parts[1:])))+tail
    return tail


def offline_trial(method,case,validation_inputs,final_inputs):
    start=perf_counter();inputs=validation_inputs[0];details={}
    if method=='stop':p=[]
    elif method=='retry_original':p=deepcopy(case['skill'])
    elif method=='delete_continue':
        _,stop=snapshot(case,inputs)
        p=resume_after(case['skill'],stop.get('location','') if stop else '')
    elif method=='goal_direct':p=from_task(case,inputs)
    elif method=='catalogue_oracle':
        # Advantaged reference prepared from trusted goals. Not a main competitor.
        p=from_task(case,inputs)
    elif method=='contract_source':
        details=construct(case['skill'],case,inputs);p=details['program']
    else:raise ValueError('UNKNOWN_METHOD')
    validation=check(p,case,validation_inputs)
    deployed=p if validation['accepted'] else []
    result={'method':method,'case_id':case['case_id'],'program':p,'validation':validation,
            'evaluation':evaluate(deployed,case,final_inputs),'accepted':validation['accepted'],
            'deployed_program':deployed,'construction':details,
            'elapsed_seconds':perf_counter()-start,'model_calls':0}
    return result
