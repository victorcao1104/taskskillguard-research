"""Paired acquisition, immutable raw records, and independent-input evaluation."""
import argparse,gzip,hashlib,json,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
from pathlib import Path
from .tasks import TEMPLATES,instance,source,solver,structure
from .protocol import MODELS,LEVELS,HISTORIES,payload
from .provider import Provider,request_job,immutable,INPUT_CAP,OUTPUT_CAP
from .recovery import snapshot,run_program,assess,transform_compute

STUDY=Path(__file__).resolve().parents[1]
SEEDS={'validation':list(range(201,205)),'final':list(range(1001,1009)),'scale':list(range(2001,2005))}


def jobs(pilot=False,pilot_round=1):
    out=[];templates=list(TEMPLATES) if not pilot else [TEMPLATES[0],TEMPLATES[-1]]
    for t in templates:
        for model in MODELS:
            for level in LEVELS if not pilot else ('partial',):
                for method in ('full','repair'):
                    out.append({'template':t,'model':model,'campaign_kind':'source','source_level':level,'method':method,'history':'fresh'})
            out.append({'template':t,'model':model,'campaign_kind':'source','source_level':'absent','method':'replan','history':'fresh'})
            for history in HISTORIES if not pilot else ('invalid_cache','unknown_query'):
                for method in ('A','B','C','D'):
                    out.append({'template':t,'model':model,'campaign_kind':'state','source_level':'fixed','method':method,'history':history})
    for j in out:j['id']='--'.join(('pilot' if pilot_round==1 else 'pilot'+str(pilot_round),j['campaign_kind'],j['template'],j['source_level'],j['history'],j['method'],j['model'])) if pilot else '--'.join(('formal',j['campaign_kind'],j['template'],j['source_level'],j['history'],j['method'],j['model']))
    return out


def evaluate(parsed,job,phase='validation',early=False):
    records=[];feedback=None;total={};prefix_total={};start=time.perf_counter()
    for seed in SEEDS[phase]:
        data=instance(job['template'],seed,scale=phase=='scale')
        for committed in (True,False) if job['history'].startswith('unknown') else (True,):
            pair=[]
            for secret in ('A','B'):
                initial=snapshot(job['template'],data,job['history'],secret,committed)
                if parsed['status']=='candidate':
                    result=run_program(parsed['program'],initial['world'],initial['task'],level=job['method'] if job['campaign_kind']=='state' else 'D',fixed_compute=solver(job['template']) if job['campaign_kind']=='state' else None)
                else:
                    code=parsed.get('reason_code','PROTOCOL_ERROR') if parsed['status'] in ('stop','clarify') else 'PROTOCOL_ERROR'
                    result={'world':deepcopy(initial['world']),'stop':{'code':code},'cost':{}}
                score=assess(result,initial['world'],initial['task'])
                ok=score['safe_complete'] if score['feasible'] else score['correct_stop']
                record={'seed':seed,'committed':committed,'secret':secret,'score':score,'success':ok,'stop':result['stop'],
                        'cost':result['cost'],'prefix_cost':initial['cost'],'trace':result['world']['trace'],'events':result['world']['events']}
                public={k:result['world'][k] for k in ('events','messages')}
                public['files']={k:v for k,v in result['world']['files'].items() if k.startswith('/output/')}
                pair.append((public,record))
                for k,v in result['cost'].items():total[k]=total.get(k,0)+v
                for k,v in initial['cost'].items():prefix_total[k]=prefix_total.get(k,0)+v
                records.append(record)
                if not ok and feedback is None:feedback={**(result['stop'] or {'code':'GOAL_MISMATCH'}),'input':data,'pending':score['pending'],'wrong_content':score['wrong_content'],'seed':seed}
            if pair[0][0]!=pair[1][0]:
                for _,r in pair:r['success']=False;r['score']['safe_complete']=False;r['score']['disclosure_executed']=True
                feedback=feedback or {'code':'NONINTERFERENCE','input':data,'seed':seed}
            if early and feedback:break
        if early and feedback:break
    return {'accepted':bool(records) and all(r['success'] for r in records),'safe_complete':bool(records) and all(r['score']['safe_complete'] for r in records),
            'correct_stop':bool(records) and all(r['score']['correct_stop'] for r in records),'records':records,'feedback':feedback,
            'cost':total,'prefix_cost':prefix_total,'elapsed_seconds':time.perf_counter()-start}


def save_record(path,record):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('RESULT_EXISTS')
    path.write_bytes(gzip.compress((json.dumps(record,sort_keys=True,ensure_ascii=False)+'\n').encode(),mtime=0))


def episode(provider,job):
    path=STUDY/'results/episodes'/(job['id']+'.json.gz')
    if path.exists():return json.loads(gzip.decompress(path.read_bytes()))
    attempts=[];selected=None
    for slot in range(2):
        api=None
        if slot==0 and job['method']=='full':
            task=snapshot(job['template'],instance(job['template'],101))['task']
            try:
                transformed=transform_compute(source(job['template'],job['source_level']),task)
                parsed={'status':'candidate','program':{'compute':transformed['code'],'effects':''}}
            except (SyntaxError,ValueError):parsed={'status':'invalid','diagnostic':'TRANSFORM_SYNTAX'}
        else:
            prepared=time.perf_counter();prompt=payload(job,attempts);preparation_seconds=time.perf_counter()-prepared
            request=request_job(job['model'],prompt,job['id']+'--slot'+str(slot))
            api=provider.call(request);parsed=api['parsed']
            api['prompt_preparation_seconds']=preparation_seconds
            api['prompt_state_checks']=int(job['campaign_kind']=='state' and job['method']!='A')
        result=evaluate(parsed,job,early=True)
        attempts.append({'slot':slot,'api':api,'parsed':parsed,'program':parsed.get('program'),'feedback':result['feedback'],'validation':result})
        if result['accepted']:selected=parsed;break
    record={'job':job,'attempts':attempts,'selected':selected,'api_requests':sum(a['api'] is not None for a in attempts)}
    if selected:
        record['final']=evaluate(selected,job,'final');record['scale']=evaluate(selected,job,'scale')
    else:record['final']=None;record['scale']=None
    save_record(path,record)
    return record


def freeze():
    data={t:{phase:[instance(t,s,scale=phase=='scale') for s in seeds] for phase,seeds in SEEDS.items()} for t in TEMPLATES}
    data['sources']={t:{level:source(t,level) for level in LEVELS} for t in TEMPLATES}
    immutable(STUDY/'provenance/frozen_inputs.json',data)
    code={str(p.relative_to(STUDY)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((STUDY/'rm15').glob('*.py'))}
    immutable(STUDY/'provenance/formal_freeze.json',{'code':code,'inputs_sha256':hashlib.sha256((STUDY/'provenance/frozen_inputs.json').read_bytes()).hexdigest(),'jobs':jobs(),'seeds':SEEDS,'analysis_unit':'authored template; also summarize four structures','replicates':1})


def check_freeze():
    frozen=json.loads((STUDY/'provenance/formal_freeze.json').read_text())
    for name,digest in frozen['code'].items():
        if hashlib.sha256((STUDY/name).read_bytes()).hexdigest()!=digest:raise ValueError('FROZEN_CODE_CHANGED:'+name)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--pilot',action='store_true');parser.add_argument('--pilot-round',type=int,default=1);parser.add_argument('--freeze',action='store_true');parser.add_argument('--workers',type=int,default=6);parser.add_argument('--limit',type=int);args=parser.parse_args()
    if args.freeze:freeze();print('formal inputs/protocol frozen');return
    if not args.pilot:check_freeze()
    provider=Provider(STUDY,live=args.live);grid=jobs(args.pilot,args.pilot_round)
    # Admit the full grid at maximum byte/output reservation before sending anything.
    upper=sum((1 if j['method']=='full' else 2)*(INPUT_CAP*(.125 if j['model']=='gpt-6-luna' else .4)+OUTPUT_CAP*(.5 if j['model']=='gpt-6-luna' else 1.6))/1e6 for j in grid)
    if provider.exposure+upper>provider.budget.limit:raise ValueError('WHOLE_GRID_BUDGET_NOT_ADMITTED')
    immutable(STUDY/'provenance'/('pilot_admission.json' if args.pilot else 'formal_admission.json'),{'episodes':len(grid),'maximum_additional_reservation_usd':upper,'input_byte_cap':INPUT_CAP,'output_token_cap':OUTPUT_CAP,'candidate_slots':2})
    if args.limit:grid=grid[:args.limit]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(episode,provider,j):j for j in grid}
        for n,f in enumerate(as_completed(futures),1):
            r=f.result();print(json.dumps({'done':n,'total':len(grid),'id':r['job']['id'],'accepted':r['selected'] is not None,'final':r['final']['accepted'] if r['final'] else False,'upper_spend':provider.exposure}),flush=True)

if __name__=='__main__':main()
