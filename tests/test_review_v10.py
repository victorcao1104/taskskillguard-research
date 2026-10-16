"""Independent prefreeze review using tiny synthetic inputs and no provider I/O."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


def toy():
    effect = {'id': 'finish', 'kind': 'effect', 'op': 'write',
              'resource': 'out', 'value': 'ok'}
    return {'case_id': 'review', 'family': 'review', 'split': 'heldout',
            'source': '```tsg-workflow\n' + json.dumps({'version': 1, 'steps': [effect]}) + '\n```',
            'worlds': [{'files': {}, 'grants': [['write', 'out']]}],
            'routes': [], 'goal': {'files': {'out': 'ok'}}, 'catalog_closed': True}


def spec():
    import run_phase10 as acquisition
    return next(row for row in acquisition.build_streams([toy()])
                if row['cell'] == 'next_exec' and row['model'] == 'gpt-4.1-mini')


class ScriptedClient:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = 0

    def call(self, model, system, prompt, *, tag, max_output, replicate, response_schema):
        from tsg.models import make_request
        request = make_request(model, system, prompt, max_output)
        request['text']['format'] = {'type': 'json_schema', 'name': 'tsg_response_v3',
                                   'strict': True, 'schema': response_schema}
        fingerprint = hashlib.sha256(json.dumps({'request': request, 'replicate': replicate},
                                     sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.calls += 1
        return {'request_hash': fingerprint, 'status': 'completed',
                'text': json.dumps(next(self.values))}


def test_failed_later_decision_retains_paid_original_and_restarts_without_dispatch(tmp_path):
    import run_phase10 as acquisition
    client = ScriptedClient([{'query_id': 'b0r0'}, {'query_id': 'b0r0'}])
    first = acquisition.acquire_stream(spec(), toy(), tmp_path, client)
    assert client.calls == 2
    assert not first['protocol_valid'] and first['stop_reason'] == 'protocol_failure'
    assert first['order'] == ['b0r0']
    assert first['result']['authorization_complete']
    assert first['result']['executions'] == 1
    second = acquisition.acquire_stream(spec(), toy(), tmp_path, client)
    assert second == first and client.calls == 2
    assert len(list((tmp_path / 'dispatch').glob('*.json'))) == 2


def test_cap_rejection_is_a_persisted_terminal_outcome_without_provider_io(tmp_path, monkeypatch):
    import run_phase10 as acquisition
    import tsg.models_v3 as models
    from tsg.budget_v7_locked import BudgetV7Locked
    def forbidden(*args, **kwargs):
        raise AssertionError('A rejected reservation must never contact the provider')
    monkeypatch.setattr(models.urllib.request, 'urlopen', forbidden)
    budget = BudgetV7Locked(tmp_path / 'budget.jsonl', 0)
    client = models.ClientV3('synthetic-test-placeholder', tmp_path / 'raw', budget)
    result = acquisition.acquire_stream(spec(), toy(), tmp_path, client)
    assert not result['protocol_valid']
    assert result['order'] == [] and result['result']['executions'] == 0
    assert result['stop_reason'] == 'budget_exhausted'
    assert result['decisions'][0]['raw_status'] == 'budget_exhausted'
    assert budget.total_cost == 0
    assert acquisition.acquire_stream(spec(), toy(), tmp_path, client) == result


def test_ready_at_end_of_valid_prefix_does_not_attribute_later_invalid_decision(tmp_path, monkeypatch):
    import run_phase10 as acquisition
    import experiment_phase10 as experiment
    case = toy()
    case['program'] = json.loads(case['source'].split('```tsg-workflow\n')[1].split('\n```')[0])
    client = ScriptedClient([{'query_id': 'b0r0'}, {'query_id': 'b0r0'}])
    stream = acquisition.acquire_stream(spec(), case, tmp_path, client)
    captured = []
    monkeypatch.setattr(experiment, 'cases', lambda: [case])
    monkeypatch.setattr(experiment, 'read_rows', lambda path: [stream])
    monkeypatch.setattr(experiment, 'write_chunks', lambda path, rows: captured.extend(rows))
    monkeypatch.setattr(experiment, 'immutable', lambda *args: None)
    experiment.query_scenarios()
    rows = [r for r in captured if r['pipeline'] == 'gpt-4.1-mini:next_exec' and r['budget'] == 8]
    stopped = next(r for r in rows if r['stop_mode'] == 'authorization')
    fixed = next(r for r in rows if r['stop_mode'] == 'fixed')
    assert stopped['result']['authorization_complete']
    assert stopped['model_request_count'] == 1 and stopped['protocol_valid']
    assert fixed['model_request_count'] == 2 and not fixed['protocol_valid']
