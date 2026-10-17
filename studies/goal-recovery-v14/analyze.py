"""Post-acquisition analysis; no network or candidate modification."""
import argparse
from collections import Counter,defaultdict
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import random
from gr14.campaign import STUDY,MODELS,METHODS
from gr14.provider import immutable,Provider
from gr14.data import make_case,inputs_for
from gr14.verify import evaluate

def read_rows(campaign):return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((STUDY/'results'/campaign).glob('*.json'))]
def compact(r):return {k:v for k,v in r.items() if k!='records'}
def aggregate(rows):
    groups=defaultdict(list)
    for r in rows:groups[(r.get('model','deterministic'),r['method'])].append(r)
    out=[]
    for (model,method),rs in sorted(groups.items()):
        feasible=[r for r in rs if r['expected_status']=='feasible'];benign=[r for r in rs if r['condition']=='benign'];non=[r for r in rs if r['expected_status']!='feasible']
        out.append({'model':model,'method':method,'n':len(rs),'safe':sum(r['final']['safe_complete'] for r in rs),
          'ordinary':sum(r['final']['ordinary_complete'] for r in rs),'feasible_n':len(feasible),'feasible_safe':sum(r['final']['safe_complete'] for r in feasible),
          'benign_n':len(benign),'benign_safe':sum(r['final']['safe_complete'] for r in benign),'nonfeasible_n':len(non),
          'nonfeasible_safe_claims':sum(r['final']['safe_complete'] for r in non),
          'nonfeasible_explicit_stop':sum(bool(r.get('attempts')) and (r['attempts'][-1].get('feedback') or {}).get('code') in ('MODEL_STOP','MODEL_CLARIFY') for r in non),
          'blocked_candidate_codes':dict(Counter(a['feedback']['code'] for r in rs for a in r.get('attempts',[]) if a.get('feedback') and a['feedback'].get('code') in ('PRIVILEGE','DISCLOSURE','DUPLICATE_EFFECT'))),
          'selected_n':sum('model' in r and r.get('selected') is not None for r in rs),'accepted_final_failures':sum('model' in r and r.get('selected') is not None and not r['final']['safe_complete'] for r in rs),
          'requests':sum(r.get('requests',0) for r in rs), 'unauthorized':sum(r['final']['unauthorized'] for r in rs),'disclosure':sum(r['final']['disclosure'] for r in rs),
          'duplicates':sum(r['final']['duplicates'] for r in rs),
          'construction_steps':sum(r.get('construction_cost',{}).get('steps',0) for r in rs),
          'construction_prefix_steps':sum(r.get('construction_cost',{}).get('logical_prefix_steps',0) for r in rs),
          'construction_steps_including_prefix':sum(r.get('construction_cost',{}).get('steps',0)+r.get('construction_cost',{}).get('logical_prefix_steps',0) for r in rs),
          'final_steps':sum(r['final']['cost'].get('steps',0) for r in rs),
          'final_prefix_steps':sum(r['final'].get('logical_prefix_cost',{}).get('steps',0) for r in rs),
          'final_steps_including_prefix':sum(r['final']['cost'].get('steps',0)+r['final'].get('logical_prefix_cost',{}).get('steps',0) for r in rs),
          'final_worlds':sum(r['final']['world_runs'] for r in rs),
          'final_tool_calls':sum(r['final']['cost'].get('tool_calls',0) for r in rs),
          'final_prefix_tool_calls':sum(r['final'].get('logical_prefix_cost',{}).get('tool_calls',0) for r in rs),
          'control_validation_steps':sum(r.get('other_phases',{}).get('validation',{}).get('cost',{}).get('steps',0) for r in rs),
          'control_validation_prefix_steps':sum(r.get('other_phases',{}).get('validation',{}).get('logical_prefix_cost',{}).get('steps',0) for r in rs),
          'construction_checks':sum(r.get('construction_cost',{}).get('checks',0) for r in rs),
          'construction_prefix_checks':sum(a.get('validation',{}).get('logical_prefix_cost',{}).get('checks',0) for r in rs for a in r.get('attempts',[])),
          'final_checks':sum(r['final']['cost'].get('checks',0) for r in rs),
          'final_prefix_checks':sum(r['final'].get('logical_prefix_cost',{}).get('checks',0) for r in rs),
          'final_checks_including_prefix':sum(r['final']['cost'].get('checks',0)+r['final'].get('logical_prefix_cost',{}).get('checks',0) for r in rs),
          'terminal_codes':dict(Counter(a['feedback']['code'] for r in rs for a in r.get('attempts',[])[-1:] if a.get('feedback'))),
          'model_usage':{k:sum((a.get('response',{}).get('usage') or {}).get(k,0) for r in rs for a in r.get('attempts',[])) for k in ('input_tokens','output_tokens')},
          'api_seconds':sum(r.get('timing',{}).get('api_seconds',0) for r in rs),'cpu_seconds':sum(r.get('timing',{}).get('cpu_seconds',0) for r in rs)})
    return out

def contrasts(rows):
    out=[]
    for model in MODELS:
        for a,b in [('repair_state','repair_raw'),('replan_state','replan_raw'),('full','repair_state'),('full','replan_state'),('full','full_no_reuse')]:
            left={(r['case_id'],r['replicate']):r for r in rows if r['model']==model and r['method']==a};right={(r['case_id'],r['replicate']):r for r in rows if r['model']==model and r['method']==b}
            if left.keys()!=right.keys() or not left:continue
            diffs=defaultdict(list);wins=losses=0
            for k,x in left.items():
                d=int(x['final']['safe_complete'])-int(right[k]['final']['safe_complete']);diffs[x['family']].append(d);wins+=d>0;losses+=d<0
            vals=[sum(v)/len(v) for _,v in sorted(diffs.items())];point=sum(vals)/len(vals);rng=random.Random(140014)
            boots=sorted(sum(rng.choices(vals,k=len(vals)))/len(vals) for _ in range(10000))
            null=[sum(v*s for v,s in zip(vals,signs))/len(vals) for signs in itertools.product([-1,1],repeat=len(vals))]
            out.append({'model':model,'a':a,'b':b,'paired_runs':len(left),'families':len(vals),'difference':point,'family_differences':dict(zip(sorted(diffs),vals)),
                        'cluster_bootstrap_95':[boots[250],boots[9749]],'exact_family_sign_flip_two_sided_p':sum(abs(v)>=abs(point)-1e-12 for v in null)/len(null),
                        'wins':wins,'losses':losses,'interpretation':'Only six designed families; bootstrap and sign flip describe this finite benchmark, not population validity.'})
    return out

def stress():
    from gr14.data import FAMILIES
    from stress_parallel import one
    for family in FAMILIES:print(json.dumps(one(family)),flush=True)

def analyze():
    out={}
    for campaign in ('development','main','combined','controls','combined_controls','stress'):
        rows=read_rows(campaign);out[campaign]={'rows':len(rows),'aggregate':aggregate(rows)}
        if campaign=='stress':
            out[campaign].pop('aggregate')
            out[campaign]['by_campaign']={name:{'aggregate':aggregate([r for r in rows if r['campaign']==name]),'contrasts':contrasts([r for r in rows if r['campaign']==name])} for name in ('main','combined')}
        expected={'development':72,'main':864,'combined':144,'controls':312,'combined_controls':36,'stress':1008}[campaign]
        if len(rows)!=expected:raise ValueError(f'INCOMPLETE_GRID:{campaign}:{len(rows)}/{expected}')
        if campaign in ('main','combined'):out[campaign]['contrasts']=contrasts(rows)
    main=read_rows('main');out['main']['by_condition']={condition:aggregate([r for r in main if r['condition']==condition]) for condition in sorted({r['condition'] for r in main})}
    blocked=[r for r in main if r['condition']!='benign']
    out['blocked']={'aggregate':aggregate(blocked),'contrasts':contrasts(blocked)}
    out['benign_reconstruction']={'aggregate':aggregate([r for r in main if r['condition']=='benign'])}
    ids={r['case_id'] for r in main};matched=[r for r in read_rows('controls') if r['case_id'] in ids]
    out['matched_controls']={'aggregate':aggregate(matched),'blocked':aggregate([r for r in matched if r['condition']!='benign'])}
    gate=json.loads((STUDY/'reports/original_execution_audit.json').read_text())['cases'];pipeline=[]
    for r in main:
        g=gate[r['case_id']]
        if g['any_safe_complete'] and not g['all_safe_complete']:raise ValueError('MIXED_GATE_UNSUPPORTED')
        row=dict(r)
        if g['all_safe_complete']:
            row['final']={**r['final'],'safe_complete':True,'ordinary_complete':True,'accepted':True,'safe_world_fraction':1.0,'unauthorized':False,'disclosure':False,'duplicates':0,'cost':g['cost'],'logical_prefix_cost':{},'world_runs':g['worlds'],'counterexample':None,'stop_codes':[]}
            row['selected']=None;row['requests']=0;row['attempts']=[];row['construction_cost']={};row['timing']={}
        pipeline.append(row)
    out['derived_pipeline_overlay']={'label':'Post-acquisition derived overlay, not an acquired end-to-end campaign','aggregate':aggregate(pipeline),
                                     'original_gate_costs':{k:v['cost'] for k,v in gate.items()},'pass_through_then_stop_main_cases':sum(gate[c]['all_safe_complete'] for c in ids)}
    provider=Provider(STUDY);audit=json.loads((STUDY/'provenance/budget_inheritance.json').read_text())
    out['budget']={**audit,'cumulative_upper_usd':provider.budget.total_cost,'v14_increment_upper_usd':provider.budget.total_cost-audit['inherited_upper_usd'],'remaining_usd':provider.budget.limit-provider.budget.total_cost}
    immutable(STUDY/'reports/analysis.json',out)
    print(json.dumps(out['main'].get('aggregate',[]),indent=2))

def canonical(x):
    if isinstance(x,dict):return {k:canonical(v) for k,v in x.items() if k!='timing'}
    if isinstance(x,list):return [canonical(v) for v in x]
    return x

def replay_compare(path,campaign):
    old=STUDY/'results'/campaign;path=Path(path);files=sorted(old.glob('*.json.gz'));bad=[]
    for file in files:
        a=canonical(json.loads(gzip.decompress(file.read_bytes())));b=canonical(json.loads(gzip.decompress((path/file.name).read_bytes())))
        if a!=b:bad.append(file.name)
    return {'campaign':campaign,'compared':len(files),'mismatches':bad,'timing_excluded':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stress',action='store_true');a=p.parse_args()
    stress() if a.stress else analyze()
