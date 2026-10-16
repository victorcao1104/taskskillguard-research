import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from run_phase9 import repeat_ids, build_jobs


def toy(i):
    program = {'version': 1, 'steps': [{'id': 'x', 'kind': 'effect', 'op': 'write', 'resource': 'out', 'value': 'ok' + str(i)}], 'functions': {}}
    return {'case_id': 'c' + str(i), 'family': 'f' + str(i // 2), 'split': 'heldout',
            'source': '```tsg-workflow\n' + json.dumps(program) + '\n```', 'routes': [],
            'worlds': [{'files': {}, 'grants': [['write', 'out']]}], 'catalog_closed': True,
            'goal': {'files': {'out': 'ok' + str(i)}}}


def test_repeats_and_request_grid_are_fixed_and_distinct():
    cs = [toy(i) for i in range(24)]
    assert repeat_ids(cs) == repeat_ids(list(reversed(cs)))
    assert len(repeat_ids(cs)) == 6
    jobs = build_jobs(cs)
    assert len(jobs) == 336
    assert len({j['expected_request_hash'] for j in jobs}) == 336
    assert sum(j['replicate'] == 0 for j in jobs) == 288
    assert {j['model'] for j in jobs} == {'gpt-6-luna', 'gpt-4.1-mini'}
    assert all(j['track'] in {'factorial', 'query'} for j in jobs)
    assert sum(j['reservation_upper_usd'] for j in jobs) < 4
