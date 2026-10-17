"""Freeze, acquire and replay the v13 synthetic study. Never overwrite evidence."""
from pathlib import Path
import argparse,hashlib,json,sys,subprocess
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
from sr13.io import save,read,digest,encoded,save_trial,source_hashes,semantic
from sr13.data import make_case,inputs_for,DEV_TASKS,DEV_ATTACKS,TEST_TASKS,ATTACKS
from sr13.methods import offline_trial,OFFLINE_METHODS
from sr13.protocol import MODEL_METHODS
from sr13.episode import run_episode
from sr13.campaign import campaign_budget,Provider,MODELS,MAX_OUTPUT,MAX_INPUT_BYTES,load_key

D=Path(__file__).resolve().parent;ROOT=D.parents[1]
MAIN_SELECTION={
 'regional_value':['benign','secret_guard','partial_write','no_permission'],
 'join_value':['benign','lost_value','confirmed_send','unknown_query'],
 'filtered_join':['benign','payload_mix','unknown_no_query','multi_fault'],
 'group_statistics':['benign','cleanup_done','insufficient_budget','prompt_poison'],
 'ordered_margin':['benign','payload_constant','prior_leak','unused_forbidden'],
 'two_stage_arithmetic':['benign','combined_guard_mix','unknown_query','confirmed_send']}


def freeze():
    manifest={'date_utc':datetime.now(timezone.utc).isoformat(),'study':'v13-stateful-recovery',
        'source_hashes':source_hashes(D),'base':'2ee03bf7f6761784a41fb98b96086b78e85e0126',
        'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'main_selection':MAIN_SELECTION,'models':MODELS,'methods':MODEL_METHODS,'replicates':3,
        'max_candidates':3,'max_output_tokens':MAX_OUTPUT,'input_byte_reservation_cap':MAX_INPUT_BYTES,
        'main_max_requests_per_model':1368,'main_reservation_bound_usd':17.52408,
        'development_max_requests_per_model':11,'development_reservation_bound_usd':.14091,
        'adaptive_max_requests_per_model':132,'adaptive_reservation_bound_usd':1.69092,
        'combined_worst_case_bound_usd':19.35591,'new_cap_usd':20,
        'validation_seeds':[101,102,103],'final_seeds':list(range(1001,1009)),
        'test_cases_generated':False,'notes':'Method and generator rules frozen before heldout case materialization. Developer-authored structural holdouts; not blind human validation.'}
    save(D/'provenance/method_freeze.json',manifest);print(json.dumps({'frozen_sources':len(manifest['source_hashes']),'planned_worst_usd':19.35591}))


def assert_frozen():
    f=read(D/'provenance/method_freeze.json')
    if source_hashes(D)!=f['source_hashes']:raise ValueError('FROZEN_SOURCE_CHANGED')
    return f


def prepare():
    frozen=assert_frozen();cases=[]
    for template in TEST_TASKS:
        for attack in ('benign',)+ATTACKS:
            c=make_case(template,attack);c['main_model_case']=attack in MAIN_SELECTION[template]
            cases.append(c)
    save(D/'data/cases.json',cases)
    save(D/'data/inputs.json',{c['case_id']:inputs_for(c) for c in cases})
    for c in cases:
        folder=D/'data/packages'/c['case_id'];folder.mkdir(parents=True,exist_ok=True)
        text=c['skill_md']+'\n';md=folder/'SKILL.md'
        if not md.exists():md.write_text(text,encoding='utf-8')
        elif md.read_text(encoding='utf-8')!=text:raise ValueError('PACKAGE_CHANGED')
        save(folder/'scripts/main.json',c['skill'])
    save(D/'data/manifest.json',{'cases':len(cases),'main_model_cases':sum(c['main_model_case'] for c in cases),
         'families':len(TEST_TASKS),'attacks':len(ATTACKS),'freeze_sha256':digest((D/'provenance/method_freeze.json').read_bytes()),
         'cases_sha256':digest((D/'data/cases.json').read_bytes()),'generated_utc':datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'heldout_cases':len(cases),'main_model_cases':sum(c['main_model_case'] for c in cases)}))


def budget():
    b,a=campaign_budget(ROOT/'studies/skill-security-v12/api/budget.jsonl',D/'api/budget.jsonl')
    save(D/'provenance/budget_authorization.json',a);return b,a


def offline(output=None):
    assert_frozen();out=Path(output) if output else D/'results/offline';cases=read(D/'data/cases.json');inputs=read(D/'data/inputs.json')
    summaries=[]
    for c in cases:
        ins=inputs[c['case_id']]
        for method in OFFLINE_METHODS:
            path=out/f"{c['case_id']}--{method}.json"
            if path.exists():r=read(path)
            else:
                catalogue=None
                if method=='catalogue_oracle':
                    ref=D/'reference_catalogue'/f"{c['case_id']}.json"
                    if ref.exists():prepared=read(ref)
                    else:
                        prepared=offline_trial('goal_direct',c,ins['validation'],ins['final'])
                        save_trial(ref,prepared)
                    catalogue=prepared['deployed_program']
                r=offline_trial(method,c,ins['validation'],ins['final'],catalogue_program=catalogue);save_trial(path,r)
            summaries.append({k:r[k] for k in ('case_id','method','accepted','evaluation','search_cost')})
    save(out/'summary.json',summaries);print(json.dumps({'offline_trials':len(summaries)}))


def model_run(env_file,*,cached=False,development=False,output=None,campaign='main',cases_override=None):
    assert_frozen();b,a=budget();provider=Provider(D/'api',b,None if cached else load_key(env_file))
    if development:
        cases=[make_case('dev_sum','partial_write')];methods=('repair','replan','plain_cegis','contract');reps=1;campaign='development'
    elif cases_override is not None:
        cases=cases_override;methods=('repair','replan','plain_cegis','contract');reps=2;campaign='adaptive'
    else:
        cases=[c for c in read(D/'data/cases.json') if c['main_model_case']];methods=MODEL_METHODS;reps=3
    jobs=[(c,m,model,rep) for c in cases for m in methods for model in MODELS for rep in range(reps)]
    jobs.sort(key=lambda j:digest((j[0]['case_id']+j[1]+j[2]+str(j[3])).encode()))
    out=Path(output) if output else D/'results'/campaign
    def one(job):
        c,m,model,rep=job;identity=c['case_id']+'--'+m+'--'+model+'--r'+str(rep)
        path=out/(identity+'.json')
        if path.exists():return read(path)
        ins=inputs_for(c)
        def propose(prompt,iteration):return provider.propose(model,prompt,method=m,case_id=c['case_id'],replicate=rep,iteration=iteration,campaign=campaign)
        result=run_episode(c,m,ins['validation'],ins['final'],propose)
        result.update(model=model,replicate=rep,campaign=campaign,expected_status=c['expected_status'])
        save_trial(path,result);return result
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one,j) for j in jobs]):
            results.append(future.result())
            if len(results)%16==0:print(json.dumps({'completed':len(results),'planned':len(jobs),'new_upper_usd':b.total_cost-a['inherited_upper_usd']}),flush=True)
    summary={'episodes':len(results),'model_calls':sum(r['model_calls'] for r in results),
         'accepted':sum(r['accepted'] for r in results),'safe_complete':sum(r['evaluation']['safe_complete'] for r in results),
         'new_upper_usd':b.total_cost-a['inherited_upper_usd'],'remaining_usd':b.limit-b.total_cost,'invoice':False}
    # Run-level summary includes cumulative ledger exposure at completion; immutable campaign outputs.
    save(out/'summary.json',summary);print(json.dumps(summary),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','prepare','offline','development','models','replay_models'])
    p.add_argument('--env-file',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.command=='freeze':freeze()
    elif a.command=='prepare':prepare()
    elif a.command=='offline':offline(a.output)
    else:model_run(a.env_file,cached=a.command=='replay_models',development=a.command=='development',output=a.output)

if __name__=='__main__':main()
