import hashlib
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify_phase2_release.py'


def module():
    spec = importlib.util.spec_from_file_location('phase2_release', SCRIPT)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_grid_rejects_duplicate_even_when_count_matches():
    errors = []
    module().check_grid([{'id': 'a'}, {'id': 'a'}], ('id',), {('a',), ('b',)}, 'track', errors)
    assert any('duplicate' in e for e in errors)
    assert any('missing' in e for e in errors)


def test_raw_hash(tmp_path):
    m = module()
    request = {'model': 'gpt-4.1-mini', 'input': []}
    digest = hashlib.sha256(json.dumps({'request': request, 'replicate': 0}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    folder = tmp_path / 'results/api/raw'
    folder.mkdir(parents=True)
    target = folder / (digest + '.json')
    target.write_text(json.dumps({'request': request, 'replicate': 0, 'request_hash': digest}), encoding='utf-8')
    errors = []
    m.check_raw(tmp_path, digest, errors)
    assert not errors
    target.write_text(json.dumps({'request': request, 'replicate': 1}), encoding='utf-8')
    m.check_raw(tmp_path, digest, errors)
    assert any('fingerprint' in e for e in errors)


def test_raw_reference_cannot_escape_evidence_directory(tmp_path):
    errors = []
    module().check_raw(tmp_path, '../outside', errors)
    assert errors == ['invalid request_hash: ../outside']
