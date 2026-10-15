"""Offline, separately labeled consolidation of preselected acquisition retries."""
import copy
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tsg.analysis_v3 import summarize_real


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def consolidate(primary, phase, trials, follow):
    original = {r['job_id']: r for r in primary}
    replayed = {r['job_id']: r for r in phase}
    expected = {r['trial_id']: r['original_job_id'] for r in trials}
    observed = {r['trial_id']: r for r in follow}
    if len(original) != len(primary) or len(replayed) != len(phase) or set(original) != set(replayed):
        raise ValueError('PRIMARY_PHASE_GRID_MISMATCH')
    if (len(expected) != len(trials) or len(observed) != len(follow) or set(expected) != set(observed)
            or len(set(expected.values())) != len(expected)
            or not set(expected.values()) <= set(original)
            or any(observed[t]['original_job_id'] != job for t,job in expected.items())):
        raise ValueError('FOLLOWUP_GRID_MISMATCH')
    replacements = {r['original_job_id']: r for r in follow}
    result = []
    for job, old in original.items():
        row = copy.deepcopy(replacements.get(job, replayed[job]))
        row['evidence_job_id'] = row['job_id']
        row['job_id'] = job
        row['primary_status'] = old['status']
        row['evidence_source'] = 'followup_new_sample' if job in replacements else 'primary_phase_reparse'
        # All preselected trials replace their missing primary observation, even if still invalid.
        result.append(row)
    return result


def agreements(rows):
    observations = {}
    for r in rows:
        if r['status'] != 'valid':
            continue
        for action in (r.get('prediction') or {}).get('actions', []):
            key = (r['skill_id'], r['context'], r['model'], r['variant'], action['action_id'])
            if key in observations:
                raise ValueError('DUPLICATE_ACTION_OBSERVATION')
            observations[key] = action
    comparisons = defaultdict(Counter)
    for (skill, context, model, variant, aid), left in observations.items():
        pairs = []
        if variant == 'raw':
            pairs.append(('representation', model, 'raw', 'graph_v2', (skill,context,model,'graph_v2',aid)))
        if model == 'gpt-4.1-mini':
            pairs.append(('model', variant, 'gpt-4.1-mini', 'gpt-6-luna', (skill,context,'gpt-6-luna',variant,aid)))
        for comparison, fixed, a, b, key in pairs:
            if key not in observations:
                continue
            for attribute in ('authorized','necessary'):
                group = (comparison, fixed, context, a, b, attribute)
                comparisons[group][left[attribute]+'|'+observations[key][attribute]] += 1
    return [{'comparison':key[0], 'fixed_condition':key[1], 'context':key[2],
             'left':key[3], 'right':key[4], 'attribute':key[5],
             'paired_action_observations':sum(counts.values()),
             'agreements':sum(n for pair,n in counts.items() if pair.split('|')[0]==pair.split('|')[1]),
             'disagreements':sum(n for pair,n in counts.items() if pair.split('|')[0]!=pair.split('|')[1]),
             'label_pairs':dict(sorted(counts.items())), 'human_accuracy':None,
             'interpretation':'Agreement on jointly protocol-valid actions; neither correctness nor independent sample count.'}
            for key,counts in sorted(comparisons.items())]


def main():
    paths = {'primary':'results/phase3/api/real.jsonl',
             'phase':'results/phase3/phase_protocol/diagnostics/real.jsonl',
             'trials':'results/phase3_followup/pending_trials.jsonl',
             'follow':'results/phase3_followup/api/real.jsonl',
             'prepared':'data/phase3/real_prepared.jsonl'}
    data = {key:read_rows(ROOT/path) for key,path in paths.items()}
    merged = consolidate(data['primary'],data['phase'],data['trials'],data['follow'])
    summary = {'analysis_kind':'posthoc_phase_correction_plus_preselected_external_failure_followup',
               'primary_results_replaced':False, 'independent_prospective_evaluation':False,
               'replacement_rule':'Every preselected trial is used regardless of its outcome; all other phase-reparsed primary observations remain.',
               'stages':{name:summarize_real(rows,data['prepared']) for name,rows in
                         [('primary',data['primary']),('phase_replay',data['phase']),('consolidated_followup',merged)]},
               'followup':json.loads((ROOT/'results/phase3_followup/summary.json').read_text(encoding='utf-8')),
               'paired_agreement':agreements(merged),
               'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths.values()},
               'human_accuracy':None,'human_annotation_status':'pending'}
    out = ROOT/'results/phase3_followup/analysis'
    if out.exists():
        raise ValueError('ANALYSIS_OUTPUT_ALREADY_EXISTS')
    out.mkdir()
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'consolidated_real.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in merged),encoding='utf-8')
    table=[]
    for stage,metrics in summary['stages'].items():
        for group in metrics['groups']:
            table.append({'stage':stage, **{k:group[k] for k in ('model','context','variant','conditions',
                'model_evaluated_conditions','not_applicable_conditions','protocol_valid_conditions','classified_action_observations')},
                **{attribute+'_'+label:group[attribute+'_counts'].get(label,0)
                   for attribute in ('authorized','necessary') for label in ('yes','no','unknown')}})
    with (out/'real_before_after.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(table[0])); writer.writeheader(); writer.writerows(table)
    print(json.dumps({'stages':{k:{f:v[f] for f in ('conditions','protocol_valid_conditions','classified_action_observations','authorized_counts','necessary_counts')} for k,v in summary['stages'].items()},'cumulative_cost_usd':summary['followup']['cumulative_cost_usd']},ensure_ascii=False))


if __name__=='__main__':
    main()
