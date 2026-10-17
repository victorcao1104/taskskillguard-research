"""Whole-stratum rerun after a physical-history correction; original records stay."""
from pathlib import Path
import argparse,json
from concurrent.futures import ThreadPoolExecutor,as_completed
from run import D,assert_frozen,budget,model_run,offline
from sr13.campaign import Provider,MODELS,load_key
from sr13.protocol import MODEL_METHODS
from sr13.data import inputs_for
from sr13.episode import run_episode
from sr13.methods import offline_trial,OFFLINE_METHODS
from sr13.adaptive import search
from sr13.io import read,save,save_trial,digest
from state_amendment import physical_history


def amendment_hashes():
    return {name:digest((D/name).read_bytes()) for name in ('state_amendment.py','corrected_run.py')}


def freeze_amendment():
    assert_frozen();b,a=budget()
    if not(D/'results/main/summary.json').exists():raise ValueError('ORIGINAL_MAIN_NOT_COMPLETE')
    reserve=2.19051+1.69092
    if b.total_cost+reserve>b.limit:raise ValueError('AMENDMENT_WORST_CASE_OVER_BUDGET')
    save(D/'provenance/state_amendment_freeze.json',{
        'source_hashes':amendment_hashes(),'prior_freeze_sha256':digest((D/'provenance/method_freeze_v2.json').read_bytes()),
        'original_main_episodes':1152,'rerun_cases':3,'rerun_episodes':144,'methods':MODEL_METHODS,
        'models':MODELS,'replicates':3,'rerun_reservation_bound_usd':2.19051,
        'remaining_adaptive_bound_usd':1.69092,'new_exposure_at_freeze':b.total_cost-a['inherited_upper_usd'],
        'new_worst_total_usd':b.total_cost-a['inherited_upper_usd']+reserve,
        'selection':'Every main case with uncertain_delivery, all methods and models, irrespective of observed outcomes.',
        'scope':'Only physical trace status of uncommitted prefix sends; permissions, calls, scoring and constructor unchanged.'})


def assert_amended():
    assert_frozen()
    if read(D/'provenance/state_amendment_freeze.json')['source_hashes']!=amendment_hashes():raise ValueError('AMENDMENT_SOURCE_CHANGED')


def rerun(env_file=None,*,cached=False,output=None):
    assert_amended();b,a=budget();provider=Provider(D/'api',b,None if cached else load_key(env_file))
    cases=[c for c in read(D/'data/cases.json') if c['main_model_case'] and c.get('uncertain_delivery')]
    jobs=[(c,m,model,rep) for c in cases for m in MODEL_METHODS for model in MODELS for rep in range(3)]
    jobs.sort(key=lambda j:digest((j[0]['case_id']+j[1]+j[2]+str(j[3])).encode()))
    out=Path(output) if output else D/'results/state_amendment'
    def one(job):
        c,m,model,rep=job;path=out/f"{c['case_id']}--{m}--{model}--r{rep}.json"
        if path.exists():return read(path)
        ins=inputs_for(c)
        def propose(prompt,iteration):return provider.propose(model,prompt,method=m,case_id=c['case_id'],replicate=rep,iteration=iteration,campaign='main_state_amendment')
        result=run_episode(c,m,ins['validation'],ins['final'],propose)
        result.update(model=model,replicate=rep,campaign='main_state_amendment',expected_status=c['expected_status'])
        save_trial(path,result);return result
    results=[]
    with physical_history():
        with ThreadPoolExecutor(max_workers=4) as pool:
            for future in as_completed([pool.submit(one,j) for j in jobs]):
                results.append(future.result())
                if len(results)%16==0:print(json.dumps({'amended_completed':len(results),'planned':len(jobs)}),flush=True)
    save(out/'summary.json',{'episodes':len(results),'safe_complete':sum(r['evaluation']['safe_complete'] for r in results),
                            'new_upper_usd':b.total_cost-a['inherited_upper_usd']})


def adaptive(env_file=None,*,cached=False,output=None):
    assert_amended();path=D/'data/adaptive_search.json'
    with physical_history():
        if not path.exists():save(path,search())
        model_run(env_file,cached=cached,output=output,cases_override=read(path)['selected'])


def offline_corrected(output=None):
    assert_amended()
    out=Path(output) if output else D/'results/offline_corrected';summaries=[]
    with physical_history():
        for c in read(D/'data/cases.json'):
            ins=inputs_for(c)
            for method in OFFLINE_METHODS:
                path=out/f"{c['case_id']}--{method}.json"
                if path.exists():r=read(path)
                else:
                    catalogue=read(D/'reference_catalogue'/f"{c['case_id']}.json")['deployed_program'] if method=='catalogue_oracle' else None
                    # A stop-after-block baseline must pass through an unblocked benign helper.
                    passthrough=c['attack']=='benign' and method in {'stop','delete_continue'}
                    r=offline_trial('retry_original' if passthrough else method,c,ins['validation'],ins['final'],catalogue_program=catalogue)
                    r['method']=method;r['unblocked_passthrough']=passthrough
                    save_trial(path,r)
                summaries.append({k:r[k] for k in ('case_id','method','accepted','evaluation','search_cost')})
    save(out/'summary.json',summaries);print(json.dumps({'corrected_offline_trials':len(summaries)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','rerun','adaptive','offline']);p.add_argument('--env-file',type=Path)
    p.add_argument('--cached',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    if a.command=='freeze':freeze_amendment()
    elif a.command=='rerun':rerun(a.env_file,cached=a.cached,output=a.output)
    elif a.command=='adaptive':adaptive(a.env_file,cached=a.cached,output=a.output)
    else:offline_corrected(a.output)
