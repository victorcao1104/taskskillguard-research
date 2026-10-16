import importlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def module():
    assert (ROOT / 'scripts/run_phase10.py').exists(), 'Phase 10 acquisition is not implemented'
    return importlib.import_module('run_phase10')


def prior(tmp_path, cost=1.25):
    p = tmp_path / 'results/phase9/api/budget.jsonl'
    p.parent.mkdir(parents=True)
    data = (json.dumps({'reservation_id': 'old', 'model': 'gpt-6-luna',
        'status': 'settled', 'reserved_usd': 2, 'cost_usd': cost}) + '\n').encode()
    p.write_bytes(data)
    return data


def test_inherit_exact_ledger_and_lower_campaign_cap(tmp_path):
    data = prior(tmp_path)
    budget, audit = module().initialize(tmp_path)
    assert budget.path.read_bytes() == data
    assert audit['inherited_upper_usd'] == 1.25
    assert budget.limit == 7.25
    assert audit['cumulative_cap_usd'] == 29.551575125
    assert module().initialize(tmp_path)[0].total_cost == 1.25


def test_inheritance_rejects_changed_prefix(tmp_path):
    prior(tmp_path)
    module().initialize(tmp_path)
    (tmp_path / 'results/phase10/api/budget.jsonl').write_bytes(b'changed\n')
    with pytest.raises(ValueError, match='PREFIX'):
        module().initialize(tmp_path)


def test_campaign_cap_never_exceeds_remaining(tmp_path):
    prior(tmp_path, 29)
    budget, _ = module().initialize(tmp_path)
    assert budget.limit == 29.551575125


def test_registered_grid_has_exact_cells_and_models():
    cs=[{'case_id':'toy','family':'toy','split':'heldout'}]
    jobs=module().build_streams(cs)
    assert len(jobs)==12 and len({j['stream_id'] for j in jobs})==12
    assert {j['protocol'] for j in jobs}=={'full','batch','next'}
    assert {j['representation'] for j in jobs}=={'source','graph','padding'}
    assert {j['objective'] for j in jobs}=={'diagnostic','execution'}
    assert {j['model'] for j in jobs}=={'gpt-6-luna','gpt-4.1-mini'}


def test_offline_replay_never_dispatches_missing_request(tmp_path):
    mod=module()
    with pytest.raises(FileNotFoundError):
        mod.read_saved({'expected_request_hash':'missing'}, tmp_path)


def test_orphan_intent_does_not_retry(tmp_path):
    from run_phase5 import dispatch_once
    j={'job_id':'s-r0','expected_request_hash':'abc'}
    p=tmp_path/'dispatch/s-r0.json';p.parent.mkdir(parents=True)
    p.write_text(json.dumps({'job_id':'s-r0','request_hash':'abc'}))
    raw=dispatch_once(j,tmp_path,lambda:pytest.fail('must not repeat dispatch'))
    assert raw['status']=='interrupted_unknown'


def test_wire_schema_omits_unsupported_uniqueness_without_weakening_parser():
    m=module()
    from tsg.query_v10 import parse_selection,selection_schema
    schema=selection_schema(['a','b'],'batch',2)
    assert 'uniqueItems' not in m.wire_schema(schema)['properties']['queries']
    assert schema['properties']['queries']['uniqueItems'] is True
    assert not parse_selection({'status':'completed','text':'{"queries":["a","a"]}'},['a','b'],'batch',2)['protocol_valid']


def test_cap_exhaustion_is_saved_and_replay_does_not_send(tmp_path):
    m=module()
    case=json.loads((ROOT/'data/phase7/heldout.jsonl').read_text().splitlines()[0])
    spec=next(s for s in m.build_streams([case]) if s['protocol']=='next')
    class Exhausted:
        def call(self,*a,**kw):raise RuntimeError('BUDGET_LIMIT')
    result=m.acquire_stream(spec,case,tmp_path,Exhausted())
    assert not result['protocol_valid'] and result['decision_count']==1
    assert result['decisions'][0]['raw_status']=='budget_exhausted'
    assert m.acquire_stream(spec,case,tmp_path,None)==result


def test_unknown_request_cost_keeps_reservation_bound():
    m=module();job={'model':'gpt-4.1-mini','reservation_upper_usd':.1}
    assert m.request_cost({'status':'transport_error'},job)==(.1,'reservation_upper_unknown_usage')
    assert m.request_cost({'status':'budget_exhausted'},job)==(0.0,'no_provider_io')
    assert m.request_cost({'status':'completed','usage':{'input_tokens':1000,'output_tokens':100}},job)[0]==.00056
