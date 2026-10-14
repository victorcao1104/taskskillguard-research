"""Compare final robustness fixes against saved frozen-study executions."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.sandbox import run_case


def read(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
def normalized(value):
    if isinstance(value,dict):return {k:normalized(v) for k,v in value.items() if k not in {'state_id','elapsed_seconds'}}
    if isinstance(value,list):return [normalized(v) for v in value]
    return value


def main():
    cases={r['case_id']:r for r in read(ROOT/'data/benchmark/synthetic_cases.jsonl')}
    failures=[];mechanistic=0;plans=0
    for old in read(ROOT/'results/mechanistic/traces.jsonl'):
        new=run_case(cases[old['case_id']],old['mode'],options=old['settings'])
        if 'ablation' in old:new['ablation']=old['ablation']
        if normalized(old)!=normalized(new):failures.append({'kind':'mechanistic','case_id':old['case_id'],'mode':old['mode'],'ablation':old.get('ablation')})
        mechanistic+=1
    for phase in ('development','validation','held_out'):
        for result in read(ROOT/f'results/{phase}/plans.jsonl'):
            if result['status']!='valid':continue
            case=cases[result['case_id']];catalog={a['id']:a for a in case['actions']}
            for old in result['runs']:
                new=run_case(case,old['mode'],actions=[catalog[i] for i in result['action_ids']])
                if normalized(old)!=normalized(new):failures.append({'kind':'model_plan','request_hash':result['request_hash'],'mode':old['mode']})
                plans+=1
    report={'mechanistic_runs_compared':mechanistic,'model_plan_runs_compared':plans,'normalization':'Only state UUID and elapsed runtime removed. Full event/output/settings/reference data compared.','differences':failures}
    out=ROOT/'results/verification';out.mkdir(parents=True,exist_ok=True)
    (out/'runtime_stability.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report));return bool(failures)


if __name__=='__main__':raise SystemExit(main())
