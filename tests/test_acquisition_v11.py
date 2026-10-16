import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from test_certificate_v11 import case
from run_phase11 import acquire_stream, build_specs, make_job
from tsg.certificate_v11 import CertificateSession,make_reader

def test_online_actual_dispatch_stops_before_next_request(tmp_path):
    c=case(True);c.update(case_id='toy',family='toy',split='heldout',generation={'seed':0})
    spec={'case_id':'toy','family':'toy','model':'gpt-4.1-mini','view':'source','stop':True,
          'world_index':0,'stream_id':'toy-mini-source-online','replicate':1,'max_queries':12}
    sent=[]
    def invoke(job):
        sent.append(job)
        q=['w0r0','w1r0'][len(sent)-1]
        return {'status':'completed','text':'{"query_id":"'+q+'"}',
                'request_hash':job['expected_request_hash'],'usage':{'input_tokens':1,'output_tokens':1}}
    r=acquire_stream(spec,c,tmp_path,invoke=invoke)
    assert len(sent)==2 and r['certificate']['status']=='certified'
    assert r['decision_count']==2 and len(list((tmp_path/'requests').glob('*.json')))==2
    replay=acquire_stream(spec,c,tmp_path)
    assert replay==r

def test_failure_retains_paid_prefix_no_fallback(tmp_path):
    c=case(True);c.update(case_id='toy',family='toy',split='heldout',generation={'seed':0})
    spec={'case_id':'toy','family':'toy','model':'gpt-4.1-mini','view':'source','stop':True,
          'world_index':0,'stream_id':'toy-fail','replicate':2,'max_queries':12}
    sent=[]
    def invoke(job):
        sent.append(job)
        return {'status':'completed','text':'{"query_id":"w0r0"}' if len(sent)==1 else '{}',
                'request_hash':job['expected_request_hash']}
    r=acquire_stream(spec,c,tmp_path,invoke=invoke)
    assert not r['protocol_valid'] and r['query_count']==1 and len(sent)==2

def test_distinct_stream_ids_and_replications():
    c=case();c.update(case_id='p11-x-0',family='x',split='heldout',generation={'seed':0})
    specs=build_specs([c]);assert len(specs)==8
    assert len({s['replicate'] for s in specs})==8
    assert sum(not s['stop'] for s in specs)==2

def test_surrogate_token_matched_padding():
    c=case();s=CertificateSession(c,make_reader(c,0));spec={'model':'gpt-4.1-mini','view':'padding',
        'replicate':1,'stream_id':'toy','case_id':'toy'}
    j=make_job(spec,s,0)
    assert j['local_tokens']['graph']==j['local_tokens']['padding']
    assert j['tokenizer']=='o200k_base surrogate, not verified model tokenizer'

def test_family_grid_cannot_substitute_duplicate_family_ids():
    from run_phase11 import validate_specs
    rows=[{'case_id':str(i),'family':'same'} for i in range(36) for _ in range(8)]
    with pytest.raises(ValueError):validate_specs(rows)

def test_budget_rejection_is_not_provider_request():
    from run_phase11 import summarize_streams
    class Budget:total_cost=19;limit=26
    decision={'raw_status':'budget_exhausted','parsed':{'protocol_valid':False}}
    row={'protocol_valid':False,'certificate':{'status':'unknown'},'decisions':[decision]}
    s=summarize_streams([row],Budget(),{'inherited_upper_usd':19})
    assert s['decision_attempts']==1 and s['provider_or_uncertain_requests']==0
