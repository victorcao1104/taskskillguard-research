"""Hand-derived offline analysis controls; never inspect held-out fixtures."""
import importlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
AXES = ('authorization', 'current_route_required', 'catalog_required')


def analysis():
    assert (ROOT / 'scripts/analyze_phase9.py').exists(), 'Phase 9 analysis is not implemented'
    return importlib.import_module('analyze_phase9')


def truth(cid='c', family='f'):
    return {'case_id': cid, 'family': family, 'split': 'heldout',
            'labels': [{'id': 'x', 'authorization': 'unknown',
                        'current_route_required': 'no', 'catalog_required': 'not_applicable'}],
            'worlds': []}


def obs(view='A00', correct=True, valid=True, rep=0):
    labels = {a: truth()['labels'][0][a] for a in AXES}
    direct = labels if correct else dict.fromkeys(AXES, 'yes')
    return {'case_id': 'c', 'family': 'f', 'split': 'heldout', 'model': 'm',
            'view': view, 'replicate': rep, 'track': 'factorial', 'job_id': view + str(rep),
            'parsed': {'protocol_valid': valid, 'by_id': {'x': direct},
                       'reduced_by_id': {'x': labels}, 'diagnostic_codes': []}, 'raw_status': 'completed'}


def runtime(cid, family, policy='calls', completed=True, calls=1, cache=True, fault='none'):
    return {'condition_id': cid + policy + str(cache) + fault, 'case_id': cid, 'family': family,
            'split': 'heldout', 'world_index': 0, 'quota': 16, 'pipeline': 'trusted',
            'fault': fault, 'policy': policy, 'cache': cache, 'planning_budget': 512,
            'gate_mode': 'conditional', 'preflight': True, 'observation_budget': 2,
            'runner_status': 'completed', 'result': {'authorized_goal': completed,
                'charged_calls': calls, 'planning_units': 5, 'audit_interpreter_calls': 1,
                'audit_steps': 2, 'planner_steps': 3, 'primitive_simulations': 2,
                'unauthorized_effects': 0, 'duplicate_effects': 0,
                'failure_reason': None if completed else 'no_feasible_route'}}


def test_family_bootstrap_does_not_weight_large_families_or_depend_on_row_order():
    a = analysis()
    rows = [{'family': 'small', 'difference': -1}] + [{'family': 'large', 'difference': 1}] * 9
    got = a.paired_interval(rows, 10000, 9009)
    assert got['estimate'] == 0 and got['pairs'] == 10 and got['families'] == 2
    assert got == a.paired_interval(list(reversed(rows)), 10000, 9009)
    assert got['interval95'] == [-1, 1]


def test_invalid_missing_records_remain_in_denominator_and_reducers_are_dependent():
    a = analysis()
    normalized = a.normalize_observations([truth()], [obs(correct=False), obs('A01', valid=False)], ('m',))
    assert len(normalized) == 6 and sum(r.get('missing_response', False) for r in normalized) == 4
    candidates, cases, metrics = a.factorial_scores([truth()], normalized)
    direct = next(r for r in metrics if r['view'] == 'A00' and r['reducer'] == 0 and r['axis'] == AXES[0])
    reduced = next(r for r in metrics if r['view'] == 'A00' and r['reducer'] == 1 and r['axis'] == AXES[0])
    invalid = next(r for r in metrics if r['view'] == 'A01' and r['reducer'] == 1 and r['axis'] == AXES[0])
    assert direct['correct'] == 0 and reduced['correct'] == 1
    assert invalid['total'] == 1 and invalid['invalid'] == 1 and invalid['accuracy'] == 0
    assert invalid['valid_label_denominator'] == 0 and invalid['validity_conditional_accuracy'] is None
    assert len(cases) == 8 and len(candidates) == 8


def test_factorial_interaction_is_difference_of_differences():
    a = analysis()
    rows = []
    for d in (0, 1):
        for t in (0, 1):
            for r in (0, 1):
                rows.append({'case_id': 'c', 'family': 'f', 'split': 'heldout', 'model': 'm',
                    'dedup': d, 'tool': t, 'reducer': r, 'total': 1,
                    'correct': dict.fromkeys(AXES, d * t)})
    summary, details = a.factorial_contrasts(rows, 100, 9009)
    values = {r['contrast']: r['estimate'] for r in summary if r['axis'] == AXES[0]}
    assert values['dedup'] == .5 and values['tool'] == .5 and values['reducer'] == 0
    assert values['dedup:tool'] == 1 and values['dedup:tool:reducer'] == 0
    assert len(details) == 21


def test_unknown_budget_abstention_is_not_proven_intrinsic_unknown():
    a = analysis()
    labels = {a: truth()['labels'][0][a] for a in AXES}
    decisions = {AXES[0]: {'proven': True, 'reason': 'intrinsic'},
                 AXES[1]: {'proven': False, 'reason': 'budget'},
                 AXES[2]: {'proven': True, 'reason': 'observed'}}
    rows = [{'case_id': 'c', 'family': 'f', 'split': 'heldout', 'pipeline': 'heuristic',
             'replicate': 0, 'budget': 2, 'protocol_valid': True,
             'result': {'by_id': {'x': labels}, 'decisions': {'x': decisions},
                        'executions': 2, 'interpreter_steps': 4, 'first_fully_resolved_at': None}}]
    scored, metrics = a.query_scores([truth()], rows)
    assert scored[0]['proven'] == 2 and scored[0]['total'] == 3
    assert scored[0]['intrinsic_unknown'] == 1 and scored[0]['budget_unknown'] == 1
    assert metrics[0]['proven_fraction'] == 2 / 3 and metrics[0]['incorrect_proven'] == 0
    rows[0]['result']['by_id']['x'][AXES[0]] = 'yes'
    with pytest.raises(ValueError, match='UNSOUND_QUERY'):
        a.query_scores([truth()], rows)


def test_runtime_pairs_keep_equal_budgets_and_all_condition_call_costs():
    a = analysis()
    rows = [runtime('a', 'f', 'calls', True, 1), runtime('a', 'f', 'priority', True, 3),
            runtime('b', 'g', 'calls', False, 4), runtime('b', 'g', 'priority', True, 2)]
    comparisons, details = a.runtime_contrasts([], rows, [], 100, 9009)
    effect = next(r for r in comparisons if r['track'] == 'recovery' and r['contrast'] == 'calls-priority'
                  and r['fault'] == 'none' and r['metric'] == 'completion' and r['population'] == 'all')
    costs = next(r for r in comparisons if r['track'] == 'recovery' and r['contrast'] == 'calls-priority'
                 and r['fault'] == 'none' and r['metric'] == 'charged_calls' and r['population'] == 'all')
    both = next(r for r in comparisons if r['track'] == 'recovery' and r['contrast'] == 'calls-priority'
                and r['fault'] == 'none' and r['metric'] == 'charged_calls' and r['population'] == 'both_success')
    assert effect['estimate'] == -.5 and effect['losses'] == 1 and effect['wins'] == 0
    assert costs['estimate'] == 0 and both['estimate'] == -2 and both['pairs'] == 1
    assert all(r['planning_budget'] == 512 for r in details if r['track'] == 'recovery')


def test_paired_losses_preserve_failure_reason_and_initial_selection():
    a = analysis()
    left = runtime('a', 'f', 'calls', False)
    right = runtime('a', 'f', 'priority', True)
    left['result'].update(global_unknown_ids=['x'], unresolved_gate_ids=['x'],
                          selection_log=[{'selected_route_index': None, 'feasible_route_indices': []}])
    right['result']['selection_log'] = [{'selected_route_index': 1, 'feasible_route_indices': [1]}]
    details = a.paired_runtime([left, right], lambda r: r['policy'] == 'calls',
                              lambda r: r['policy'] == 'priority', 'calls-priority', 'recovery', ('policy',))
    summary = a.paired_failure_causes(details)
    assert summary[0]['outcome'] == 'loss' and summary[0]['pairs'] == 1
    assert summary[0]['treatment_reason'] == 'no_feasible_route'
    assert summary[0]['baseline_reason'] == 'completed'
    assert summary[0]['treatment_unresolved_gate'] is True
    assert details[0]['treatment_first_selected_route'] is None
    assert details[0]['baseline_first_selected_route'] == 1


def test_failures_are_compact_and_supplied_query_audit_must_be_zero():
    a = analysis()
    row = runtime('c', 'f', completed=False)
    row['query_budget'] = 8
    row['result']['evidence_source'] = 'trusted_queries'
    with pytest.raises(ValueError, match='UNCOUNTED_AUDIT'):
        a.check_integration([row])
    row['result'].update(audit_interpreter_calls=0, audit_steps=0)
    assert a.check_integration([row])['no_uncounted_audit'] is True
    failures = a.runtime_failures('integrated', [row])
    assert len(failures) == 1 and 'trace' not in failures[0] and 'result' not in failures[0]
    assert failures[0]['reason'] == 'no_feasible_route'


def test_query_repeat_equality_requires_valid_complete_three_runs():
    a = analysis()
    rows = [{**obs('Q0', rep=i), 'track': 'query',
             'parsed': {'protocol_valid': True, 'order': ['q1', 'q2']}} for i in range(3)]
    assert a.repeat_summary([truth()], rows)[0]['identical_query_order'] is True
    rows[2]['parsed']['protocol_valid'] = False
    assert a.repeat_summary([truth()], rows)[0]['identical_query_order'] is False


def test_gate_unknowns_distinguish_true_disagreement_from_missing_inactive_evidence():
    a = analysis()
    t = truth()
    t['labels'].append({'id': 'inactive', **dict.fromkeys(AXES, 'not_applicable')})
    row = runtime('c', 'f', completed=False)
    row['result'].update(global_unknown_ids=['x', 'inactive'], unresolved_gate_ids=['inactive'],
                         evidence_source='trusted_queries', unresolved_commit_count=0)
    table = a.gate_evidence_summary([t], {'integrated': [row]})
    assert table[0]['global_unknown_sites'] == 2
    assert table[0]['true_global_unknown_sites'] == 1
    assert table[0]['unknown_on_nonunknown_truth'] == 1
    assert table[0]['unresolved_true_inactive_sites'] == 1


def test_analysis_rerun_is_byte_identical_and_refuses_mutated_outputs(tmp_path):
    a = analysis()
    rows = [obs(v) for v in ('A00', 'A01', 'A10', 'A11')]
    one = a.analyze([truth()], rows, models=('m',), draws=100, output=tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    a.analyze([truth()], list(reversed(rows)), models=('m',), draws=100, output=tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert one['summary']['primary_expected'] == 6
    (tmp_path / 'summary.json').write_text('{}')
    with pytest.raises(ValueError, match='IMMUTABLE_MISMATCH'):
        a.analyze([truth()], rows, models=('m',), draws=100, output=tmp_path)


def test_graph_equivalence_uses_source_only_and_accounts_extra_prompt_bytes():
    a = analysis()
    from test_acquisition_v9 import toy
    from run_phase9 import build_jobs
    jobs = build_jobs([toy(0)])
    audited = a.graph_audit(jobs)
    assert len(audited) == 2
    assert all(r['source_equivalent'] and r['graph_source_derived'] for r in audited)
    assert all(r['Q1']['prompt_bytes'] > r['Q0']['prompt_bytes'] for r in audited)
    next(r for r in jobs if r['view'] == 'Q1')['prompt'] = '{}'
    with pytest.raises((KeyError, ValueError)):
        a.graph_audit(jobs)


def test_observation_strata_distinguish_hidden_disagreement_from_singleton():
    a = analysis()
    from test_acquisition_v9 import toy
    c = toy(0)
    t = truth('c0', 'f0')
    t['worlds'] = [{'index': 0, 'labels': t['labels']}]
    assert a.case_characteristics([c], [t])[0]['observation_class'] == 'single_world'
    c['worlds'].append({'files': {'hidden': 'yes'}, 'grants': []})
    c.update(observable_files=[], observable_grants=[])
    t['worlds'].append({'index': 1, 'labels': [{'id': 'x', **dict.fromkeys(AXES, 'yes')}]})
    assert a.case_characteristics([c], [t])[0]['observation_class'] == 'hidden_disagreement'
    c['observable_files'] = ['hidden']
    assert a.case_characteristics([c], [t])[0]['observation_class'] == 'fully_observable'


def test_scientific_figures_are_immutable_and_reproducible(tmp_path):
    assert (ROOT / 'scripts/plot_phase9.py').exists(), 'Phase 9 plots are not implemented'
    p = importlib.import_module('plot_phase9')
    import matplotlib.pyplot as plt
    def create():
        fig, ax = plt.subplots(figsize=(3, 2))
        ax.plot([0, 1], [0, 1])
        return fig
    p.save_figure(create(), tmp_path, 'toy')
    before = {x.name: x.read_bytes() for x in tmp_path.iterdir()}
    p.save_figure(create(), tmp_path, 'toy')
    assert before == {x.name: x.read_bytes() for x in tmp_path.iterdir()}
    assert set(before) == {'toy.png', 'toy.pdf'}
    fig = create()
    fig.axes[0].set_title('changed')
    with pytest.raises(ValueError, match='IMMUTABLE_MISMATCH'):
        p.save_figure(fig, tmp_path, 'toy')
