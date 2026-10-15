"""Create-only, offline publication supplement; never replaces primary evidence."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from prepare_phase4 import immutable, json_bytes, sha
from run_phase5 import CAP, read_rows
from tsg.budget_v4 import BudgetV4


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def usage_sum(records):
    records = list(records)
    return {k: sum((r.get('usage') or {}).get(k, 0) for r in records)
            for k in ('input_tokens', 'output_tokens', 'total_tokens')}


def audit_requests(observations, raw_by_hash):
    groups = defaultdict(list)
    for obs in observations:
        groups[obs['request_hash']].append(obs)
    if set(groups) != set(raw_by_hash):
        raise ValueError('RAW_SET_MISMATCH')
    for h, group in groups.items():
        if any(o['parsed'] != group[0]['parsed'] for o in group):
            raise ValueError('SHARED_RAW_PARSE_MISMATCH:' + h)
    return {
        'planned_observed_conditions': len(observations),
        'unique_requests': len(groups),
        'reused_condition_count': len(observations) - len(groups),
        'unique_protocol_valid': sum(g[0]['parsed']['protocol_valid'] for g in groups.values()),
        'condition_protocol_valid': sum(o['parsed']['protocol_valid'] for o in observations),
        'unique_raw_status': dict(Counter(r['status'] for r in raw_by_hash.values())),
        'provider_reported_unique_request_usage': usage_sum(raw_by_hash.values()),
        'condition_attributed_usage_not_actual_billing': usage_sum(
            raw_by_hash[o['request_hash']] for o in observations),
        'shared_requests': [{'request_hash': h, 'job_ids': [o['job_id'] for o in g],
                             'case_ids': sorted({o['case_id'] for o in g})}
                            for h, g in sorted(groups.items()) if len(g) > 1],
        'interpretation': 'Same payload plus replicate shares one cached raw response. '
                          'Conditions remain in pipeline comparisons, but are not independent API draws. '
                          'Unique provider usage is observed usage, not an invoice; failed usage may be absent.'}


def decompose_pairs(rows):
    index = {(r['model'], r['axis'], r['view'], r['case_id'], r['context'], r['candidate_id']): r
             for r in rows}
    output = []
    for model in sorted({r['model'] for r in rows}):
        for axis in sorted({r['axis'] for r in rows}):
            for left in ('auto', 'oracle', 'shuffled', 'length_control'):
                base = [r for r in rows if r['model'] == model and r['axis'] == axis
                        and r['view'] == 'table' and r['eligible']]
                strata = defaultdict(lambda: {'pairs': 0, 'left_correct': 0, 'right_correct': 0})
                for b in base:
                    a = index[(model, axis, left, b['case_id'], b['context'], b['candidate_id'])]
                    if a['gold'] != b['gold'] or not a['eligible']:
                        raise ValueError('UNPAIRED_TRUTH')
                    av, bv = a['protocol_status'] == 'valid', b['protocol_status'] == 'valid'
                    key = ('both_valid' if av and bv else 'left_only_valid' if av else
                           'right_only_valid' if bv else 'neither_valid')
                    s = strata[key]; s['pairs'] += 1
                    s['left_correct'] += int(av and a['prediction'] == a['gold'])
                    s['right_correct'] += int(bv and b['prediction'] == b['gold'])
                for s in strata.values():
                    s['net_correct'] = s['left_correct'] - s['right_correct']
                net = sum(s['net_correct'] for s in strata.values())
                output.append({'model': model, 'axis': axis, 'left': left, 'right': 'table',
                               'planned_pairs': len(base), 'net_correct': net,
                               'difference_planned': net / len(base), 'strata': dict(strata),
                               'status': 'posthoc_diagnostic_not_primary_estimand',
                               'caution': 'Both-valid subset is selected by outcome; it is not a causal '
                                          'edge-quality estimate or a replacement for planned-denominator scoring.'})
    return output


def build(out):
    audits = {}
    for name, rel in [('main', 'results/phase5'), ('q017_followup', 'results/phase5_q017')]:
        obs = read_rows(ROOT / rel / 'api/observations.jsonl')
        raws = {o['request_hash']: read(ROOT / o['raw_ref']) for o in obs}
        audits[name] = audit_requests(obs, raws)
    old = BudgetV4(ROOT / 'results/phase4/api/budget.jsonl', CAP)
    now = BudgetV4(ROOT / 'results/phase5/api/budget.jsonl', CAP)
    new_ids = set(now.entries) - set(old.entries)
    if len(new_ids) != sum(a['unique_requests'] for a in audits.values()):
        raise ValueError('UNIQUE_REQUEST_RESERVATION_COUNT_MISMATCH')
    budget = {'inherited_upper_usd': old.total_cost, 'current_upper_usd': now.total_cost,
              'phase5_incremental_upper_usd': now.total_cost - old.total_cost,
              'cumulative_cap_usd': CAP, 'remaining_usd': CAP - now.total_cost,
              'new_unique_reservations': len(new_ids),
              'new_reservation_status': dict(Counter(now.entries[i]['status'] for i in new_ids)),
              'is_provider_invoice': False,
              'basis': 'Preserved inherited ledger plus unique request reservations; unknown usage '
                       'retains reservation; no cache-hit discount credited.'}
    rows = read_rows(ROOT / 'results/phase5/analysis/label_scores.jsonl')
    decomposition = decompose_pairs(rows)
    extraction = read(ROOT / 'results/phase5/extraction_primary/summary.json')
    reasoning = read(ROOT / 'results/phase5/analysis/summary.json')
    recovery = read(ROOT / 'results/phase5/recovery_primary/summary.json')
    comparison = {
        'paired_extraction': extraction['groups'],
        'real_180': {'all_candidates_v4': 250, 'all_candidates_v5': 252,
                    'selected_v4': 217, 'selected_v5': 219,
                    'zero_selected_v4': 128, 'zero_selected_v5': 128,
                    'human_validated_accuracy': None,
                    'active_human_items_per_rater': 832, 'uncollected_files': 2447},
        'reasoning_within_phase5': reasoning['synthetic']['by_model_view_axis'],
        'protocol': reasoning['main_protocol'],
        'recovery_within_phase5': recovery,
        'cross_phase_reasoning': 'Historical context only: new families, denial variants and necessity '
                                 'estimands prevent causal before/after accuracy subtraction.',
        'unknown_semantics': 'Missing/invalid response, extraction omission, correct epistemic unknown, '
                             'avoidable unknown and unsupported yes/no are distinct outcomes.',
        'uncompleted_by_design': ['Independent human source annotation and adjudication',
                                 'Real-corpus accuracy estimates requiring those annotations']}
    out.mkdir(parents=True, exist_ok=True)
    for name, value in [('request_cache_audit.json', audits), ('budget_summary.json', budget),
                        ('protocol_pair_decomposition.json', decomposition), ('comparison.json', comparison)]:
        immutable(out / name, json_bytes(value))
    source_paths = ['scripts/publish_phase5.py', 'results/phase5/analysis/summary.json',
                    'results/phase5/analysis/label_scores.jsonl', 'results/phase5/api/observations.jsonl',
                    'results/phase5_q017/api/observations.jsonl', 'results/phase5/api/budget.jsonl',
                    'results/phase5/extraction_primary/summary.json',
                    'results/phase5/recovery_primary/summary.json']
    immutable(out / 'provenance.json', json_bytes({'source_sha256': {
        p: sha((ROOT / p).read_bytes()) for p in source_paths},
        'registration': 'Retrospective publication audit; original prospective results unchanged.'}))
    return comparison, budget


def plot(out, comparison):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), layout='constrained')
    colors = ['#8294a6', '#247a9c']
    ax = axes[0, 0]
    data = [r for r in comparison['paired_extraction'] if r['generation'] == 'phase5']
    x = np.arange(3)
    for offset, version, color in [(-.18, 'v4', colors[0]), (.18, 'v5', colors[1])]:
        vals = [next(r for r in data if r['extractor'] == version and r['split'] == s)
                for s in ('all', 'validation', 'heldout')]
        bars = ax.bar(x + offset, [100*r['recall'] for r in vals], .36, label=version, color=color)
        ax.bar_label(bars, labels=[f"{r['matched']}/{r['expected']}" for r in vals], padding=3, fontsize=9)
    ax.set(xticks=x, xticklabels=['All new', 'Validation', 'Held-out'], ylim=(0, 110),
           ylabel='Effect recall (%)', title='A. Same new fixtures, old vs new extractor')
    ax.legend(frameon=False)
    ax = axes[0, 1]
    bars = ax.bar(['Original', 'Guard', 'Guard + recovery'], [3/48*100, 0, 40/48*100],
                  color=[colors[0], '#bb7047', colors[1]])
    ax.bar_label(bars, labels=['3/48', '0/48', '40/48'], padding=3)
    ax.set(ylim=(0, 105), ylabel='Authorized core-goal success (%)',
           title='B. Matched finite fault tasks')
    ax = axes[1, 0]
    views = ['table', 'auto', 'oracle', 'shuffled', 'length_control']
    rs = comparison['reasoning_within_phase5']
    for model, marker, color in [('gpt-4.1-mini', 'o', '#bb7047'), ('gpt-6-luna', 's', colors[1])]:
        vals = [next(r for r in rs if r['model']==model and r['view']==v and r['axis']=='task_necessary')
                for v in views]
        ax.plot(range(5), [r['exact_accuracy']*100 for r in vals], marker=marker, label=model, color=color)
    ax.set(xticks=range(5), xticklabels=['Table', 'Auto', 'Oracle', 'Shuffled', 'Padding'], ylim=(65, 100),
           ylabel='Task-necessity accuracy (%)', title='C. No stable graph benefit across models')
    ax.legend(frameon=False, fontsize=8)
    ax = axes[1, 1]
    bars = ax.bar(['v4 selected', 'v5 selected', 'Zero-candidate skills'], [217, 219, 128],
                  color=[colors[0], colors[1], '#bb7047'])
    ax.bar_label(bars, padding=3)
    ax.set(ylim=(0, 260), ylabel='Count (different units labelled)',
           title='D. Limited change on 180 real skills')
    fig.suptitle('TaskSkillGuard Phase 5 | finite, source-grounded evaluation', fontsize=15)
    fig.text(.5, -.025, 'A: effect-level recall; B: finite gateway, no arbitrary-program guarantee. '
             'C: planned denominator includes invalid outputs; 18 families, exploratory. '
             'D: candidate counts are not human-validated accuracy.', ha='center', fontsize=8, wrap=True)
    fig.savefig(out / 'overview.png', dpi=160, bbox_inches='tight')
    fig.savefig(out / 'overview.pdf', bbox_inches='tight', metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)


if __name__ == '__main__':
    out = ROOT / 'results/phase5/publication_v2'
    comparison, budget = build(out)
    if not (out / 'overview.png').exists():
        plot(out, comparison)
    print(json.dumps(budget), flush=True)
