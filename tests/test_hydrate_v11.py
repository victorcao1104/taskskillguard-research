"""Clean-checkout fixture integrity, including refusal to overwrite."""
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hydrate_phase11_test', ROOT / 'scripts/hydrate_phase11.py')
hydrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hydrate)


def test_hydration_copies_archived_bytes_and_rejects_mutation(tmp_path):
    for cohort in ('main', 'challenge'):
        d = tmp_path / 'results/phase11/reference' / cohort / 'first-pass'
        d.mkdir(parents=True)
        content = b'{"synthetic":true}\n'
        (d / 'cases.jsonl').write_bytes(content)
        (d / 'provenance.json').write_text(json.dumps({'artifact_sha256': {
            'cases.jsonl': sha256(content).hexdigest()}}), encoding='utf-8')
    assert hydrate.hydrate(tmp_path) == {'main': 2, 'challenge': 2}
    assert hydrate.hydrate(tmp_path) == {'main': 2, 'challenge': 2}
    target = tmp_path / 'work/phase11-reference-firstpass/cases.jsonl'
    assert target.read_bytes() == content
    target.write_bytes(b'changed')
    with pytest.raises(ValueError, match='EXISTING_FIRSTPASS_DIFFERS'):
        hydrate.hydrate(tmp_path)
    assert target.read_bytes() == b'changed'


def test_archived_truth_hash_is_checked(tmp_path):
    d = tmp_path / 'results/phase11/reference/main/first-pass'
    d.mkdir(parents=True)
    (d / 'cases.jsonl').write_bytes(b'wrong')
    (d / 'provenance.json').write_text(json.dumps({'artifact_sha256': {'cases.jsonl': 'bad'}}))
    with pytest.raises(ValueError, match='ARCHIVED_FIRSTPASS_CHANGED'):
        hydrate.hydrate(tmp_path)
    assert not (tmp_path / 'work').exists()
