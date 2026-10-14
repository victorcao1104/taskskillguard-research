"""SkillScope-style action-in-task overprivilege; no vacuous skill-level F1."""
import json
import sys
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.evaluation import classification_metrics,augment_prediction


def overprivileged_label(authorized,necessary):
    if authorized=='no' or necessary=='no':return 'yes'
    if authorized=='yes' and necessary=='yes':return 'no'
    return 'unknown'


def read(path):return [json.loads(s) for s in (ROOT/path).read_text(encoding='utf-8').splitlines()]


def main():
    cases={r['case_id']:r for r in read('data/benchmark/synthetic_cases.jsonl')}
    replays=defaultdict(dict)
    for row in read('results/mechanistic/replays.jsonl'):replays[row['case_id']][row['action_id']]=row
    groups=defaultdict(list)
    for phase in ('development','validation','held_out'):
        for row in read(f'results/{phase}/detection.jsonl'):
            case=cases[row['case_id']]
            base=row.get('prediction',{'actions':[]})
            predictions={row['variant']:base}
            if row['variant']=='v1':
                predictions.update({v:augment_prediction(base,list(replays[case['case_id']].values()),v) for v in ('v2','v5')})
            for variant,prediction in predictions.items():
                lookup={a['action_id']:a for a in prediction['actions']}
                for truth in case['ground_truth']:
                    a=lookup.get(truth['action_id'],{})
                    groups[(row['model'],case['split'],variant)].append({'case_id':case['case_id'],'action_id':truth['action_id'],
                        'family_id':case['family_id'],'replicate':row['replicate'],'truth':'yes' if truth['overprivileged'] else 'no',
                        'predicted':overprivileged_label(a.get('authorized'),a.get('necessary'))})
    rows=[{'model':m,'split':s,'variant':v,**classification_metrics(rs,positive='yes',bootstrap_samples=1000)} for (m,s,v),rs in sorted(groups.items())]
    result={'formula':'privilege_relevant AND (NOT authorized OR unnecessary)','action_in_task':rows,
        'skill_level_f1':None,'reason':'All 12 synthetic skill identities have attack variants, so skill-level aggregation has no negative class and is not a useful benchmark. Real skills have no human ground truth.'}
    out=ROOT/'results/summary/combined_metrics.json';out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'combined_metric_rows':len(rows)}))


if __name__=='__main__':main()
