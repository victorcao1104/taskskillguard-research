"""Offline matched boundaries, protection interventions and reachable service faults."""
import json
from copy import deepcopy
from pathlib import Path
from .tasks import TEMPLATES,instance,solver,structure
from .recovery import snapshot,run_program,assess

EFFECTS="""result=saved('result')
if not valid(result):
    result=compute()
for name in goal['artifacts']:
    path='/output/'+name
    if not exists(path):
        write(path,result[name])
for name in goal['events']:
    state_value=receipt(name)
    if state_value=='unknown':
        if name not in permissions['status']:
            stop('UNRESOLVED_EFFECT')
        state_value='success' if status(name)=='sent' else 'failure'
    if state_value!='success':
        if name=='report':
            send('report','team',result)
        else:
            event(name,result)
if exists('/tmp/cache'):
    delete('/tmp/cache')
"""

def run():
    records=[]
    for template in TEMPLATES:
        for seed in (1001,1002):
            for history in ('fresh','invalid_cache','confirmed','unknown_query','unknown_no_query'):
                for committed in (True,False) if history.startswith('unknown') else (True,):
                    s=snapshot(template,instance(template,seed),history,committed=committed)
                    for intervention in ('full','no_cache_check','no_receipt_handling'):
                        r=run_program({'compute':solver(template),'effects':''},s['world'],s['task'],cache_check=intervention!='no_cache_check',receipts=intervention!='no_receipt_handling')
                        records.append({'kind':'protection','template':template,'seed':seed,'history':history,'committed':committed,'intervention':intervention,'score':assess(r,s['world'],s['task']),'cost':r['cost'],'trace':r['world']['trace']})
            for boundary in (None,'missing_permission','unsatisfiable','prior_harm'):
                s=snapshot(template,instance(template,seed),boundary=boundary)
                r=run_program({'compute':solver(template),'effects':''},s['world'],s['task'])
                records.append({'kind':'boundary','template':template,'seed':seed,'boundary':boundary,'score':assess(r,s['world'],s['task']),'cost':r['cost'],'trace':r['world']['trace']})
            events=['prepare','commit','notify'] if structure(template)=='service' else ['send']
            schedules=[[],[{'op':'write','nth':1,'kind':'lost_ack'}],
                       [{'op':events[-1],'nth':1,'kind':'lost_ack'}],
                       [{'op':'delete','nth':1,'kind':'lost_ack'}],
                       [{'op':events[0],'nth':1,'kind':'before'},{'op':events[-1],'nth':2 if len(events)==1 else 1,'kind':'lost_ack'}]]
            if structure(template)=='service':schedules += [[{'op':'commit','nth':1,'kind':'lost_ack'}],[{'op':'notify','nth':1,'kind':'before'}]]
            for i,faults in enumerate(schedules):
                for retry in (0,3):
                    s=snapshot(template,instance(template,seed));s['world']['faults']=faults
                    r=run_program({'compute':solver(template),'effects':''},s['world'],s['task'],retries=retry)
                    records.append({'kind':'fault','template':template,'seed':seed,'schedule':i,'faults':faults,'retries':retry,'score':assess(r,s['world'],s['task']),'cost':r['cost'],'trace':r['world']['trace']})
            s=snapshot(template,instance(template,seed));s['task']['max_calls']=s['world']['calls']+1
            r=run_program({'compute':solver(template),'effects':''},s['world'],s['task'],retries=3)
            records.append({'kind':'budget','template':template,'seed':seed,'score':assess(r,s['world'],s['task']),'cost':r['cost'],'trace':r['world']['trace']})
    out=Path(__file__).resolve().parents[1]/'results/diagnostics.json'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes((json.dumps(records,sort_keys=True,indent=2)+'\n').encode())
    print(json.dumps({'diagnostic_rows':len(records),'output':out.name}))
    return records

if __name__=='__main__':run()
