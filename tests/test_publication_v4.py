import importlib.util
import json
from pathlib import Path
import pytest


spec = importlib.util.spec_from_file_location('phase4_publication',
    Path(__file__).resolve().parents[1] / 'scripts/report_phase4.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def packet():
    return module.annotation_packet([{'skill_id': 's', 'source_sha256': {'a': 'hash'},
        'action': {'id': 'a1', 'provenance': {'file': 'a', 'start': 1, 'end': 1},
                   'candidate_status': 'suspicious', 'sensitivity': 'secret',
                   'operation': 'file.read', 'resource': 'hidden'}}], 'A')


def test_source_first_packet_does_not_expose_predictions():
    row = packet()[0]
    assert set(row['candidate']) == {'id', 'provenance'}
    assert row['labels'] == {} and row['notes'] == ''


@pytest.mark.parametrize('field,value', [('labels', {'valid': True}), ('notes', 'human note'),
                                        ('status', 'reviewed')])
def test_never_erase_human_work(tmp_path, field, value):
    path = tmp_path / 'annotation.jsonl'
    data = packet()
    module.write_blank_packet(path, data)
    data[0][field] = value
    path.write_text(json.dumps(data[0]) + '\n', encoding='utf-8')
    original = path.read_bytes()
    with pytest.raises(ValueError, match='REFUSE_TO_OVERWRITE'):
        module.write_blank_packet(path, packet())
    assert path.read_bytes() == original


def test_blank_packet_is_repeatable_but_population_cannot_change(tmp_path):
    path = tmp_path / 'annotation.jsonl'
    module.write_blank_packet(path, packet())
    original = path.read_bytes()
    module.write_blank_packet(path, packet())
    assert path.read_bytes() == original
    changed = packet()
    changed[0]['candidate']['id'] = 'other'
    with pytest.raises(ValueError, match='POPULATION'):
        module.write_blank_packet(path, changed)
    assert path.read_bytes() == original
