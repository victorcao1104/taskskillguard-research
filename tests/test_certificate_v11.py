import json
from copy import deepcopy
from itertools import product
import pytest
from tsg.certificate_v11 import CertificateSession, make_reader, decide, choose_query, run_policy


def case(hidden=False):
    p={'version':1,'steps':[{'id':'w','kind':'effect','op':'write','resource':'/out','value':'ok'}]}
    alt={'version':1,'steps':[{'id':'w2','kind':'effect','op':'write','resource':'/out','value':'ok'}]}
    return {'source':'```tsg-workflow\n'+json.dumps(p)+'\n```','program':p,'routes':[alt],
        'worlds':[{'files':{'/marker':'a'},'grants':[['write','/out']]},
                  {'files':{'/marker':'b'},'grants':[['write','/out']]}],
        'goal':{'files':{'/out':'ok'}},'catalog_closed':True,
        'observable_files':[] if hidden else ['/marker'],'observable_grants':[]}


def test_positive_needs_every_compatible_world_then_survives_refinement():
    c=case();s=CertificateSession(c,make_reader(c,0));s.consume('w0r0')
    assert s.check()['status']=='unknown'
    s.consume('w1r0');cert=s.check();assert cert['status']=='certified' and cert['route']==0
    s.consume('o0');assert s.check()['status']=='certified'
    assert s.result()['interpreter_calls']==2 and s.result()['initial_observation_calls']==1
    assert s.result()['compatible_worlds']==[0]


def test_negative_requires_no_remaining_separating_observation():
    assert decide([0,1],2,{(0,0):False,(1,1):False},True)['status']=='unknown'
    assert decide([0,1],2,{(0,0):False,(1,1):False},False)['status']=='infeasible'


def test_run_query_does_not_reveal_actual_world():
    c=case();s=CertificateSession(c,make_reader(c,1));s.consume('w0r0')
    assert s.result()['compatible_worlds']==[0,1]
    s.consume('o0');assert s.result()['compatible_worlds']==[1]


def test_invalid_selection_no_effect_and_snapshot_independence():
    c=case();s=CertificateSession(c,make_reader(c,0));before=s.result()
    with pytest.raises(ValueError):s.consume('invented')
    assert s.result()==before
    s.consume('w0r0');snap=s.result();snap['observations'].clear()
    assert s.result()['observations']
    with pytest.raises(ValueError):s.consume('w0r0')


def test_guarded_dedup_queries_match_runtime_contract():
    c=case(True);c['program']['steps']=[{'id':'a','kind':'effect','op':'emit','resource':'x','value':'y','key':'k'},
                                     {'id':'b','kind':'effect','op':'emit','resource':'x','value':'y','key':'k'}]
    c['source']='```tsg-workflow\n'+json.dumps(c['program'])+'\n```'
    c['worlds']=[{'files':{},'grants':[['emit','x']]}]
    c['goal']={'emits':[{'resource':'x','value':'y','count':2}]}
    s=CertificateSession(c,make_reader(c,0));s.consume('w0r0')
    r=s.result()['observations']['w0r0'];assert not r['safe_success']
    assert r['receipt_reuses']==1 and len(r['emits'])==1


def test_denied_and_quota_cannot_be_certified():
    c=case(True);c['worlds'][0]['grants']=[]
    s=CertificateSession(c,make_reader(c,0));s.consume('w0r0')
    assert s.result()['observations']['w0r0']['error']=='grant_denied'
    s=CertificateSession(case(),make_reader(case(),0),quota=0);s.consume('w0r0')
    assert s.result()['observations']['w0r0']['error']=='quota_exhausted'


def test_checker_has_no_interpreter_or_reader_calls(monkeypatch):
    c=case();s=CertificateSession(c,make_reader(c,0));s.consume('w0r0');s.consume('w1r0')
    monkeypatch.setattr('tsg.certificate_v11.audit_run',lambda *a,**k:pytest.fail('free run'))
    s._reader=lambda key:pytest.fail('free observation')
    for _ in range(3):assert s.check()['status']=='certified'


def test_online_stop_calls_selector_only_before_certificate():
    c=case(True);calls=[]
    def chooser(session):
        calls.append(session.result()['query_count']);return choose_query(session,'route_cover')
    stopped=run_policy(c,0,chooser,budget=12,stop=True)
    assert stopped['certificate']['status']=='certified'
    assert calls==[0,1] and stopped['query_count']==2
    fixed=run_policy(c,0,lambda s:choose_query(s,'route_cover'),budget=12,stop=False)
    assert fixed['query_count']==4


def test_exhaustive_small_certificate_soundness_and_monotone_witness():
    checked=0
    for cells in product((None,False,True),repeat=6):
        outcomes={(w,r):cells[2*w+r] for w in range(3) for r in range(2) if cells[2*w+r] is not None}
        for sep in (False,True):
            d=decide([0,1,2],2,outcomes,sep);checked+=1
            if d['status']=='certified':
                assert all(outcomes.get((w,d['route'])) is True for w in (0,1,2))
                for subset in ([0],[1],[2],[0,2]):
                    assert all(outcomes[(w,d['route'])] is True for w in subset)
            elif d['status']=='infeasible':
                assert not sep and all(any(outcomes.get((w,r)) is False for w in range(3)) for r in range(2))
    assert checked==1458


def test_unavailable_and_mismatched_observations_abstain():
    c=case();s=CertificateSession(c,lambda key:{'available':False});s.consume('o0')
    assert s.result()['compatible_worlds']==[0,1]
    s=CertificateSession(c,lambda key:{'available':True,'present':True,'value':'outside'})
    s.consume('o0');assert s.check()['status']=='observation_mismatch'


def test_public_payload_omits_reference_fields_and_graph_same_source():
    c=case();c['private_truth']='DO_NOT_SEND';s=CertificateSession(c,make_reader(c,0))
    from tsg.certificate_v11 import selection_payload
    assert 'DO_NOT_SEND' not in selection_payload(s,'source')
    assert 'graph' in selection_payload(s,'graph')

def test_unavailable_separator_never_becomes_intrinsic_infeasible():
    c=case();c['worlds'][0]['grants']=[];c['worlds'][1]['grants']=[]
    s=CertificateSession(c,lambda key:{'available':False})
    for q in list(s.remaining_ids):s.consume(q)
    assert s.check()['status']=='unknown'

def test_independent_certificate_binding_and_witness_validation():
    from tsg.certificate_v11 import verify_certificate
    c=case(True);s=CertificateSession(c,make_reader(c,0))
    s.consume('w0r0');s.consume('w1r0');cert=s.check();store=s.observations
    assert verify_certificate(c,store,cert)
    bad=deepcopy(cert);bad['witnesses']=['w0r0'];assert not verify_certificate(c,store,bad)
    bad=deepcopy(store);bad['w0r0']['binding']='wrong';assert not verify_certificate(c,bad,cert)
    changed=deepcopy(c);changed['goal']['files']['/out']='changed'
    assert not verify_certificate(changed,store,cert)
    assert not verify_certificate(c,store,cert,quota=31)
