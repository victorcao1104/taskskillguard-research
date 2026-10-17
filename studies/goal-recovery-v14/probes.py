"""Controlled diagnostic candidate bank; not independent task-family evidence."""
import itertools
import json
from copy import deepcopy
from gr14.campaign import STUDY
from gr14.data import FAMILIES,make_case,inputs_for
from gr14.compiler import compile_program,EFFECTS
from gr14.goals import truth
from gr14.runtime import new_world
from gr14.recovery import run_program
from gr14.verify import evaluate
from gr14.provider import immutable

def witness(rows,goal):
    for k in range(goal['min_count'],goal['max_count']+1):
        for group in itertools.combinations(rows,k):
            if goal['order_by']:group=sorted(group,key=lambda r:tuple(r[f] for f in goal['order_by']))
            ids=[r['id'] for r in group]
            if truth(ids,rows,goal)['valid']:return ids
    return None

def main():
    validation=[];reuse=[]
    for fam in FAMILIES:
        c=make_case(fam,'benign');weak=inputs_for(c,'weak');strong=inputs_for(c,'validation');final=inputs_for(c,'final');base=compile_program(c['task'],reuse=False)
        table={i['rows'][0]['id']:witness(i['rows'],c['task']['goal']) for i in weak}
        bank={'three_examples_only':{'compute':f"known={table!r}\nrows=read('/input/options')\nresult=None\nif rows[0]['id'] in known:\n    result=known[rows[0]['id']]",'effects':EFFECTS}}
        for name,condition in [('id_format_assumption',"'renamed_' in rows[0]['id']"),('no_decoy_assumption',"rows[0]['cost']==100"),('nonboundary_assumption',"sum([row['cost'] for row in rows])==len(rows)")]:
            bank[name]={'compute':base['compute']+"\nrows=read('/input/options')\nif "+condition+":\n    result=['wrong']",'effects':EFFECTS}
        for name,p in bank.items():
            result={phase:evaluate(p,c,ins,early=True) for phase,ins in [('weak',weak),('strong',strong),('final',final)]}
            validation.append({'family':fam,'probe':name,'program':p,'outcomes':{k:{'accepted':v['accepted'],'counterexample':v['counterexample'],'cost':v['cost']} for k,v in result.items()}})
        # Identical observed valid value does not justify future reuse: vary input/goal.
        first=weak[0];value=witness(first['rows'],c['task']['goal'])
        for mode in ('same_input','new_ids','changed_goal','forged_certificate'):
            ins=deepcopy(first);task=deepcopy(c['task']);cached=deepcopy(value)
            if mode=='new_ids':ins=deepcopy(final[0])
            if mode=='changed_goal':task['goal']['min_count']=task['goal']['max_count']=len(value)+1
            if mode=='forged_certificate':cached=['nonexistent']
            world=new_world(ins['rows']);world['env']={'cached':{'value':cached,'labels':[]},'certificate':{'value':{'valid':True},'labels':[]}}
            old=run_program(base,world,task,state=True,legacy_name='cached')
            new=run_program(compile_program(task,reuse=False),world,task,state=True)
            reuse.append({'family':fam,'mode':mode,'cached_valid_now':truth(cached,ins['rows'],task['goal'])['valid'],
                 'legacy':{'reused':old['reused'],'valid_output':truth(old['world']['files'].get('/output/selection'),ins['rows'],task['goal'])['valid'],'stop':old['stop']},
                 'current':{'reused':new['reused'],'valid_output':truth(new['world']['files'].get('/output/selection'),ins['rows'],task['goal'])['valid'],'stop':new['stop'],'certificates':new['certificates']}})
    immutable(STUDY/'reports/controlled_probes.json',{'purpose':'Hand-designed failure demonstrations, not a random error-rate estimate; no candidates were sent to models.','validation':validation,'reuse':reuse})
    print(json.dumps({'bank':len(validation),'weak_accepted':sum(x['outcomes']['weak']['accepted'] for x in validation),'strong_accepted':sum(x['outcomes']['strong']['accepted'] for x in validation),'reuse_cases':len(reuse),'legacy_invalid_outputs':sum(not x['legacy']['valid_output'] for x in reuse),'current_invalid_outputs':sum(not x['current']['valid_output'] for x in reuse)}))
if __name__=='__main__':main()
