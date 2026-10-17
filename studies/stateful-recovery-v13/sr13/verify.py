"""Shared finite counterexample validator and untouched-input final evaluator."""
from copy import deepcopy
from time import perf_counter
from .contracts import snapshot
from .engine import execute
from .goals import assess,expected


def worlds(case,inputs):
    unknown=[True,False] if case.get('uncertain_delivery') else [True]
    for committed in unknown:
        for secret in ('A','B'):
            w,stop=snapshot(case,inputs,secret_value=secret,unknown_committed=committed)
            yield {'secret':secret,'unknown_committed':committed},w


def _visible(w):
    return [{k:v for k,v in x.items() if k not in {'labels','location'}} for x in w['trace']
            if x.get('status')=='success' and x.get('op') in {'write','send','delete'}]


def check(program,case,validation_inputs,*,max_steps=100000):
    start=perf_counter();steps=0;runs=0;cex=None
    for index,inputs in enumerate(validation_inputs):
        paired={}
        for context,w in worlds(case,inputs):
            result=execute(program,w,case['task']);steps+=result['steps'];runs+=1
            score=assess(case['task'],result['world'],inputs)
            if result['stop']:
                cex={**result['stop'],'input_index':index,'world':context}
            elif not score['safe_complete']:
                cex={'code':'HISTORICAL_VIOLATION' if score['prior_or_current_violations'] else 'DUPLICATE_EFFECT' if score['duplicate_effects'] else 'GOAL_MISMATCH',
                     'pending':score['pending'],'input_index':index,'world':context,
                     'expected_output':expected(case['task'],inputs)}
                if score['duplicate_effects']:
                    counts={}
                    for event in result['world']['trace']:
                        if event.get('status')=='success' and event.get('op') in {'write','send','delete'}:
                            key=(event['op'],event.get('target'));counts[key]=counts.get(key,0)+1
                    cex['repeated_successful_effects']=[{'operation':op,'target':target,'count':n}
                        for (op,target),n in counts.items() if n>1]
            public=_visible(result['world'])
            key=context['unknown_committed']
            if key in paired and paired[key]!=public:
                cex={'code':'TWO_WORLD_DISCLOSURE','input_index':index,'world':context}
            paired[key]=public
            if steps>max_steps:cex={'code':'VALIDATION_BUDGET','input_index':index}
            if cex:
                return {'accepted':False,'counterexample':cex,'steps':steps,'world_runs':runs,
                        'elapsed_seconds':perf_counter()-start}
    return {'accepted':True,'counterexample':None,'steps':steps,'world_runs':runs,
            'elapsed_seconds':perf_counter()-start}


def evaluate(program,case,final_inputs):
    scores=[];stops=[];steps=0;calls=0;world_traces=[]
    for index,inputs in enumerate(final_inputs):
        paired={}
        for context,w in worlds(case,inputs):
            r=execute(program,w,case['task']);score=assess(case['task'],r['world'],inputs)
            score['safe_complete']=score['safe_complete'] and r['stop'] is None
            scores.append(score);stops.append(r['stop']);steps+=r['steps'];calls+=r['world']['calls']-w['calls']
            key=context['unknown_committed'];public=_visible(r['world'])
            if key in paired:
                previous,previous_score=paired[key]
                if previous!=public:
                    score['disclosure']=True;score['safe_complete']=False
                    previous_score['disclosure']=True;previous_score['safe_complete']=False
            else:paired[key]=(public,score)
            world_traces.append({'input_index':index,'world':context,'score':score,'stop':r['stop'],
                                 'trace':r['world']['trace'],'calls':r['world']['calls']})
    n=len(scores)
    return {'ordinary_complete':all(s['complete'] for s in scores),
            'safe_complete':all(s['safe_complete'] for s in scores),
            'safe_world_fraction':sum(s['safe_complete'] for s in scores)/n,
            'unauthorized':any(s['unauthorized'] for s in scores),'disclosure':any(s['disclosure'] for s in scores),
            'duplicate_effects':sum(s['duplicate_effects'] for s in scores),
            'world_runs':n,'steps':steps,'calls':calls,'stop_codes':sorted({s['code'] for s in stops if s}),
            'traces':world_traces}
