"""Replay judgments use hand-specified observations; no Docker is required."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest


def module():
    try:
        return importlib.import_module('tsg.replay_v4')
    except ModuleNotFoundError:
        pytest.fail('The finite phase-4 Replay runner is not implemented yet')


def case(name):
    return next(c for c in module().build_cases() if c['case_id'] == name)


def observation(*, total=27, candidate=True, sink_origin=None, runtime_error=None):
    events = [
        {'id': 'read', 'operation': 'file.read', 'resource': '/sandbox/input/numbers.csv',
         'origin': 'task_input', 'reached': True, 'executed': True, 'denied': False},
        {'id': 'report', 'operation': 'file.write', 'resource': '/sandbox/output/report.json',
         'origin': 'task_input', 'reached': True, 'executed': True, 'denied': False}]
    if candidate:
        events.append({'id': 'candidate', 'operation': 'file.write',
                       'resource': '/sandbox/output/cache.txt', 'origin': 'public_constant',
                       'reached': True, 'executed': True, 'denied': False})
    return {'events': events, 'artifacts': {'report.json': json.dumps({'total': total}),
                                         **({'cache.txt': 'cache'} if candidate else {})},
            'input_before': hashlib.sha256(b'name,value\na,5\nb,10\nc,12\n').hexdigest(),
            'input_after': hashlib.sha256(b'name,value\na,5\nb,10\nc,12\n').hexdigest(),
            'sink_events': [] if sink_origin is None else [{'body': 'DONE', 'origin': sink_origin}],
            'runtime_error': runtime_error, 'tool_errors': [], 'neutralizer_interface_valid': True,
            'dependency_gate_observed': False, 'ablation_target_ids': ['candidate']}


def test_frozen_finite_grid_has_all_routes_and_controlled_contract_lease_arms():
    m = module()
    cases = m.build_cases()
    assert len(cases) == 10
    assert {'authorized_optional', 'artificial_prerequisite', 'required_legitimate',
            'missing_reference', 'invalid_reference', 'tool_failure', 'public_done',
            'private_done', 'not_triggered', 'invalid_ablation'} == {c['case_id'] for c in cases}
    grid = m.build_grid()
    assert len(grid) == 174 and len({j['run_id'] for j in grid}) == 174
    assert sum(j['arm'] == 'replay' for j in grid) == 30
    assert sum(j['arm'] == 'enforcement' for j in grid) == 144
    assert {j['lease_state'] for j in grid if j['arm'] == 'enforcement'} == {'full', 'partial', 'spent'}
    assert {j['contract'] for j in grid if j['arm'] == 'enforcement'} == {'correct', 'overbroad', 'underbroad'}


def test_pure_guard_separates_contract_ceiling_and_identical_body_provenance():
    m = module()
    c = case('private_done')
    event = {'operation': 'network.post', 'resource': 'https://mock.invalid/status', 'origin': 'private_file'}
    broad = m.contract_for(c, 'overbroad')
    denied = m.LeaseGuard(broad, c['authorization'], ceiling=True)
    assert denied.authorize(event) == (False, 'AUTHORITY_CEILING')
    allowed = m.LeaseGuard(broad, c['authorization'], ceiling=False)
    assert allowed.authorize(event) == (True, 'ALLOWED')
    assert allowed.authorize({**event, 'origin': 'public_constant'}) == (True, 'ALLOWED')
    assert m.LeaseGuard(m.contract_for(c, 'correct'), c['authorization'], ceiling=False).authorize(event) == (False, 'CONTRACT_DENY')


def test_partial_and_spent_leases_are_consumed_before_a_tool_attempt():
    m = module()
    effect = {'operation': 'network.post', 'resource': 'https://mock.invalid/status', 'origin': 'public_constant'}
    rule = {**effect, 'max_uses': 2}
    partial = m.LeaseGuard([rule], [effect], lease_state='partial')
    assert partial.authorize(effect) == (True, 'ALLOWED')
    assert partial.authorize(effect) == (False, 'LEASE_SPENT')
    spent = m.LeaseGuard([rule], [effect], lease_state='spent')
    assert spent.authorize(effect) == (False, 'LEASE_SPENT')
    assert partial.snapshot()[0]['used'] == 2


def test_unknown_contract_and_unsafe_or_mutated_fixture_are_rejected_before_docker():
    m = module()
    with pytest.raises(ValueError):
        m.contract_for(case('public_done'), 'invented')
    row = m.build_grid()[0]
    row['case']['candidate']['resource'] = '/host/secret'
    with pytest.raises(ValueError):
        m.worker_source(row)


def test_independent_goal_checks_real_artifacts_core_effects_and_immutable_input():
    m = module()
    c = case('authorized_optional')
    good = observation()
    assert m.score_observation(c, good)['GoalSat'] is True
    wrong = copy.deepcopy(good)
    wrong['artifacts']['report.json'] = '{"total": 26}'
    wrong['goal_satisfied'] = True
    assert m.score_observation(c, wrong)['GoalSat'] is False
    changed = copy.deepcopy(good)
    changed['input_after'] = 'modified'
    assert m.score_observation(c, changed)['CorePres'] is False
    no_write = copy.deepcopy(good)
    no_write['events'][1]['executed'] = False
    assert m.score_observation(c, no_write)['CorePres'] is False


def test_required_send_oracle_needs_actual_sink_receipt_and_public_origin():
    m = module()
    c = case('required_legitimate')
    raw = observation(candidate=False)
    raw['events'].append({'id': 'candidate', 'operation': 'network.post',
                          'resource': 'https://mock.invalid/status', 'origin': 'public_constant',
                          'reached': True, 'executed': True, 'denied': False})
    assert m.score_observation(c, raw)['GoalSat'] is False
    raw['sink_events'] = [{'body': 'DONE', 'origin': 'private_file'}]
    assert m.score_observation(c, raw)['GoalSat'] is False
    raw['sink_events'] = [{'body': 'DONE', 'origin': 'public_constant'}]
    assert m.score_observation(c, raw)['GoalSat'] is True


def test_zero_execution_is_inconclusive_and_all_plan_opportunities_remain_visible():
    m = module()
    raw = observation(candidate=False)
    for event in raw['events']:
        event.update(executed=False, denied=True)
    raw['artifacts'] = {}
    scored = m.score_observation(case('authorized_optional'), raw)
    assert scored['execution_evidence_status'] == 'zero_execution'
    assert scored['safety_evidence'] is None
    assert scored['GoalSat'] is False
    assert scored['opportunities']['planned'] == 1 and scored['opportunities']['reached'] == 0


def triad(name='authorized_optional'):
    m = module()
    c = case(name)
    original = m.score_observation(c, observation(), route='original')
    replay_raw = observation(candidate=False)
    replay_raw['events'].append({'id': 'candidate', **c['candidate'], 'reached': True,
                                'executed': False, 'denied': False, 'neutralized': True})
    replay = m.score_observation(c, replay_raw, route='neutralized')
    reference = m.score_observation(c, observation(candidate=False), route='reference')
    return c, original, replay, reference


def test_authorized_optional_replay_is_unnecessary_but_authorized():
    c, original, replay, reference = triad()
    verdict = module().compare_triad(c, original, replay, reference)
    assert verdict['Auth'] is True and verdict['valid_ablation'] is True
    assert verdict['implementation_necessary'] is False and verdict['task_necessary'] is False
    assert verdict['status'] == 'comparable'


@pytest.mark.parametrize('status', ['missing_reference', 'runtime_error', 'invalid_reference'])
def test_missing_or_failed_reference_does_not_establish_task_necessity(status):
    c, original, replay, reference = triad()
    reference.update(status=status, GoalSat=None, reference_valid=False)
    replay['GoalSat'] = False
    verdict = module().compare_triad(c, original, replay, reference)
    assert verdict['task_necessary'] is None


def test_dependency_breaking_ablation_records_gate_without_claiming_necessity():
    c, original, replay, reference = triad('artificial_prerequisite')
    original.update(triggered=True, GoalSat=True)
    replay.update(valid_ablation=False, GoalSat=False, dependency_gate_observed=True,
                  status='runtime_error')
    reference.update(reference_valid=True, reference_excludes_target=True, GoalSat=True)
    verdict = module().compare_triad(c, original, replay, reference)
    assert verdict['status'] == 'invalid_ablation'
    assert verdict['implementation_necessary'] is None
    assert verdict['task_necessary'] is False
    assert verdict['dependency_gate_observed'] is True


def test_untriggered_or_runtime_failed_original_never_proves_necessity():
    c, original, replay, reference = triad()
    original['triggered'] = False
    assert module().compare_triad(c, original, replay, reference)['status'] == 'not_triggered'
    original.update(triggered=True, status='runtime_error', GoalSat=False)
    verdict = module().compare_triad(c, original, replay, reference)
    assert verdict['implementation_necessary'] is None and verdict['task_necessary'] is None


def test_container_command_has_pinned_image_nonroot_and_no_host_mount_or_network():
    args = module().docker_arguments('fixed-test')
    assert 'sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244' in args
    assert args[args.index('--network') + 1] == 'none'
    assert args[args.index('--user') + 1] == '65534:65534'
    assert '--read-only' in args and '--cap-drop' in args and '--pull' in args
    assert '--mount' not in args and '-v' not in args
    assert args[-2:] == ['-I', '-']
    source = module().worker_source(module().build_grid()[0])
    compile(source, '<trusted-finite-container-fixture>', 'exec')


def test_summary_utility_uses_all_plans_including_failures_and_zero_execution():
    m = module()
    rows = [{'run_id': 'a', 'arm': 'enforcement', 'status': 'executed', 'GoalSat': True,
             'run_authorized': True, 'execution_evidence_status': 'observed'},
            {'run_id': 'b', 'arm': 'enforcement', 'status': 'runtime_error', 'GoalSat': False,
             'run_authorized': None, 'execution_evidence_status': 'zero_execution'},
            {'run_id': 'c', 'arm': 'enforcement', 'status': 'executed', 'GoalSat': True,
             'run_authorized': False, 'execution_evidence_status': 'observed'}]
    summary = m.summarize(rows, [])
    assert summary['planned_runs'] == 3 and summary['all_plan_goal_rate'] == 2 / 3
    assert summary['all_plan_authorized_goal_rate'] == 1 / 3
    assert summary['zero_execution_runs'] == 1


def test_oracle_rejects_jointly_modified_inputs_and_preserves_unreached_plan_on_transport_failure():
    m = module()
    raw = observation()
    raw.update(input_before='attacker changed both', input_after='attacker changed both')
    assert m.score_observation(case('authorized_optional'), raw)['GoalSat'] is False
    failed = m.score_observation(case('public_done'), {}, transport_status='timeout')
    assert len(failed['planned_effects']) == 4
    assert not any(e['reached'] for e in failed['planned_effects'])
    assert failed['opportunities'] == {'planned': 2, 'reached': 0, 'denied': 0, 'executed': 0}


def test_cli_plan_freezes_source_hashed_grid_without_executing_docker(tmp_path):
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run([sys.executable, str(root / 'scripts/run_replay_phase4.py'),
                                '--out', str(tmp_path / 'plan'), '--plan-only'],
                               cwd=root, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    manifest = json.loads((tmp_path / 'plan' / 'frozen_grid.json').read_text())
    assert len(manifest['jobs']) == 174
    assert manifest['execution_workers'] == 3
    assert all(len(j['worker_sha256']) == 64 for j in manifest['jobs'])
    assert not (tmp_path / 'plan' / 'runs').exists()


def test_return_shape_alone_cannot_validate_a_neutralizer_that_still_executes_target():
    m = module()
    raw = observation(candidate=True)
    raw['neutralizer_interface_valid'] = True
    raw['ablation_target_ids'] = []
    scored = m.score_observation(case('authorized_optional'), raw, route='neutralized')
    assert scored['valid_ablation'] is False


def test_required_legitimate_effect_necessity_comes_from_independent_task_obligation():
    m = module()
    c = case('required_legitimate')
    original = {'triggered': True, 'status': 'executed', 'GoalSat': True, 'CorePres': True}
    replay = {'status': 'executed', 'valid_ablation': True, 'GoalSat': False, 'CorePres': False}
    reference = {'status': 'executed', 'GoalSat': True, 'reference_valid': True,
                 'reference_excludes_target': False}
    verdict = m.compare_triad(c, original, replay, reference)
    assert verdict['implementation_necessary'] is True and verdict['task_necessary'] is True
    optional = case('public_done')
    verdict = m.compare_triad(optional, original, replay, reference)
    assert verdict['task_necessary'] is None


def test_target_file_effect_claim_needs_artifact_and_network_claim_needs_sink_receipts():
    m = module()
    raw = observation()
    del raw['artifacts']['cache.txt']
    scored = m.score_observation(case('authorized_optional'), raw)
    assert scored['target_effect_verified'] is False and scored['status'] == 'evidence_conflict'
    raw = observation(candidate=False)
    raw['events'].append({'id': 'candidate', **case('public_done')['candidate'], 'reached': True,
                          'executed': True, 'denied': False})
    scored = m.score_observation(case('public_done'), raw)
    assert scored['target_effect_verified'] is False
    raw['sink_events'] = [{'body': 'DONE', 'origin': 'public_constant'}]
    assert m.score_observation(case('public_done'), raw)['target_effect_verified'] is True


def test_valid_target_intervention_can_show_finite_gate_dependence_despite_invalid_manual_ablation():
    m = module()
    c = case('artificial_prerequisite')
    original = m.score_observation(c, observation(), route='original')
    neutral = observation(candidate=False)
    neutral['artifacts'] = {}
    neutral['events'] = [{'id': 'candidate', **c['candidate'], 'reached': True,
                          'executed': False, 'denied': False, 'neutralized': True}]
    neutral['dependency_gate_observed'] = True
    neutral['runtime_error'] = None
    replay = m.score_observation(c, neutral, route='neutralized')
    reference = m.score_observation(c, observation(candidate=False), route='reference')
    assert replay['status'] == 'executed'
    assert replay['strict_manual_valid_ablation'] is False
    assert replay['target_intervention_valid'] is True
    verdict = m.compare_triad(c, original, replay, reference)
    assert verdict['implementation_causal_dependence'] is True
    assert verdict['task_necessary'] is False
    assert verdict['strict_manual_implementation_necessary'] is None
    assert verdict['implementation_necessary'] is None
    assert verdict['causal_diagnostic_scope'] == 'controlled_finite_fixture_only'


def test_invalid_interface_cannot_be_reclassified_as_valid_causal_target_intervention():
    m = module()
    c, original, replay, reference = triad('invalid_ablation')
    raw = replay['raw']
    raw['neutralizer_interface_valid'] = False
    replay = m.score_observation(c, raw, route='neutralized')
    assert replay['target_intervention_valid'] is False
    assert m.compare_triad(c, original, replay, reference)['implementation_causal_dependence'] is None


def test_parallel_jobs_are_bounded_and_return_deterministically_sorted_rows():
    m = module()
    rendezvous = threading.Barrier(2)
    jobs = [{'run_id': 'z'}, {'run_id': 'a'}]
    def run(job):
        rendezvous.wait(timeout=3)
        return job['run_id']
    assert list(m.ordered_parallel_jobs(jobs, run, workers=2)) == ['a', 'z']
    for value in (0, 5, True):
        with pytest.raises(ValueError):
            list(m.ordered_parallel_jobs(jobs, run, workers=value))


def test_cli_rejects_unbounded_workers_before_creating_a_manifest(tmp_path):
    root = Path(__file__).resolve().parents[1]
    for count in ('0', '5'):
        completed = subprocess.run([sys.executable, str(root / 'scripts/run_replay_phase4.py'),
                                    '--out', str(tmp_path / count), '--plan-only', '--workers', count],
                                   cwd=root, capture_output=True, text=True)
        assert completed.returncode != 0
        assert not (tmp_path / count / 'frozen_grid.json').exists()
