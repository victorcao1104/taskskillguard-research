"""Generate descriptive publication tables from saved observations, never API calls."""
import csv
from collections import Counter, defaultdict
import json
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tsg.budget_v4 import BudgetV4


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in (ROOT / path).read_text(encoding='utf-8').splitlines() if line]


def write_csv(path, data):
    data = list(data)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]) if data else [])
        writer.writeheader()
        writer.writerows(data)


def annotation_packet(handoff, rater):
    # Source-first review: do not expose extractor status, sensitivity, operation,
    # resource, summary, role, or any model decision as an apparent answer key.
    return [{'skill_id': row['skill_id'],
        'candidate': {'id': row['action']['id'], 'provenance': row['action']['provenance']},
        'source_sha256': row['source_sha256'], 'source_ref': 'data/phase4/human_review/sources.jsonl',
        'rater_id': rater, 'labels': {}, 'notes': '', 'status': 'pending_human_review'} for row in handoff]


def write_blank_packet(path, packet):
    if path.exists():
        old = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
        if any(row.get('labels') != {} or row.get('notes') != '' or
               row.get('status') != 'pending_human_review' for row in old):
            raise ValueError('REFUSE_TO_OVERWRITE_HUMAN_ANNOTATION')
        key = lambda row: (row['skill_id'], row['candidate']['id'], row['rater_id'])
        if [key(row) for row in old] != [key(row) for row in packet]:
            raise ValueError('REFUSE_TO_REPLACE_ANNOTATION_POPULATION')
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in packet), encoding='utf-8')


def main():
    out = ROOT / 'results/phase4/publication'
    out.mkdir(parents=True, exist_ok=True)
    summary = read('results/phase4/analysis/summary.json')
    extraction = []
    for version in ('extraction_rescored', 'extraction_revised'):
        for row in read(f'results/phase4/{version}/summary.json')['groups']:
            if row['split'] == 'all' and not (version == 'extraction_revised' and row['extractor'] == 'v2'):
                extraction.append({'observation': version, **row})
    write_csv(out / 'extraction_comparison.csv', extraction)
    keys = ('model', 'view', 'axis', 'correct', 'planned_eligible', 'exact_accuracy',
            'known_truth_accuracy', 'decided_coverage', 'selective_accuracy', 'predicted_unknown',
            'missing_or_invalid_predictions')
    write_csv(out / 'synthetic_metrics.csv', ({k: row[k] for k in keys}
              for row in summary['synthetic']['by_model_view_axis']))
    paired = []
    for row in summary['synthetic']['paired_graph_minus_table']:
        if row['split'] in ('all', 'heldout'):
            paired.append({k: row[k] for k in ('model', 'split', 'axis', 'metric',
                'difference_graph_minus_table', 'ci95_percentile', 'families', 'planned_paired_labels')})
    write_csv(out / 'paired_family_intervals.csv', paired)
    real_groups = defaultdict(Counter)
    for row in summary['real']['by_group']:
        real_groups[(row['model'], row['context'], row['axis'])].update(row['counts'])
    write_csv(out / 'real_labels_descriptive.csv', ({'model': key[0], 'context': key[1], 'axis': key[2],
        'planned_labels': sum(counts.values()), **{label: counts[label] for label in
        ('yes', 'no', 'unknown', 'missing_or_invalid')}} for key, counts in sorted(real_groups.items())))
    keys = ('arm', 'contract', 'ceiling', 'lease_state', 'planned_runs', 'goal', 'authorized_goal',
            'unauthorized_effect_run', 'zero_execution', 'denied_effects', 'executed_effects')
    write_csv(out / 'enforcement_conditions.csv', ({k: row[k] for k in keys}
        for row in summary['replay']['by_contract_ceiling_lease'] if row['arm'] == 'enforcement'))

    usage = defaultdict(Counter)
    for row in rows('results/phase4/api/observations.jsonl'):
        key = (row['track'], row['model'], row['view'])
        usage[key]['planned_jobs'] += 1
        usage[key]['usage_observed_jobs'] += row['usage'] is not None
        for name in ('input_tokens', 'output_tokens', 'total_tokens'):
            usage[key][name] += (row['usage'] or {}).get(name, 0)
    write_csv(out / 'primary_token_usage.csv', ({'track': k[0], 'model': k[1], 'view': k[2],
        **{name: counts[name] for name in ('planned_jobs', 'usage_observed_jobs',
        'input_tokens', 'output_tokens', 'total_tokens')}} for k, counts in sorted(usage.items())))
    revision = read('results/phase4/provenance/budget_revision.json')
    budget = BudgetV4(ROOT / 'results/phase4/api/budget.jsonl', revision['cumulative_cap_usd'])
    settled = sum(r['cost_usd'] for r in budget.entries.values() if r['status'] == 'settled')
    reserved = sum(r['reserved_usd'] for r in budget.entries.values() if r['status'] != 'settled')
    cost = {'historical_original_estimate_usd': revision['original_exposure_usd'],
        'historical_corrected_upper_usd': revision['corrected_exposure_upper_usd'],
        'new_exposure_upper_usd': budget.total_cost - revision['corrected_exposure_upper_usd'],
        'cumulative_upper_usd': budget.total_cost, 'cumulative_cap_usd': budget.limit,
        'remaining_usd': budget.limit - budget.total_cost, 'settled_usage_upper_usd': settled,
        'unknown_reserved_usd': reserved, 'invoice': False}
    (out / 'budget_summary.json').write_text(json.dumps(cost, indent=2) + '\n', encoding='utf-8')

    # Separate blank packets: no predictions, other rater decisions, or adjudications.
    handoff = rows('data/phase4/annotation_handoff.jsonl')
    annotation = ROOT / 'data/phase4/human_review'
    annotation.mkdir(parents=True, exist_ok=True)
    sources = [{'skill_id': row['skill_id'], 'files': row['files'],
        'source_sha256': {file: hashlib.sha256(text.encode('utf-8')).hexdigest()
                          for file, text in row['files'].items()}}
        for row in rows('data/phase4/real_prepared.jsonl')]
    (annotation / 'sources.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
        for row in sources), encoding='utf-8')
    for rater in ('A', 'B'):
        write_blank_packet(annotation / f'rater_{rater}.jsonl', annotation_packet(handoff, rater))

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), layout='constrained')
    labels = ['Legacy v2', 'v4 first\nrescored', 'v4 revised\nposthoc']
    x = list(range(3))
    axes[0].bar([i-.18 for i in x], [r['precision']*100 for r in extraction], .36,
                label='Precision', color='#356C9B')
    axes[0].bar([i+.18 for i in x], [r['recall']*100 for r in extraction], .36,
                label='Recall, all expected effects', color='#C17C35')
    axes[0].set(xticks=x, xticklabels=labels, ylim=(0, 110), ylabel='Percent',
                title='Extraction: 50 fixed fixtures / 25 families')
    axes[0].legend(fontsize=8, loc='upper left', bbox_to_anchor=(0, -.14))
    conditions = [('correct', False), ('overbroad', False), ('overbroad', True), ('underbroad', True)]
    selected = [next(r for r in summary['replay']['by_contract_ceiling_lease'] if
        r['arm']=='enforcement' and r['contract']==contract and r['ceiling']==ceiling and
        r['lease_state']=='full') for contract, ceiling in conditions]
    axes[1].bar([i-.18 for i in range(4)], [r['authorized_goal'] for r in selected], .36,
                label='Authorized goal completion', color='#356C9B')
    axes[1].bar([i+.18 for i in range(4)], [r['unauthorized_effect_run'] for r in selected], .36,
                label='Runs with unauthorized effects', color='#B64949')
    axes[1].set(xticks=list(range(4)), xticklabels=['Correct\nceiling off', 'Overbroad\nceiling off',
        'Overbroad\nceiling on', 'Underbroad\nceiling on'], ylim=(0, 8.8), yticks=list(range(9)),
        ylabel='Runs out of 8 planned', title='Finite runtime: full lease only')
    axes[1].legend(fontsize=8, loc='upper left', bbox_to_anchor=(0, -.14))
    for ax in axes:
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_axisbelow(True)
        ax.grid(axis='y', alpha=.2)
    fig.savefig(out / 'evidence_summary.png', dpi=180)
    fig.savefig(out / 'evidence_summary.pdf')
    plt.close(fig)
    print(json.dumps({'budget': cost, 'human_rows_per_packet': len(handoff)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
