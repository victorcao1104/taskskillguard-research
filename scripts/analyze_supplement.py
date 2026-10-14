"""Descriptive real transfer agreement, replay Judge, and paired prompt study."""
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def read(relative):
    p=ROOT/relative
    return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()] if p.exists() else []


def divide(a,b):return a/b if b else None


def main():
    transfer=read('results/transfer/predictions.jsonl');judges=read('results/judge/predictions.jsonl');ablations=read('results/prompt_ablation/predictions.jsonl')
    groups=defaultdict(list)
    for row in transfer:groups[(row['model'],row['variant'],row['context'])].append(row)
    summary=[]
    for (model,variant,context),rows in sorted(groups.items()):
        counts={key:Counter(a[key] for row in rows if row['status']=='valid' for a in row['prediction']['actions']) for key in ('authorized','necessary')}
        summary.append({'model':model,'variant':variant,'context':context,'n_records':len(rows),'n_valid':sum(r['status']=='valid' for r in rows),'n_skills':len({r['skill_id'] for r in rows}), 'n_expected':30,'labels':{k:dict(v) for k,v in counts.items()},'human_ground_truth':False})
    index={(r['skill_id'],r['context'],r['variant'],r['model']):r for r in transfer}
    agreement=[]
    for context in ('low','high','edge'):
        for variant in ('v0','v1'):
            matches=Counter();counts=Counter();valid=0
            for sid in sorted({r['skill_id'] for r in transfer}):
                pair=[index.get((sid,context,variant,m)) for m in ('gpt-6-luna','gpt-4.1-mini')]
                if not all(r and r['status']=='valid' for r in pair):continue
                valid+=1;actions=[{a['action_id']:a for a in r['prediction']['actions']} for r in pair]
                for aid in actions[0].keys() & actions[1].keys():
                    for key in ('authorized','necessary'):
                        values=[p[aid][key] for p in actions];counts[key+'_all']+=1;matches[key+'_all']+=values[0]==values[1]
                        if 'unknown' not in values:
                            counts[key+'_decided']+=1;matches[key+'_decided']+=values[0]==values[1]
            agreement.append({'context':context,'variant':variant,'valid_skill_pairs':valid,'counts':dict(counts),'matching':dict(matches),'rates':{k:divide(matches[k],n) for k,n in counts.items()}})
    judge_summary=[]
    for model in ('gpt-6-luna','gpt-4.1-mini'):
        rows=[r for r in judges if r['model']==model];record={'model':model,'n_records':len(rows),'n_expected':36,'n_valid':sum(r['status']=='valid' for r in rows)}
        for key,truth in [('core_preserved','oracle_core'),('goal_satisfied','oracle_goal')]:
            decided=[r for r in rows if r['status']=='valid' and type(r['prediction'][key]) is bool]
            correct=sum(r['prediction'][key]==r[truth] for r in decided)
            record[key]={'decided':len(decided),'correct':correct,'accuracy_decided':divide(correct,len(decided)),'unknown_or_invalid':len(rows)-len(decided)}
        judge_summary.append(record)
    cases={c['case_id']:c for c in read('data/benchmark/synthetic_cases.jsonl')}
    prompt_groups=defaultdict(list)
    for row in ablations:prompt_groups[(row['model'],row['removed_sentence'])].append(row)
    prompt_summary=[];changed=[]
    for (model,sentence),rows in sorted(prompt_groups.items()):
        counts=Counter()
        for row in rows:
            if row['status']!='valid' or row['original_status']!='valid':counts['invalid_pairs']+=1;continue
            counts['valid_response_pairs']+=1
            predictions=[{a['action_id']:a for a in row[k]['actions']} for k in ('original_prediction','prediction')]
            for truth in cases[row['case_id']]['ground_truth']:
                for key in ('authorized','necessary'):
                    expected='yes' if truth[key] else 'no';full,ablated=[p[truth['action_id']][key] for p in predictions]
                    counts['label_pairs']+=1;counts['full_prompt_errors_or_unknown']+=full!=expected;counts['ablated_prompt_errors_or_unknown']+=ablated!=expected
                    if full!=ablated:changed.append({'case_id':row['case_id'],'model':model,'variant':row['variant'],'replicate':row['replicate'],'action_id':truth['action_id'],'label':key,'expected':expected,'full_prompt':full,'ablated_prompt':ablated,'request_hash':row['request_hash']})
        prompt_summary.append({'model':model,'removed_sentence':sentence,'n_records':len(rows),'counts':dict(counts),'post_hoc_development_only':True})
    result={'transfer':{'n_records':len(transfer),'n_expected':360,'groups':summary,'cross_model_agreement':agreement,'interpretation':'Hypothetical tasks; agreement is not accuracy or maliciousness prevalence.'},
            'judge':{'n_records':len(judges),'n_expected':72,'groups':judge_summary,'interpretation':'Judges inspect finite VM traces; no real dynamic execution.'},
            'prompt_ablation':{'n_records':len(ablations),'n_expected':48,'groups':prompt_summary,'changes':changed,'interpretation':'Post-hoc matched development probes; one sentence removed per targeted subset; no held-out tuning.'}}
    out=ROOT/'results/supplement_summary';out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    (out/'prompt_changes.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in changed),encoding='utf-8')
    print(json.dumps({'transfer':len(transfer),'judge':len(judges),'prompt_ablation':len(ablations)},ensure_ascii=False))


if __name__=='__main__':main()
