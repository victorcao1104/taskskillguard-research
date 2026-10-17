"""Matched four-method transport sensitivity; no changes to action semantics."""
from pathlib import Path
import argparse,json
from concurrent.futures import ThreadPoolExecutor,as_completed
from run import D,budget
from corrected_run import assert_amended
from sr13.campaign import MODELS,load_key
from sr13.data import inputs_for
from sr13.episode import run_episode
from sr13.protocol import MODEL_METHODS
from sr13.io import read,save,save_trial,digest
from state_amendment import physical_history
from robust_protocol import NormalizedProvider

METHODS=MODEL_METHODS


def hashes():return {n:digest((D/n).read_bytes()) for n in ('robust_run.py','robust_protocol.py')}


def freeze():
    assert_amended()
    if not(D/'results/adaptive/summary.json').exists():raise ValueError('EARLIER_ACQUISITION_STILL_ACTIVE')
    b,a=budget();bound=17.52408
    if b.total_cost+bound>b.limit:raise ValueError('ROBUST_GRID_WORST_CASE_OVER_BUDGET')
    save(D/'provenance/robust_protocol_freeze.json',{'source_hashes':hashes(),'cases':24,'methods':METHODS,
         'models':MODELS,'replicates':3,'episodes':1152,'max_requests_per_model':1368,
         'reservation_bound_usd':bound,'exposure_before':b.total_cost-a['inherited_upper_usd'],
         'worst_new_total_usd':b.total_cost-a['inherited_upper_usd']+bound,
         'selection':'All original main cases, eight methods including ablations, both models, all three repeats; not selected by outcomes.',
         'change':'Last completed output-text selection when that is the sole strict error; one trailing brace/comma after a complete array. No semantic repairs or validator relaxations.'})


def run(env_file=None,*,cached=False,output=None,adaptive=False):
    assert_amended()
    if hashes()!=read(D/'provenance/robust_protocol_freeze.json')['source_hashes']:raise ValueError('ROBUST_SOURCE_CHANGED')
    b,a=budget();provider=NormalizedProvider(D/'api',b,None if cached else load_key(env_file))
    if adaptive:
        if not(D/'results/robust_protocol/summary.json').exists():raise ValueError('MAIN_NORMALIZED_ACQUISITION_INCOMPLETE')
        if not cached and b.total_cost+1.69092>b.limit:raise ValueError('ADAPTIVE_WORST_CASE_OVER_BUDGET')
        cases=read(D/'data/adaptive_search.json')['selected'];methods=('repair','replan','plain_cegis','contract');reps=2;campaign='robust_adaptive'
    else:
        cases=[c for c in read(D/'data/cases.json') if c['main_model_case']];methods=METHODS;reps=3;campaign='robust_protocol'
    jobs=[(c,m,model,rep) for c in cases for m in methods for model in MODELS for rep in range(reps)]
    jobs.sort(key=lambda j:digest((j[0]['case_id']+j[1]+j[2]+str(j[3])).encode()))
    out=Path(output) if output else D/'results'/campaign
    def one(job):
        c,m,model,rep=job;path=out/f"{c['case_id']}--{m}--{model}--r{rep}.json"
        if path.exists():return read(path)
        ins=inputs_for(c)
        def propose(prompt,iteration):return provider.propose(model,prompt,method=m,case_id=c['case_id'],replicate=rep,iteration=iteration,campaign=campaign)
        result=run_episode(c,m,ins['validation'],ins['final'],propose)
        result.update(model=model,replicate=rep,campaign=campaign,expected_status=c['expected_status'])
        save_trial(path,result);return result
    results=[]
    with physical_history():
        with ThreadPoolExecutor(max_workers=4) as pool:
            for future in as_completed([pool.submit(one,j) for j in jobs]):
                results.append(future.result())
                if len(results)%24==0:print(json.dumps({'robust_completed':len(results),'planned':len(jobs),'new_upper_usd':b.total_cost-a['inherited_upper_usd']}),flush=True)
    summary={'episodes':len(results),'safe_complete':sum(r['evaluation']['safe_complete'] for r in results),
             'new_upper_usd':b.total_cost-a['inherited_upper_usd'],'remaining_usd':b.limit-b.total_cost}
    save(out/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','run','adaptive']);p.add_argument('--env-file',type=Path)
    p.add_argument('--cached',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    if a.command=='freeze':freeze()
    else:run(a.env_file,cached=a.cached,output=a.output,adaptive=a.command=='adaptive')
