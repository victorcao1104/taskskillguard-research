"""Hand-authored adversarial controls for posthoc recorded-trace validation."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
a = importlib.import_module('audit_phase11_traces')


def operation(key, generation=0):
    return hashlib.sha256(json.dumps(['epoch', 1, key, generation], ensure_ascii=False,
                                     sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def example():
    world = {'files': {'input': 'x'}, 'grants': [['write', 'out']]}
    key = ['site', 'w', 1]
    binding = {'epoch': 'epoch', 'operation_id': operation(key),
               'policy_context': 'context', 'signature': ['write', 'out', 'ok']}
    result = {'environment_trace': [{'binding': binding, 'committed': True}],
              'controller_trace': [{'key': key, 'route_index': 1, 'signature': ['write', 'out', 'ok'],
                                    'attempt': 1, 'status': 'receipt'}], 'status_log': [],
              'files': {'input': 'x', 'out': 'ok'}, 'emits': [], 'effect_calls': 1,
              'status_calls': 0, 'charged_calls': 1, 'unauthorized_effects': 0,
              'duplicate_effects': 0, 'remaining_quota': 31, 'remaining_status_budget': 1}
    return world, result


def test_authorization_rebuilt_from_world_grants_not_self_report():
    world, result = example()
    result['environment_trace'][0]['binding']['signature'][1] = 'forbidden'
    result['unauthorized_effects'] = 0
    got = a.audit_execution(world, result)
    assert got['observed_unauthorized_commits'] == 1
    assert got['unauthorized_commit_event_indices'] == [0]
    assert 'unauthorized_effects' in got['self_reported_mismatches']
    assert got['observed_binding_signature_mismatches'] == 1
    assert not got['replayed_files_equal']


def test_duplicate_logical_mutation_count_uses_commit_events():
    world, result = example()
    result['environment_trace'] *= 2
    result['duplicate_effects'] = 0
    got = a.audit_execution(world, result)
    assert got['observed_duplicate_logical_mutations'] == 1
    assert got['observed_duplicate_mutation_operation_ids'] == 1
    assert 'duplicate_effects' in got['self_reported_mismatches']


def test_same_signature_different_logical_keys_is_not_duplicate():
    world, result = example()
    second = deepcopy(result['environment_trace'][0])
    second['binding']['operation_id'] = operation(['site', 'w2', 1])
    result['environment_trace'].append(second)
    result['controller_trace'].append({**result['controller_trace'][0], 'key': ['site', 'w2', 1]})
    got = a.audit_execution(world, result)
    assert got['observed_duplicate_logical_mutations'] == 0
    assert got['unmapped_mutation_commits'] == 0


def test_fresh_generation_same_key_duplicate_is_detected():
    world, result = example()
    second = deepcopy(result['environment_trace'][0])
    second['binding']['operation_id'] = operation(['site', 'w', 1], 1)
    result['environment_trace'].append(second)
    got = a.audit_execution(world, result)
    assert got['observed_duplicate_logical_mutations'] == 1
    assert got['observed_duplicate_mutation_operation_ids'] == 0


def test_missing_logical_key_mapping_is_unknown_not_zero():
    world, result = example()
    result['environment_trace'][0]['binding']['operation_id'] = 'unmapped'
    got = a.audit_execution(world, result)
    assert got['observed_duplicate_logical_mutations'] is None
    assert got['unmapped_mutation_commits'] == 1
    assert got['observed_unauthorized_commits'] == 0


def test_controller_and_status_logs_reconstruct_charges_without_counters():
    world, result = example()
    result['controller_trace'] += [
        {**result['controller_trace'][0], 'status': 'receipt_reused'},
        {**result['controller_trace'][0], 'status': 'fenced_operation'},
        {**result['controller_trace'][0], 'status': 'quota_exhausted'}]
    result['status_log'] = [{'status': {'body': {'outcome': 'pending'}}},
                            {'error': 'status_budget_exhausted'}]
    result['charged_calls'] = 999
    got = a.audit_execution(world, result, quota=2, status_budget=0)
    assert got['reconstructed_effect_calls'] == 2
    assert got['reconstructed_status_calls'] == 1
    assert got['reconstructed_charged_calls'] == 3
    assert got['quota_violation'] and got['status_budget_violation']
    assert 'charged_calls' in got['self_reported_mismatches']


def test_malformed_or_absent_traces_do_not_become_clean_zero_audits():
    world, result = example()
    result['environment_trace'][0]['binding']['signature'] = ['write']
    got = a.audit_execution(world, result)
    assert got['malformed_environment_events'] == 1
    assert got['observed_unauthorized_commits'] is None
    absent = a.audit_execution(world, {})
    assert absent['audit_status'] == 'incomplete_trace'
    assert absent['observed_unauthorized_commits'] is None
    assert absent['reconstructed_charged_calls'] is None


def test_null_executions_are_retained_and_inputs_not_mutated():
    world, result = example(); before = deepcopy((world, result))
    got = a.audit_execution(world, result)
    assert got['audit_status'] == 'audited' and not got['self_reported_mismatches']
    assert (world, result) == before
    missing = a.audit_execution(world, None)
    assert missing['audit_status'] == 'null_execution'
    assert missing['observed_committed_events'] is None
