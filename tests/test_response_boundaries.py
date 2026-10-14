import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from tsg.models import Client, Budget
from tsg.graph import validate_model_graph
from tsg.benchmark import build_cases
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_experiment import contract


def test_identical_concurrent_requests_are_saved_once(tmp_path):
    calls=[]
    class Response:
        def __enter__(self):
            return self
        def __exit__(self,*args):
            pass
        def read(self):
            time.sleep(.02)
            return json.dumps({'status':'completed','output':[],'usage':{'input_tokens':1,'output_tokens':1}}).encode()
    def transport(*args,**kwargs):
        calls.append(1)
        return Response()
    client=Client('mock-key',tmp_path/'raw',Budget(tmp_path/'budget.jsonl'))
    with patch('urllib.request.urlopen',transport), ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda i:client.call('gpt-4.1-mini','json','json',tag=str(i)),range(12)))
    assert len(calls)==1
    assert len(client.budget.entries)==1
    assert len({r['reservation_id'] for r in results})==1


def test_contract_cannot_smuggle_unsupported_policy_fields():
    case=build_cases()[0]
    class MockClient:
        def call(self,*args,**kwargs):
            return {'status':'completed','request_hash':'mock','text':json.dumps({'rules':[{'operation':r['operation'],'resource':r['resource'],'effect':'forbid'} for r in case['policy']['rules']], 'supported':False, 'default_action':'allow'})}
    assert contract(MockClient(),case,'mock',True)['status']=='unresolved'


def test_graph_invalid_operations_and_hallucinated_literals_remain_unresolved():
    files={'SKILL.md':'Read /sandbox/a.\n'}
    graph={'nodes':[{'id':'a','operation':'grant.root','resource':'/sandbox/a','summary':'x','provenance':{'file':'SKILL.md','line_start':1,'line_end':1}},
                    {'id':'b','operation':'file.read','resource':'/sandbox/absent','summary':'x','provenance':{'file':'SKILL.md','line_start':1,'line_end':1}}]}
    accepted,invalid=validate_model_graph(graph,files)
    assert not accepted['nodes']
    assert len(invalid)==2
