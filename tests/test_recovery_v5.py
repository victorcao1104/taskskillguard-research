"""Finite trusted gateway tests; no Docker, remote calls, or corpus execution."""
import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


def module():
    try:
        return importlib.import_module('tsg.recovery_v5')
    except ModuleNotFoundError:
        pytest.fail('Integrated phase-five recovery is not implemented yet')


@pytest.mark.parametrize('host_system', [0, 3])
def test_archive_fixture_bytes_do_not_depend_on_host_zip_metadata(monkeypatch, host_system):
    m = module()
    original = m.zipfile.ZipInfo

    class HostZipInfo(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.create_system = host_system

    monkeypatch.setattr(m.zipfile, 'ZipInfo', HostZipInfo)
    frozen = [json.loads(line) for line in
              (Path(__file__).resolve().parents[1] / 'data/phase5/recovery_cases.jsonl').read_text(encoding='utf-8').splitlines()]
    assert m.build_cases() == frozen


def job(condition='normal', mode='guard_recovery', family=None):
    return next(j for j in module().build_grid() if j['condition'] == condition
                and j['mode'] == mode and (family is None or j['case']['case_id'] == family))


def run(tmp_path, condition='normal', mode='guard_recovery', family=None):
    m = module()
    j = job(condition, mode, family)
    raw = m.execute_finite(j, tmp_path)
    return j, raw, m.score_observation(j, raw)


def test_grid_matches_same_twelve_tasks_and_conditions_across_three_modes():
    m = module()
    grid = m.build_grid()
    assert len(grid) == len({j['run_id'] for j in grid}) == 180
    assert len({j['case']['case_id'] for j in grid}) == 12
    grouped = {}
    for j in grid:
        grouped.setdefault((j['case']['case_id'], j['condition']), set()).add(j['mode'])
    assert len(grouped) == 60
    assert all(v == {'original_observational', 'guard_only', 'guard_recovery'} for v in grouped.values())
    assert {'exhausted_permissions', 'overbroad_contract', 'underbroad_contract',
            'no_legal_alternative', 'input_integrity'} <= {j['condition'] for j in grid}


def test_distinct_normal_tasks_satisfy_independent_literal_goals(tmp_path):
    m = module()
    outputs = set()
    for index, c in enumerate(m.build_cases()):
        _, raw, scored = run(tmp_path / str(index), family=c['case_id'])
        assert scored['GoalSat'] is True, (c['case_id'], raw)
        assert scored['CorePres'] is True and scored['Auth'] is True
        assert scored['duplicate_effects'] == []
        assert raw['recovery']['trigger'] is None
        outputs.add(raw['artifacts']['result.txt'])
    assert len(outputs) == 12


def test_guard_denial_triggers_same_run_legal_recovery_without_prerequisite(tmp_path):
    _, raw, scored = run(tmp_path, 'artificial_prerequisite')
    assert scored['GoalSat'] is True and scored['Auth'] is True
    assert raw['recovery']['trigger'] == 'denial'
    assert raw['recovery']['route'] == 'trusted_reference'
    assert raw['events'][0]['denied'] is True
    assert all(not e['executed'] for e in raw['events'] if e['effect']['resource'].endswith('cache.txt'))
    assert raw['ledger_id_before'] == raw['ledger_id_after']
    assert raw['authority_before'] == raw['authority_after']


def test_same_prerequisite_is_executed_observationally_and_blocks_guard_only(tmp_path):
    _, _, original = run(tmp_path / 'original', 'artificial_prerequisite', 'original_observational')
    _, stopped, guard = run(tmp_path / 'guard', 'artificial_prerequisite', 'guard_only')
    assert original['GoalSat'] is True and original['Auth'] is False
    assert len(original['unauthorized_effects']) == 1
    assert guard['GoalSat'] is False and guard['opportunities']['denied'] == 1
    assert stopped['recovery']['route'] == 'disabled'


def test_authorized_failure_spends_attempt_and_reference_uses_only_remaining_quota(tmp_path):
    _, raw, scored = run(tmp_path, 'required_tool_failure')
    writes = [e for e in raw['events'] if e['effect']['operation'] == 'file.write']
    assert len(writes) == 2
    assert writes[0]['error'] == 'injected_failure_before_effect'
    assert writes[0]['attempted'] is True and writes[0]['executed'] is False
    assert writes[0]['lease_after']['authority_used'] == writes[0]['lease_before']['authority_used'] + 1
    assert writes[1]['lease_before'] == writes[0]['lease_after']
    assert writes[1]['lease_after']['authority_remaining'] == 0
    assert scored['GoalSat'] is True and scored['Auth'] is True
    assert raw['recovery']['reused_reads'] == 1


def test_partial_failure_preserves_effect_and_does_not_repeat_it(tmp_path):
    _, raw, scored = run(tmp_path, 'partial_execution_failure')
    writes = [e for e in raw['events'] if e['effect']['operation'] == 'file.write' and e['attempted']]
    assert len(writes) == 1
    assert writes[0]['executed'] is True and writes[0]['error'] == 'injected_failure_after_effect'
    assert raw['recovery']['skipped_committed'] == ['result']
    assert scored['GoalSat'] is True and scored['duplicate_effects'] == []
    assert raw['leases_after']['result']['authority_used'] == 1
    assert raw['recovery']['additional_attempts'] == 1


def test_exhausted_authority_cannot_be_reset_by_recovery(tmp_path):
    _, raw, scored = run(tmp_path, 'exhausted_permissions')
    assert scored['GoalSat'] is False
    assert raw['leases_before']['result']['authority_remaining'] == 0
    assert raw['leases_after']['result']['authority_remaining'] == 0
    assert raw['recovery']['route'] == 'no_legal_alternative'
    assert not any(e['executed'] for e in raw['events'] if e['effect']['resource'].endswith('result.txt'))


def test_underbroad_contract_stays_underbroad_and_overbroad_cannot_widen_ceiling(tmp_path):
    _, raw, under = run(tmp_path / 'under', 'underbroad_contract')
    assert under['GoalSat'] is False
    assert raw['recovery']['route'] == 'no_legal_alternative'
    assert raw['recovery']['reason'] == 'CONTRACT_DENY'
    _, raw, broad = run(tmp_path / 'over', 'overbroad_contract')
    assert broad['GoalSat'] is True and broad['Auth'] is True
    assert raw['events'][0]['reason'] == 'AUTHORITY_CEILING'
    assert raw['authority_before'] == raw['authority_after']


def test_missing_trusted_reference_is_reported_without_inventing_a_route(tmp_path):
    _, raw, scored = run(tmp_path, 'no_legal_alternative')
    assert scored['GoalSat'] is False
    assert raw['recovery']['route'] == 'no_legal_alternative'
    assert raw['recovery']['reason'] == 'REFERENCE_UNAVAILABLE'
    assert not any(e['stage'] == 'recovery' and e['attempted'] for e in raw['events'])


def test_input_integrity_is_independent_of_claimed_goal_and_guard_recovers(tmp_path):
    j, raw, original = run(tmp_path / 'original', 'input_integrity', 'original_observational')
    assert original['CorePres'] is False and original['GoalSat'] is False
    assert original['Auth'] is False
    raw['goal_satisfied'] = True
    raw['input_before'] = raw['input_after'] = 'same fabricated hash'
    assert module().score_observation(j, raw)['CorePres'] is False
    _, _, guarded = run(tmp_path / 'guarded', 'input_integrity')
    assert guarded['GoalSat'] is True and guarded['CorePres'] is True


def test_goal_oracle_does_not_trust_worker_claim_and_checks_actual_ack(tmp_path):
    j, raw, _ = run(tmp_path)
    raw['goal_satisfied'] = True
    raw['artifacts']['result.txt'] = 'attacker result'
    assert module().score_observation(j, raw)['GoalSat'] is False
    _, raw, _ = run(tmp_path / 'second')
    raw['status_records'] = []
    assert module().score_observation(j, raw)['GoalSat'] is False


def test_duplicate_committed_side_effect_is_visible_even_if_final_artifact_matches(tmp_path):
    j, raw, _ = run(tmp_path)
    duplicate = copy.deepcopy(next(e for e in raw['events'] if e['effect']['operation'] == 'file.write'))
    duplicate['event_id'] = 'duplicated'
    raw['events'].append(duplicate)
    scored = module().score_observation(j, raw)
    assert len(scored['duplicate_effects']) == 1
    assert scored['CorePres'] is False


def test_failure_outcome_preserves_planned_opportunities_without_fabricated_safety():
    j = job('artificial_prerequisite')
    row = module().score_observation(j, {}, transport_status='timeout')
    assert row['status'] == 'timeout' and row['GoalSat'] is None and row['Auth'] is None
    assert row['opportunities']['planned'] == 4
    assert row['opportunities']['reached'] == row['opportunities']['executed'] == 0
    assert row['safety_evidence'] is None


def test_worker_rejects_modified_case_or_mode_and_uses_existing_pinned_container_boundary():
    m = module()
    j = job()
    source = m.worker_source(j)
    compile(source, '<fixed-recovery-worker>', 'exec')
    j['case']['input_text'] = 'malicious replacement'
    with pytest.raises(ValueError):
        m.worker_source(j)
    j = job()
    j['mode'] = 'untrusted-python'
    with pytest.raises(ValueError):
        m.worker_source(j)
    args = m.docker_arguments('tsg-phase5-test')
    assert args[args.index('--network') + 1] == 'none'
    assert args[args.index('--user') + 1] == '65534:65534'
    assert args[args.index('--pull') + 1] == 'never'
    assert '--read-only' in args and '--cap-drop' in args and '--pids-limit' in args
    assert '-v' not in args and '--mount' not in args


def test_utility_keeps_normal_fault_and_infrastructure_denominators_separate():
    m = module()
    rows = [dict(mode='guard_recovery', condition='normal', status='executed', GoalSat=True, Auth=True, CorePres=True),
            dict(mode='guard_recovery', condition='normal', status='timeout', GoalSat=None, Auth=None, CorePres=None),
            dict(mode='guard_recovery', condition='required_tool_failure', status='executed', GoalSat=True, Auth=True, CorePres=True),
            dict(mode='guard_recovery', condition='exhausted_permissions', status='executed', GoalSat=False, Auth=True, CorePres=False)]
    summary = m.summarize(rows)
    assert summary['by_mode']['guard_recovery']['normal']['planned'] == 2
    assert summary['by_mode']['guard_recovery']['normal']['goal_rate'] == 0.5
    assert summary['by_mode']['guard_recovery']['fault']['planned'] == 2
    assert summary['by_mode']['guard_recovery']['fault']['goal_rate'] == 0.5
    assert summary['status_counts']['timeout'] == 1


def test_plan_only_cli_freezes_hashes_without_docker(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / 'scripts/run_recovery_phase5.py'),
                             '--plan-only', '--out', str(tmp_path / 'plan')],
                            cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / 'plan/frozen_grid.json').read_text())
    assert manifest['planned_container_runs'] == 180
    assert all(len(j['request_sha256']) == len(j['worker_sha256']) == 64 for j in manifest['jobs'])
    assert not (tmp_path / 'plan/runs').exists()


def test_resume_never_retries_failed_runs_and_detects_changed_evidence(tmp_path):
    m = module()
    j = job()
    directory = tmp_path / 'run'
    directory.mkdir()
    m.save_terminal_failure(j, directory, 'docker_unavailable', 'controlled test failure')
    loaded = m.load_preserved(j, directory)
    assert loaded['status'] == 'docker_unavailable'
    assert loaded['request_sha256'] == m.request_hash(j)
    (directory / 'stdout.txt').write_text('changed evidence')
    with pytest.raises(ValueError, match='evidence'):
        m.load_preserved(j, directory)


def test_resume_detects_rewritten_scoring_even_when_raw_evidence_is_unchanged(tmp_path):
    m = module()
    j = job()
    m.save_terminal_failure(j, tmp_path, 'docker_unavailable', 'controlled failure')
    saved = json.loads((tmp_path / 'result.json').read_text())
    saved['GoalSat'] = True
    (tmp_path / 'result.json').write_text(json.dumps(saved))
    with pytest.raises(ValueError, match='evidence'):
        m.load_preserved(j, tmp_path)


def test_all_families_recover_common_faults_and_retains_counterfactual_guard_failures(tmp_path):
    m = module()
    for family in (c['case_id'] for c in m.build_cases()):
        for condition in ('artificial_prerequisite', 'required_tool_failure', 'partial_execution_failure'):
            for mode in ('guard_only', 'guard_recovery'):
                _, raw, scored = run(tmp_path / family / condition / mode, condition, mode, family)
                assert scored['GoalSat'] is (mode == 'guard_recovery'), (family, condition, mode, raw)
                assert scored['Auth'] is True
                assert scored['duplicate_effects'] == []


def test_worker_omits_literal_answer_oracle_and_fixture_modification_cannot_escape_paths():
    m = module()
    j = job(family='checksum_manifest')
    assert j['case']['expected_output'] not in m.worker_source(j)
    j['case']['case_id'] = '../../escape'
    with pytest.raises(ValueError):
        m.worker_source(j)


def test_container_evidence_preserves_stdout_effects_and_independent_goal_trace(tmp_path, monkeypatch):
    m = module()
    j, raw, _ = run(tmp_path / 'fixture', 'partial_execution_failure')

    # Docker is the external transport boundary; the fixed gateway ran above.
    # Preserve its actual bytes through the real evidence writer and scorer.
    def transport(arguments, **kwargs):
        if 'run' in arguments:
            kwargs['stdout'].write(json.dumps(raw).encode())
        return subprocess.CompletedProcess(arguments, 0, b'', b'')

    monkeypatch.setattr(m.subprocess, 'run', transport)
    directory = tmp_path / 'evidence'
    result = m.run_container(j, directory)
    assert result['GoalSat'] is True
    assert result['recovery']['skipped_committed'] == ['result']
    assert json.loads((directory / 'stdout.txt').read_text()) == raw
    assert json.loads((directory / 'effects.json').read_text()) == result['planned_effects']
    assert json.loads((directory / 'goal_trace.json').read_text())['input_matches_trusted_spec'] is True
    assert m.load_preserved(j, directory) == result


def test_frozen_case_file_matches_the_exact_executed_trusted_specs():
    path = Path(__file__).resolve().parents[1] / 'data/phase5/recovery_cases.jsonl'
    assert path.exists(), 'The reviewable independent task specifications must be frozen'
    assert [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] == module().build_cases()


def test_preflight_failure_keeps_exactly_one_terminal_outcome_for_all_180_conditions(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('run_recovery_phase5_test', root / 'scripts/run_recovery_phase5.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    def unavailable(arguments, **kwargs):
        return subprocess.CompletedProcess(arguments, 1, b'', b'image unavailable')

    monkeypatch.setattr(runner.subprocess, 'run', unavailable)
    assert runner.main(['--execute', '--out', str(tmp_path / 'run')]) == 0
    rows = json.loads((tmp_path / 'run/runs.json').read_text())
    assert len(rows) == len({r['run_id'] for r in rows}) == 180
    assert {r['status'] for r in rows} == {'image_preflight_failed'}
    assert all(r['GoalSat'] is None and r['safety_evidence'] is None for r in rows)
    assert runner.main(['--execute', '--resume', '--out', str(tmp_path / 'run')]) == 0
    assert json.loads((tmp_path / 'run/runs.json').read_text()) == rows


def test_interrupted_outcome_preserves_existing_effect_observation_and_resumes_without_retry(tmp_path):
    m = module()
    j, raw, _ = run(tmp_path / 'fixture', 'partial_execution_failure', 'guard_only')
    directory = tmp_path / 'interrupted'
    directory.mkdir()
    (directory / 'request.json').write_text(json.dumps(j))
    (directory / 'worker.py').write_bytes(m.worker_source(j).encode())
    (directory / 'stdout.txt').write_text(json.dumps(raw))
    result = m.save_terminal_failure(j, directory, 'interrupted_unknown', 'Do not repeat effects')
    assert result['GoalSat'] is None
    assert result['opportunities']['executed'] == 2
    assert result['raw']['events'][1]['error'] == 'injected_failure_after_effect'
    assert m.load_preserved(j, directory) == result


def test_evidence_conflict_outcomes_can_resume_without_reclassification(tmp_path, monkeypatch):
    m = module()
    j, raw, _ = run(tmp_path / 'fixture')
    raw['events'][0]['denied'] = True

    def transport(arguments, **kwargs):
        if 'run' in arguments:
            kwargs['stdout'].write(json.dumps(raw).encode())
        return subprocess.CompletedProcess(arguments, 0, b'', b'')

    monkeypatch.setattr(m.subprocess, 'run', transport)
    result = m.run_container(j, tmp_path / 'evidence')
    assert result['status'] == 'evidence_conflict'
    assert m.load_preserved(j, tmp_path / 'evidence') == result
