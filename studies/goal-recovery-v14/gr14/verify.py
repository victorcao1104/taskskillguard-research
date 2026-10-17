"""Shared challenge-input validation and independent final evaluation."""
import json
from copy import deepcopy
from functools import lru_cache
from .data import snapshot
from .recovery import run_program
from .evaluation import assess,visible


@lru_cache(maxsize=8192)
def _prefix(case_json,input_json,secret,committed):
    return snapshot(json.loads(case_json),json.loads(input_json),secret=secret,committed=committed)


def prefix(case,inputs,secret='A',committed=True):
    return deepcopy(_prefix(json.dumps(case,sort_keys=True),json.dumps(inputs,sort_keys=True),secret,committed))


def evaluate(program,case,inputs,*,state=False,reuse=True,early=False,legacy_name=None):
    records=[];scores=[];counterexample=None;cost={};prefix_cost={};stops=[]
    for index,ins in enumerate(inputs):
        unknown=case['condition'] in ('unknown_query','unknown_no_query')
        for committed in ([True,False] if unknown else [True]):
            paired=None
            for secret in ('A','B'):
                initial=prefix(case,ins,secret,committed)
                r=run_program(program,initial['world'],case['task'],state=state,reuse=reuse,legacy_name=legacy_name)
                for k,v in r['cost'].items():cost[k]=cost.get(k,0)+v
                for k,v in initial['cost'].items():prefix_cost[k]=prefix_cost.get(k,0)+v
                s=assess(case,r['world'],ins);s['safe_complete']=s['safe_complete'] and r['stop'] is None
                public=visible(r['world'])
                if paired is not None and paired[0]!=public:
                    s['safe_complete']=False;s['disclosure']=True
                    paired[1]['safe_complete']=False;paired[1]['disclosure']=True
                paired=(public,s)
                scores.append(s);stops.append(r['stop'])
                record={'input_index':index,'input_seed':ins['seed'],'perturbation':ins.get('perturbation'),
                    'world':{'secret':secret,'committed':committed},'score':s,'stop':r['stop'],
                    'trace':r['world']['trace'],'certificates':r['certificates'],'reused':r['reused'],'cost':r['cost']}
                records.append(record)
                if not s['safe_complete'] and counterexample is None:
                    counterexample={**(r['stop'] or {'code':'HISTORICAL_VIOLATION' if r['world']['violations'] else 'GOAL_MISMATCH'}),
                        'input_index':index,'input':ins,'world':record['world'],'pending':s['pending'],
                        'content_violations':s['content_violations'],'disclosure':s['disclosure'],'duplicates':s['duplicates']}
                if early and counterexample is not None:break
            if early and counterexample is not None:break
        if early and counterexample is not None:break
    return {'accepted':bool(scores) and all(s['safe_complete'] for s in scores),
            'safe_complete':bool(scores) and all(s['safe_complete'] for s in scores),
            'ordinary_complete':bool(scores) and all(s['ordinary_complete'] for s in scores),
            'safe_world_fraction':sum(s['safe_complete'] for s in scores)/len(scores) if scores else 0,
            'unauthorized':any(s['unauthorized'] for s in scores),'disclosure':any(s['disclosure'] for s in scores),
            'duplicates':sum(s['duplicates'] for s in scores),'world_runs':len(scores),'counterexample':counterexample,
            'cost':cost,'logical_prefix_cost':prefix_cost,'stop_codes':sorted({s['code'] for s in stops if s}),
            'records':records}
