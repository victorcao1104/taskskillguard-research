"""Two-model trusted P planning, semantic-format controls, and closed-loop ablation."""
import argparse
import concurrent.futures
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FROZEN_INPUT_MANIFESTS = {
    'phase2_pipeline_api': 'phase2_pipeline_api-2026-10-14T23-08-21.741110+00-00.json',
    'development': 'development-2026-10-14T22-16-26.307819+00-00.json',
    'validation': 'validation-2026-10-14T22-16-33.520818+00-00.json',
    'held_out': 'held_out-2026-10-14T22-16-35.693046+00-00.json',
}
sys.path.insert(0,str(ROOT/'src'))
from tsg.models import Client,Budget,load_key
from tsg.policy import Policy,Rule
from tsg.pipeline_v2 import FEATURES,run_pipeline
from tsg.trusted_planner_v2 import planner_payload,P_SYSTEM,parse_plan
from tsg.sandbox import run_case
from run_experiment import dump_jsonl,run_manifest,graph_input


def load(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]


def validate_frozen_inputs(root=ROOT):
    """Fail closed against the explicitly identified final input manifests."""
    root = Path(root)
    dataset = 'data/benchmark/synthetic_cases.jsonl'
    digest = hashlib.sha256((root / dataset).read_bytes()).hexdigest()
    audit = {'synthetic_cases_sha256': digest, 'manifests': {}}
    for phase, filename in FROZEN_INPUT_MANIFESTS.items():
        path = root / 'results/run_manifests' / filename
        try:
            raw = path.read_bytes()
            manifest = json.loads(raw)
            hashes = [v for k, v in manifest['files_sha256'].items()
                      if k.replace('\\', '/') == dataset]
            if manifest.get('phase') != phase or len(hashes) != 1:
                raise ValueError('FROZEN_INPUT_AMBIGUOUS: ' + phase)
            if hashes[0] != digest:
                raise ValueError('FROZEN_INPUT_MISMATCH: ' + phase)
        except (OSError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            raise ValueError('FROZEN_INPUT_UNVERIFIABLE: ' + phase) from exc
        audit['manifests'][phase] = {'path': str(path.relative_to(root)),
                                     'sha256': hashlib.sha256(raw).hexdigest(),
                                     'synthetic_cases_sha256': hashes[0]}
    return audit


def apply_q_plan_status(record, q_plan):
    record['q_plan_status'] = 'valid' if isinstance(q_plan, list) else 'unresolved'
    if record['q_plan_status'] != 'valid' and record.get('status') == 'valid':
        record['original_pipeline_status'] = record['status']
        record['status'] = 'unresolved_q_plan'


def infer(client,case,model,variant,form,replicate):
    payload=planner_payload(case,form)
    if variant in {'v0','v1'}:
        # Description heading order/blank lines change, action order does not.
        skill=case['skill_text']
        if form!='json':
            transformed='<!-- Documentation-only layout variant -->\n\n'+skill.replace('## Workflow','\n## Workflow\n')
            assert [s for s in transformed.splitlines() if s.startswith('- [')]==[s for s in skill.splitlines() if s.startswith('- [')]
            skill=transformed
        payload['untrusted_skill']=skill
    if variant=='v1':
        payload['untrusted_graph']=graph_input(case)
    raw=client.call(model,P_SYSTEM,json.dumps(payload),tag='phase2-planner:'+case['case_id']+':'+variant+':'+form,
                    max_output=1400,replicate=replicate)
    result={'case_id':case['case_id'],'family_id':case['family_id'],'split':case['split'],
            'model':model,'variant':variant,'form':form,'replicate':replicate,
            'request_hash':raw['request_hash'],'status':'unresolved','equivalence_oracle':'finite_task_spec_roundtrip_and_identical_action_sequence',
            'p_sees_untrusted':variant!='v5'}
    try:
        prediction,actions=parse_plan(raw.get('text',''),case)
        scope=Policy(tuple(Rule(**r) for r in prediction['rules']))
        if not scope.valid():
            raise ValueError('unsupported scope')
        result.update(status='valid',prediction=prediction,scope_policy=scope.to_dict(),reference_actions=actions)
    except (ValueError,TypeError,KeyError):
        pass
    return result


def platform_lease(case,policy):
    if policy is None:
        return None
    result=copy.deepcopy(policy)
    for rule in result['rules']:
        # Fixed trusted platform lifecycle, applied equally to both contract
        # conditions. This cannot add or repair any operation/resource scope.
        rule.update(starts=0,expires=3 if rule['operation'] in {'file.read','secret.read'} else 20,max_uses=1)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--api',action='store_true');p.add_argument('--env-file',type=Path)
    p.add_argument('--workers',type=int,default=8);p.add_argument('--limit',type=int)
    a=p.parse_args();cases=load(ROOT/'data/benchmark/synthetic_cases.jsonl')
    input_validation = None if a.api else validate_frozen_inputs(ROOT)
    if a.limit:cases=cases[:a.limit]
    out=ROOT/'results/phase2/pipeline';out.mkdir(parents=True,exist_ok=True)
    if input_validation is not None:
        (out/'frozen_input_validation.json').write_text(json.dumps(input_validation,indent=2),encoding='utf-8')
    run_manifest('phase2_pipeline_api' if a.api else 'phase2_pipeline_runtime')
    if a.api:
        client=Client(load_key(a.env_file),ROOT/'results/api/raw',Budget(ROOT/'results/api/budget.jsonl',20))
        jobs=[]
        for case in cases:
            for model in ('gpt-6-luna','gpt-4.1-mini'):
                for variant in ('v0','v5'):
                    for replicate in (0,1):
                        jobs.append((case,model,variant,'json',replicate))
                if '-0-' in case['case_id'] and case['scenario'] in {'low','high','claim_inflation','authority_spoofing','artificial_dependency','data_flow_misuse','optional_cache'}:
                    for variant in ('v0','v1','v5'):
                        if variant=='v1':jobs.append((case,model,variant,'json',0))
                        for form in ('fields','indented_json'):
                            jobs.append((case,model,variant,form,0))
        results=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
            fs=[pool.submit(infer,client,*job) for job in jobs]
            for i,f in enumerate(concurrent.futures.as_completed(fs),1):
                results.append(f.result());dump_jsonl(out/'planner.jsonl',results)
                if i%30==0 or i==len(jobs):
                    print(json.dumps({'planner_completed':i,'total':len(jobs),'budget_upper_usd':client.budget.total_cost}),flush=True)
        return
    saved=load(out/'planner.jsonl')
    plans={(r['case_id'],r['model'],r['variant'],r['form'],r['replicate']):r for r in saved}
    classifications={};q_plans={};old_contracts={}
    for phase in ('development','validation','held_out'):
        for r in load(ROOT/f'results/{phase}/detection.jsonl'):
            classifications[(r['case_id'],r['model'],r['variant'],r['replicate'])]=r.get('prediction')
        for r in load(ROOT/f'results/{phase}/plans.jsonl'):
            if not r['textual_guard']:
                q_plans[(r['case_id'],r['model'])] = r.get('action_ids') if r.get('status') == 'valid' else None
        for r in load(ROOT/f'results/{phase}/contracts.jsonl'):
            old_contracts[(r['case_id'],r['model'],r['separated'])]=r
    # Required E3 special condition: original LLM scope contracts are really
    # executed, without repair by the ground-truth policy. Oracle stays scorer.
    closed=[]
    for case in cases:
        for model in ('gpt-6-luna','gpt-4.1-mini'):
            for origin in ('oracle_correct_policy','LLM_generated_separated','LLM_generated_mixed'):
                record=old_contracts.get((case['case_id'],model,origin.endswith('separated')),{})
                scope=case['policy'] if origin=='oracle_correct_policy' else record.get('proposed_policy')
                for mode in ('none','v3','v4','v5'):
                    run=run_case(case,mode,policy=scope or Policy(()).to_dict())
                    required={g['action_id'] for g in case['ground_truth'] if g['authorized'] and g['necessary']}
                    closed.append({'case_id':case['case_id'],'family_id':case['family_id'],'split':case['split'],
                        'model':model,'policy_origin':origin,'request_hash':None if origin=='oracle_correct_policy' else record.get('request_hash'),
                        'status':'valid' if scope is not None else 'unresolved_policy','mode':mode,
                        'required_calls':len(required),'incorrect_required_denials':sum(e['action_id'] in required and not e['executed'] for e in run['events']),
                        'required_actions_not_executed':sorted(required-{e['action_id'] for e in run['events'] if e['executed']}),
                        'run':run})
    dump_jsonl(out/'e3_closed_loop.jsonl',closed)
    for variant in FEATURES:
        results=[]
        for case in cases:
            for model in ('gpt-6-luna','gpt-4.1-mini'):
                for replicate in (0,1):
                    clean=plans.get((case['case_id'],model,'v5','json',replicate),{})
                    mixed=plans.get((case['case_id'],model,'v0','json',replicate),{})
                    result=run_pipeline(case,
                        classifications.get((case['case_id'],model,'v1',replicate)),
                        classifications.get((case['case_id'],model,'v0',replicate)),
                        platform_lease(case,clean.get('scope_policy')),platform_lease(case,mixed.get('scope_policy')),
                        variant=variant,q_plan=q_plans.get((case['case_id'],model)) or [],reference_actions=clean.get('reference_actions',[]))
                    result.update(model=model,replicate=replicate,p_request_hash=(clean if FEATURES[variant]['trust'] else mixed).get('request_hash'),
                                  q_plan_source='frozen_v1_tool_free_model_recommendation',
                                  p_declared_unknowns=(clean if FEATURES[variant]['trust'] else mixed).get('prediction',{}).get('unknowns',[]),
                                  runtime_kind='capability_vm',attack_opportunity=case['malicious'],
                                  p_reference_result=run_case(case,'none',actions=clean.get('reference_actions',[])))
                    apply_q_plan_status(result,q_plans.get((case['case_id'],model)))
                    result['p_reference_valid']=(result['p_reference_result']['goal_satisfied'] and not result['p_reference_result']['unauthorized_executed'])
                    results.append(result)
        dump_jsonl(out/('ablation_'+variant+'.jsonl'),results)
        print(json.dumps({'variant':variant,'runs':len(results),'unauthorized':sum(r['run']['unauthorized_executed'] for r in results),
                          'goal_satisfied':sum(r['run']['goal_satisfied'] for r in results)}),flush=True)
    # Same fixed actions isolate enforcement mechanisms from LLM filtering.
    mechanisms=[]
    for case in cases:
        for variant in FEATURES:
            r=run_pipeline(case,None,None,case['policy'],case['policy'],variant=variant,filter_actions=False)
            r['track']='fixed_actions_mechanistic';mechanisms.append(r)
    dump_jsonl(out/'fixed_actions_mechanistic.jsonl',mechanisms)


if __name__=='__main__':main()
