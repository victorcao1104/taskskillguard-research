"""Independent hand-computed controls for the Phase 11 analysis contract."""
from copy import deepcopy
import importlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
a = importlib.import_module('analyze_phase11')


def fixture():
    cases = [{'case_id': 'a-0', 'family': 'a', 'split': 'heldout', 'worlds': [{}, {}],
              'routes': [{}], 'observable_files': [], 'observable_grants': []},
             {'case_id': 'b-0', 'family': 'b', 'split': 'challenge', 'worlds': [{}],
              'routes': [{}], 'observable_files': [], 'observable_grants': []}]
    refs = [{'case_id': 'a-0', 'executions': [[{'safe_success': True}], [{'safe_success': True}]],
             'observation_classes': [{'world_indices': [0, 1], 'common_safe_routes': [0]}],
             'hindsight_certificate_cost': [{'actual_world_index': i, 'minimum_positive_total_queries': 2} for i in (0, 1)]},
            {'case_id': 'b-0', 'executions': [[{'safe_success': False}]],
             'observation_classes': [{'world_indices': [0], 'common_safe_routes': []}],
             'hindsight_certificate_cost': [{'actual_world_index': 0, 'minimum_positive_total_queries': None}]}]
    return cases, refs


def policy(case='a-0', world=0, stop=True, status='certified', count=2):
    return {'case_id': case, 'world_index': world, 'policy': 'observe_cover', 'budget': 12, 'stop': stop,
            'result': {'query_count': count, 'interpreter_steps': count*3, 'observations': {},
                       'certificate': {'status': status, 'route': 0 if status == 'certified' else None}},
            'execution': {'authorized_goal': True} if status == 'certified' else None}


def test_family_equal_bootstrap_and_input_order_invariance():
    rows = [{'family': 'a', 'difference': -1}] + [{'family': 'b', 'difference': 1}]*17
    result = a.paired_interval(rows)
    assert result['estimate'] == 0 and result['families'] == 2 and result['pairs'] == 18
    assert result['interval95'] == [-1, 1]
    assert result == a.paired_interval(list(reversed(rows)))
    assert a.paired_interval([])['estimate'] is None


def test_unknown_class_and_hindsight_gap_are_not_actual_world_feasibility():
    cases, refs = fixture()
    rows = [policy(status='unknown'), policy(case='b-0', status='unknown'), policy(count=5)]
    detail = a.policy_scores(cases, refs, rows)
    assert detail[0]['unknown_class'] == 'budget_limited_certifiable'
    assert detail[1]['unknown_class'] == 'unresolved_robust_infeasibility'
    assert detail[1]['hindsight_cost_gap'] is None
    assert detail[2]['hindsight_cost_gap'] == 3


def test_family_aggregate_averages_worlds_before_families_and_scaling_stays_separate():
    rows = [{'cohort': 'main', 'family': 'a', 'condition': 'x', 'score': 0}]*20
    rows += [{'cohort': 'challenge', 'family': 'b', 'condition': 'x', 'score': 1}]
    rows += [{'cohort': 'scaling', 'family': 'a', 'condition': 'x', 'score': 100}]
    agg = a.aggregate(rows, ('condition',), ('score',))
    combined = next(r for r in agg if r['cohort'] == 'combined')
    assert combined['estimate'] == .5 and combined['families'] == 2 and combined['rows'] == 21
    assert next(r for r in agg if r['cohort'] == 'scaling')['estimate'] == 100


def test_partial_invalid_stream_keeps_earlier_certificate_completion_and_reports_protocol_failure():
    cases, refs = fixture()
    stream = {'case_id': 'a-0', 'family': 'a', 'model': 'toy', 'view': 'source', 'stop': True,
              'world_index': 0, 'stream_id': 's', 'query_count': 2,
              'protocol_valid': False, 'stop_reason': 'protocol_failure',
              'certificate': {'status': 'certified'}, 'api_cost_upper_usd': .1,
              'api_elapsed_seconds_sum': 3, 'decisions': [
                  {'raw_status': 'completed', 'parsed': {'protocol_valid': True}, 'usage': {'input_tokens': 5, 'output_tokens': 2}},
                  {'raw_status': 'incomplete', 'parsed': {'protocol_valid': False}, 'usage': None}]}
    integrated = [{'case_id': 'a-0', 'stream_id': 's', 'world_index': 0, 'model': 'toy',
                   'view': 'source', 'stop': True, 'budget': 12, 'fault': 'none',
                   'policy': 'strict_stop', 'acquired_queries': 2,
                   'certificate': {'status': 'certified'}, 'result': {'authorized_goal': True}}]
    scored = a.stream_scores(cases, refs, [stream], integrated)[0]
    assert scored['completion'] == 1 and scored['partial_paid_prefix_success'] == 1
    assert scored['stream_valid'] == 0 and scored['valid_complete_stream_success'] == 0
    replay = a.integrated_scores(cases, refs, [stream], integrated)[0]
    assert replay['completion'] == 1 and replay['valid_complete_stream_success'] == 0
    assert scored['decision_attempts'] == 2 and scored['completed_envelopes'] == 1
    assert scored['valid_decisions'] == 1 and scored['missing_usage_decisions'] == 1
    assert scored['api_cost_upper_usd'] == .1


def test_budget_rejection_is_censoring_and_retained_as_failure():
    cases, refs = fixture()
    stream = {'case_id': 'a-0', 'model': 'toy', 'view': 'source', 'stop': True, 'world_index': 0,
              'stream_id': 's', 'query_count': 0, 'protocol_valid': False,
              'stop_reason': 'budget_exhausted', 'certificate': {'status': 'unknown'},
              'api_cost_upper_usd': 0, 'api_elapsed_seconds_sum': 0,
              'decisions': [{'raw_status': 'budget_exhausted', 'parsed': {'protocol_valid': False}}]}
    row = a.stream_scores(cases, refs, [stream], [])[0]
    assert row['budget_censored'] == 1 and row['budget_rejections_before_io'] == 1
    assert row['provider_or_uncertain_requests'] == 0 and row['completion'] == 0


def test_paired_contrast_missing_pairs_are_explicit():
    rows = [{'cohort': 'main', 'case_id': 'a', 'world_index': 0, 'family': 'a',
             'cell': cell, 'score': value} for cell, value in [('left', 1), ('right', 0)]]
    rows += [{'cohort': 'main', 'case_id': 'b', 'world_index': 0, 'family': 'b', 'cell': 'left', 'score': 0}]
    effects, summary = a.contrast(rows, 'example', lambda r: r['cell'] == 'left',
                                  lambda r: r['cell'] == 'right', (), ('score',))
    assert len(effects) == 2 and summary[0]['unmatched_left'] == 1
    assert summary[0]['estimate'] == 1 and summary[0]['wins'] == 1


def test_duplicate_pairs_rejected_and_pure_summary_does_not_mutate():
    cases, refs = fixture()
    rows = [policy(), policy(stop=False, count=5)]
    before = deepcopy((cases, refs, rows))
    got = a.summarize(cases, refs, policies=rows)
    assert (cases, refs, rows) == before
    assert got == a.summarize(cases, refs, policies=list(reversed(rows)))
    with pytest.raises(ValueError, match='DUPLICATE'):
        a.summarize(cases, refs, policies=[rows[0], rows[0]])


def test_recovery_denominators_include_missing_certificates_and_untriggered():
    cases, _ = fixture()
    rows = [{'case_id': 'a-0', 'world_index': i, 'fault': 'ambiguous_after',
             'policy': 'terminal_status', 'status_budget': 1, 'certificate_status': 'certified',
             'result': {'authorized_goal': True, 'fault_diagnostics': {'fault_triggered': i == 0}}}
            for i in (0, 1)]
    rows += [{'case_id': 'b-0', 'world_index': 0, 'fault': 'ambiguous_after',
              'policy': 'terminal_status', 'status_budget': 1, 'certificate_status': 'infeasible', 'result': None}]
    detail = a.recovery_scores(cases, rows)
    assert len(detail) == 3 and sum(r['fault_triggered'] for r in detail) == 1
    assert sum(r['completion'] for r in detail) == 2
    assert sum(r['missing_certificate'] for r in detail) == 1


def test_grid_validator_rejects_missing_or_duplicate_evidence():
    with pytest.raises(ValueError, match='INCOMPLETE'):
        a._expected([{'x': 1}], {(1,), (2,)}, ('x',), 'TOY')
    with pytest.raises(ValueError, match='DUPLICATE'):
        a._expected([{'x': 1}, {'x': 1}], {(1,)}, ('x',), 'TOY')


def test_publication_exports_have_no_clock_or_random_id_variation():
    p = importlib.import_module('plot_phase11')
    def draw():
        fig, ax = p.plt.subplots(figsize=(2, 2))
        ax.plot([0, 1], [0, 1]); ax.set_ylim(0, 1)
        return p.figure_bytes(fig)
    first, second = draw(), draw()
    assert first == second
    assert set(first) == {'png', 'svg', 'pdf'}


def test_typed_error_normalization_preserves_original_strings():
    cases, refs = fixture()
    ref = {'files': {}, 'emits': [], 'safe_success': False, 'charged_calls': 0,
           'receipt_reuses': 0, 'steps_entered': 1, 'error': 'unbound_variable:x'}
    refs[0]['executions'][0][0] = ref
    row = {'case_id': 'a-0', 'world_index': 0, 'route': 0,
           'audit': {**ref, 'error': 'unbound_variable', 'interpreter_steps': 1},
           'execution': {'files': {}, 'emits': [], 'authorized_goal': False,
                         'charged_calls': 0, 'receipt_reuses': 0, 'failure_reason': 'unbound_variable'}}
    result = a.semantics_scores(cases, refs, [row])[0]
    assert result['all_compared_equal'] == 1
    assert result['raw_reference_audit_error_equal'] == 0
    assert result['reference_error'] == 'unbound_variable:x'
