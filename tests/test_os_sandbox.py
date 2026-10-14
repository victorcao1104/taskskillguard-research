import hashlib
import json
import os
import tarfile
from pathlib import Path

import pytest

from tsg.os_sandbox import ContainerSandbox, parse_trace, replay_verdict, stage_bundle, validate_job


def test_stage_rejects_traversal_and_changed_source(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'main.py').write_bytes(b'print(1)\n')
    row = {'skill_id': 'test', 'bundle_path': str(source), 'file_sha256': {'main.py': hashlib.sha256(b'print(1)\n').hexdigest()}}
    archive = tmp_path / 'source.tar'
    staged = stage_bundle(row, archive)
    assert staged['files'] == 1
    with tarfile.open(archive) as reader:
        assert reader.extractfile('source/main.py').read() == b'print(1)\n'
    (source / 'main.py').write_bytes(b'print(2)\n')
    with pytest.raises(ValueError, match='hash'):
        stage_bundle(row, archive)
    row['file_sha256'] = {'../outside.py': 'x'}
    with pytest.raises(ValueError, match='path'):
        stage_bundle(row, archive)


def test_stage_rejects_oversized_content(tmp_path):
    (tmp_path / 'a.py').write_bytes(b'x' * 9)
    row = {'skill_id': 'test', 'bundle_path': str(tmp_path), 'file_sha256': {'a.py': hashlib.sha256(b'x' * 9).hexdigest()}}
    with pytest.raises(ValueError, match='limit'):
        stage_bundle(row, tmp_path / 'out.tar', max_bytes=8)


def test_job_validation_disallows_host_paths_and_unbounded_arguments():
    with pytest.raises(ValueError):
        validate_job({'kind': 'source', 'script': '../../etc/passwd', 'args': []})
    with pytest.raises(ValueError):
        validate_job({'kind': 'source', 'script': '/home/user/key.py', 'args': []})
    with pytest.raises(ValueError):
        validate_job({'kind': 'source', 'script': 'a.py', 'args': ['x'] * 100})


def test_trace_uses_actual_syscall_return_values():
    trace = '12 execve("/usr/bin/python", ["python"], 0x1) = 0\n12 openat(AT_FDCWD, "/source/main.py", O_WRONLY) = -1 EROFS (Read-only file system)\n12 connect(3, {sa_family=AF_INET, sin_port=htons(80), sin_addr=inet_addr("192.0.2.1")}, 16) = -1 ENETUNREACH (Network is unreachable)\n'
    out = parse_trace(trace)
    assert out['process_events'] == 1
    assert out['file_events'] == 1
    assert out['network_events'] == 1
    assert out['denied_errno'] == {'EROFS': 1, 'ENETUNREACH': 1}


def test_incomparable_replay_never_proves_necessity():
    original = {'status': 'executed', 'goal_satisfied': True, 'target_triggered': True}
    replay = {'status': 'runtime_error', 'goal_satisfied': False}
    reference = {'status': 'executed', 'goal_satisfied': True, 'reference_excludes_target': True}
    assert replay_verdict(original, replay, reference)['task_necessary'] is None
    replay['status'] = 'executed'
    result = replay_verdict(original, replay, reference)
    assert result['status'] == 'dependency_blocked'
    assert result['task_necessary'] is False
    reference['reference_excludes_target'] = False
    assert replay_verdict(original, replay, reference) == {'status': 'unknown', 'task_necessary': None}
    replay['ablation_valid'] = False
    assert replay_verdict(original, replay, reference)['status'] == 'invalid_ablation'
    replay['ablation_valid'] = True
    original['goal_satisfied'] = False
    assert replay_verdict(original, replay, reference)['status'] == 'original_failed'


def test_independent_reference_cannot_silently_bypass_guard():
    with pytest.raises(ValueError, match='reference'):
        validate_job({'kind': 'fixture', 'fixture': 'csv', 'variant': 'reference', 'guard_enabled': True, 'policy': []})


@pytest.mark.skipif(os.environ.get('TSG_OS_INTEGRATION') != '1', reason='Requires explicit Docker integration run')
def test_real_sandbox_containment_and_syscall_audit(tmp_path):
    result = ContainerSandbox().run({'kind': 'fixture', 'fixture': 'csv', 'variant': 'original', 'target': 'optional_cache', 'probe': True}, tmp_path)
    assert result['status'] == 'executed'
    assert result['goal_satisfied'] is True
    assert result['containment']['readonly_source'] is True
    assert result['containment']['readonly_root'] is True
    assert result['containment']['external_network'] is True
    assert result['containment']['audit_write'] is True
    assert result['audit']['file_events'] > 0
    assert result['audit']['network_events'] > 0
    assert result['audit']['process_events'] > 0
    assert result['resources']['child_cpu_seconds'] > 0
    assert result['resources']['cgroup_memory_peak_bytes'] > 0


@pytest.mark.skipif(os.environ.get('TSG_OS_INTEGRATION') != '1', reason='Requires explicit Docker integration run')
def test_guard_blocks_real_optional_write_but_preserves_required_work(tmp_path):
    job = {'kind': 'fixture', 'fixture': 'csv', 'guard_enabled': True, 'policy': [{'operation': 'file.read', 'resource': '/sandbox/input/numbers.csv'}, {'operation': 'file.write', 'resource': '/sandbox/output/report.json'}]}
    result = ContainerSandbox().run(job, tmp_path)
    assert result['goal_satisfied'] is True
    assert not (tmp_path / 'output/optional_cache.txt').exists()
    assert any(e['resource'] == '/sandbox/output/optional_cache.txt' and e['decision'] == 'deny' and not e['executed'] for e in result['tool_events'])
    assert not any(e['required'] and e['decision'] == 'deny' for e in result['tool_events'])


@pytest.mark.skipif(os.environ.get('TSG_OS_CORRECTED_ORACLES') != '1', reason='Requires separately built corrected-oracles image')
@pytest.mark.parametrize('fixture,context,policy', [
    ('http', 'low', None),
    ('smtp', 'high', [{'operation': 'file.read', 'resource': '/sandbox/input/message.txt'}, {'operation': 'email.send', 'resource': 'recipient@example.invalid'}, {'operation': 'file.write', 'resource': '/sandbox/output/sent.txt'}]),
])
def test_goal_oracle_does_not_waive_literal_output_or_required_draft(tmp_path, fixture, context, policy):
    job = {'kind': 'fixture', 'fixture': fixture, 'context': context, 'guard_enabled': policy is not None, 'policy': policy or []}
    result = ContainerSandbox(image='taskskillguard-os:corrected-oracles').run(job, tmp_path)
    assert result['status'] == 'executed'
    assert len(result['sink_events']) == 1
    assert result['goal_satisfied'] is False
