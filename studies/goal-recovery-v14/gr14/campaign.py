"""Prespecified paired acquisition, complete-grid admission and cached replay."""
import argparse
import gzip
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from .data import FAMILIES,MAIN,CONDITIONS,make_case,inputs_for
from .protocol import METHODS,MODELS,payload
from .provider import Provider,request_job,immutable,INPUT_CAP,OUTPUT_CAP,ROOT
from .recovery import transform_compute
from .verify import evaluate
from .compiler import compile_program
STUDY=Path(__file__).resolve().parents[1]

def grid(campaign):
    if campaign=='development':
        cases=[make_case(f,c) for f,c in [('dev_cover','benign'),('dev_cover','forbidden'),('dev_cover','mixed'),('dev_quality','confirmed'),('dev_quality','destroyed'),('dev_quality','unknown_query')]];reps=1;methods=METHODS
    elif campaign=='main':cases=[make_case(f,c) for f in FAMILIES for c in MAIN[f]];reps=3;methods=METHODS
    elif campaign=='combined':cases=[make_case(f,c) for f in FAMILIES for c in ('guard_mix','cache_destroy')];reps=2;methods=('full','repair_state','replan_state')
    else:raise ValueError('UNKNOWN_CAMPAIGN')
    jobs=[(c,m,model,r) for c in cases for m in methods for model in MODELS for r in range(reps)]
    return sorted(jobs,key=lambda x:hashlib.sha256((x[0]['case_id']+str(x[1:])).encode()).hexdigest())

def add(total,new):
    for k,v in new.items():total[k]=total.get(k,0)+v

def episode(case,method,model,rep,campaign,provider):
    started=time.perf_counter();cpu=time.thread_time();attempts=[];selected=None;construction={};api_seconds=0
    state=method in ('repair_state','replan_state','full','full_no_reuse');reuse=method!='full_no_reuse'
    validation=inputs_for(case,'validation');ins=validation[0];requests=0
    for iteration in range(3):
        if method.startswith('full') and iteration==0:
            t=transform_compute(case['skill']['compute'],case['task'])
            program={'compute':t['code'],'effects':'pass'};attempt={'origin':'source_bootstrap','transformation':t,'program':program}
        else:
            try:job=request_job(model,payload(case,ins,method,attempts,iteration),method=method,case_id=case['case_id'],replicate=rep,iteration=iteration,campaign=campaign)
            except ValueError as e:
                attempts.append({'origin':'model','feedback':{'code':str(e)}});break
            raw=provider.call(job);requests+=1;api_seconds+=raw.get('elapsed_seconds',0)
            parsed=raw['parsed'];attempt={'origin':'model','response':raw,'program':parsed.get('program')}
            if parsed['status']!='candidate':
                attempt['feedback']={'code':'MODEL_'+parsed['status'].upper(),'diagnostic':parsed.get('diagnostic'),'reason':parsed.get('reason')};attempts.append(attempt)
                if parsed['status'] in ('stop','clarify') or raw['raw_status'] not in ('completed','incomplete'):break
                continue
            program=parsed['program']
        checked=evaluate(program,case,validation,state=state,reuse=reuse,early=True)
        add(construction,checked['cost']);add(construction,{'logical_prefix_steps':checked['logical_prefix_cost'].get('steps',0)})
        attempt['validation']=checked;attempt['feedback']=checked['counterexample'];attempts.append(attempt)
        if checked['accepted']:selected=program;break
    # No candidate passes => no continuation executes; never auto-recover via empty wrapper.
    final=evaluate(selected or {'compute':'pass','effects':'pass'},case,inputs_for(case,'final'),state=state if selected else False,reuse=reuse)
    return {'case_id':case['case_id'],'family':case['family'],'condition':case['condition'],'expected_status':case['expected_status'],
            'method':method,'model':model,'replicate':rep,'campaign':campaign,'selected':selected,'attempts':attempts,
            'requests':requests,'construction_cost':construction,'final':final,'state':state,'reuse':reuse,
            'timing':{'wall_seconds':time.perf_counter()-started,'cpu_seconds':time.thread_time()-cpu,'api_seconds':api_seconds}}

def save_result(path,result):
    # Full evidence in compressed file, small table row for analysis. Never overwrite.
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    evidence=gzip.compress((json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode(),mtime=0)
    trace=path.with_suffix('.json.gz')
    if trace.exists():raise ValueError('RESULT_ALREADY_EXISTS')
    trace.write_bytes(evidence)
    summary={k:v for k,v in result.items() if k not in ('attempts','final')}
    summary['final']={k:v for k,v in result['final'].items() if k!='records'}
    summary['attempts']=[{k:v for k,v in a.items() if k!='validation'}|({'validation':{k:v for k,v in a['validation'].items() if k!='records'}} if 'validation' in a else {}) for a in result.get('attempts',[])]
    immutable(path,summary)

def source_hashes():
    files=list((STUDY/'gr14').glob('*.py'))+list((STUDY/'tests').glob('*.py'))+[STUDY/'design.md',STUDY/'plan.md']
    files += [ROOT/'src/tsg/models.py',ROOT/'src/tsg/models_v3.py',ROOT/'src/tsg/budget_v4.py',ROOT/'scripts/run_phase5.py']
    return {str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def freeze(campaign,jobs,provider):
    upper=sum((INPUT_CAP*(.125 if model=='gpt-6-luna' else .4)+OUTPUT_CAP*(.5 if model=='gpt-6-luna' else 1.6))/1e6*(2 if m.startswith('full') else 3) for _,m,model,_ in jobs)
    path=STUDY/'provenance'/f'{campaign}_freeze.json'
    manifest={'campaign':campaign,'episodes':len(jobs),'source_hashes':source_hashes(),
              'grid':[(c['case_id'],m,model,r) for c,m,model,r in jobs],
              'max_reservation_usd':upper,'input_byte_cap':INPUT_CAP,'output_token_cap':OUTPUT_CAP,
              'independent_families':2 if campaign=='development' else 6,'seeds':{'validation':list(range(101,107)),'final':list(range(1001,1017)),'stress':list(range(2001,2033))}}
    if not path.exists() and upper>provider.budget.limit-provider.budget.total_cost:raise ValueError('WHOLE_GRID_BUDGET_ADMISSION_FAILED')
    immutable(path,manifest)
    cases={c['case_id']:c for c,_,_,_ in jobs}
    for c in cases.values():immutable(STUDY/'data'/f"{c['case_id']}.json",{'case':c,'inputs':{phase:inputs_for(c,phase) for phase in ('validation','final','stress')}})
    return manifest

def run(campaign,live=False,out=None):
    provider=Provider(STUDY,live=live);jobs=grid(campaign);manifest=freeze(campaign,jobs,provider)
    out=Path(out) if out else STUDY/'results'/campaign
    out.mkdir(parents=True,exist_ok=True)
    def one(job):
        c,m,model,r=job;name=f"{c['case_id']}--{m}--{model}--r{r}"
        if (out/(name+'.json')).exists():return 'existing'
        result=episode(c,m,model,r,campaign,provider);save_result(out/(name+'.json'),result)
        return result['final']['safe_complete']
    completed=0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(one,j) for j in jobs]):
            f.result();completed+=1
            if completed%6==0:print(json.dumps({'campaign':campaign,'completed':completed,'total':len(jobs),'upper_usd':provider.budget.total_cost}),flush=True)
    print(json.dumps({'complete':campaign,'episodes':completed,'remaining_usd':provider.budget.limit-provider.budget.total_cost}),flush=True)

def controls(out=None):
    out=Path(out) if out else STUDY/'results/controls';out.mkdir(parents=True,exist_ok=True)
    for family in FAMILIES:
        for condition in CONDITIONS:
            c=make_case(family,condition)
            for method in ('stop','compiler','compiler_fresh','source_state'):
                path=out/f'{c["case_id"]}--{method}.json'
                if path.exists():continue
                p={'compute':'pass','effects':'pass'} if method=='stop' else compile_program(c['task'],reuse=method!='compiler_fresh')
                if method=='source_state':p={'compute':transform_compute(c['skill']['compute'],c['task'])['code'],'effects':'pass'}
                phases={phase:evaluate(p,c,inputs_for(c,phase),state=method=='source_state') for phase in ('validation','final','stress')}
                save_result(path,{'case_id':c['case_id'],'family':family,'condition':condition,'expected_status':c['expected_status'],'method':method,'selected':p,'final':phases.pop('final'),'other_phases':phases})
        print(json.dumps({'controls_family_done':family}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('campaign',choices=['development','main','combined','controls']);p.add_argument('--live',action='store_true');p.add_argument('--out');a=p.parse_args()
    controls(a.out) if a.campaign=='controls' else run(a.campaign,a.live,a.out)
