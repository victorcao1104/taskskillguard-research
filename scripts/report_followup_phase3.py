"""Offline, separately labeled consolidation of preselected acquisition retries."""
import copy
import csv
import hashlib
import json
import re
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


def candidate_diagnostics(prepared, observations):
    counts = Counter(); fences = []; fence_keys = set()
    for row in prepared:
        for node in row['graph']['nodes']:
            if node['id'] not in row['action_ids']:
                continue
            counts['selected_candidates'] += 1
            counts['resource_status_'+str(node.get('resource_status'))] += 1
            if re.fullmatch(r'\s*(```+|~~~+)\s*[\w+-]*\s*', node.get('summary','')):
                fences.append({'skill_id':row['skill_id'], 'action_id':node['id'],
                               'summary':node['summary'],'operation':node['operation'],
                               'provenance':node['provenance']})
                fence_keys.add((row['skill_id'],node['id']))
    groups = defaultdict(Counter)
    for row in observations:
        if row['status'] != 'valid':
            continue
        for action in (row.get('prediction') or {}).get('actions',[]):
            group = 'standalone_fence' if (row['skill_id'],action['action_id']) in fence_keys else 'other_candidate'
            groups[group]['action_observations'] += 1
            for attribute in ('authorized','necessary'):
                groups[group][attribute+'_'+action[attribute]] += 1
    return {'analysis_status':'exploratory_posthoc_syntactic_diagnostic',
            'counts':dict(counts),'standalone_fence_candidates':len(fences),
            'affected_skills':len({r['skill_id'] for r in fences}),
            'fence_rule':r'fullmatch: \s*(```+|~~~+)\s*[\w+-]*\s*',
            'standalone_fence_evidence':fences,
            'model_label_counts':{k:dict(v) for k,v in groups.items()},
            'interpretation':'Syntactic counts expose candidate noise, not human-validated precision or causal attribution of unknown. Frozen candidates and all denominators remain unchanged.'}


def markdown_report(summary):
    def table(headers, values):
        return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |']+
                         ['| '+' | '.join(map(str,row))+' |' for row in values])
    labels={'primary':'冻结主结果','phase_replay':'同一响应阶段重放','consolidated_followup':'阶段重放＋预选补跑'}
    overview=[]
    for stage,s in summary['stages'].items():
        overview.append([labels[stage],s['conditions'],s['not_applicable_conditions'],
                         f"{s['protocol_valid_conditions']}/{s['model_evaluated_conditions']}",
                         s['classified_action_observations'],s['authorized_counts'].get('unknown',0),
                         s['necessary_counts'].get('unknown',0)])
    current=summary['stages']['consolidated_followup']; follow=summary['followup']
    groups=[[g['model'],g['context'],g['variant'],
             f"{g['protocol_valid_conditions']}/{g['model_evaluated_conditions']}",g['classified_action_observations'],
             g['authorized_counts'].get('unknown',0),g['necessary_counts'].get('unknown',0)] for g in current['groups']]
    diag=summary['candidate_diagnostics']
    return '\n\n'.join(['# 真实样本补跑与前后对照',
        '原始冻结结果与首次失败全部保留；第三行是同一条件集合的证据汇总，不是新的独立测试集。预选的每条补跑均按规则使用，包括任何仍然失败的结果。',
        table(['观察层次','计划条件','不适用','协议有效/适用','动作观察','授权unknown','必要性unknown'],overview),
        f"补跑完成 {follow['completed_trials']}/{follow['planned_trials']} 条；状态计数为 {json.dumps(follow['status_counts'],ensure_ascii=False)}。新增费用估计 ${follow['followup_cost_usd']:.6f}，累计保守费用上界 ${follow['cumulative_cost_usd']:.6f}，余量 ${follow['remaining_budget_usd']:.6f}。费用含保留的历史未知账单预留，不是供应商账单。",
        '## 汇总后的分组覆盖',
        table(['模型','语境','表示','协议有效/适用','动作观察','授权unknown','必要性unknown'],groups),
        '同一候选会在不同语境、模型与表示下重复，因此动作观察数不是唯一动作数。协议有效不等于语义正确；人工准确率仍为空。',
        '## 提取器剩余问题',
        f"共 {diag['counts']['selected_candidates']} 个选中候选，其中 {diag['standalone_fence_candidates']} 个仅为代码围栏，涉及 {diag['affected_skills']} 个 Skill；资源状态 unknown 的候选为 {diag['counts'].get('resource_status_unknown',0)} 个。这是事后句法诊断，逐节点来源保存在 summary.json；未更改冻结候选与分母。",
        '## 配对分歧',
        '机器汇总中的 paired_agreement 按模型/表示、语境与 authorized/necessary 给出完整三值标签配对表。仅统计双方协议有效、动作 ID 相同的配对；一致和分歧都不表示谁正确。真人标注仍由用户安排。'])+'\n'


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
               'candidate_diagnostics':candidate_diagnostics(data['prepared'],merged),
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
    (ROOT/'docs/phase3_followup_results.md').write_text(markdown_report(summary),encoding='utf-8')
    print(json.dumps({'stages':{k:{f:v[f] for f in ('conditions','protocol_valid_conditions','classified_action_observations','authorized_counts','necessary_counts')} for k,v in summary['stages'].items()},'cumulative_cost_usd':summary['followup']['cumulative_cost_usd']},ensure_ascii=False))


if __name__=='__main__':
    main()
