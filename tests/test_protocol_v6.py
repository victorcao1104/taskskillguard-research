import json
import pytest

from tsg.protocol_v6 import parse_record, payloads, allowed_ids


def test_missing_duplicate_and_incomplete_fail_closed():
    one={'id':'x','authorization':'yes','implementation':'no','task':'unknown'}
    for judgments in [[],[one,one]]:
        row=parse_record({'status':'completed','text':json.dumps({'judgments':judgments})},['x'])
        assert not row['protocol_valid']
        assert allowed_ids(row)==[]
    row=parse_record({'status':'incomplete','text':json.dumps({'judgments':[one]})},['x'])
    assert not row['protocol_valid']


def test_necessity_never_grants_authority():
    js=[{'id':'x','authorization':'unknown','implementation':'yes','task':'yes'},
        {'id':'y','authorization':'no','implementation':'yes','task':'yes'},
        {'id':'z','authorization':'yes','implementation':'no','task':'no'}]
    row=parse_record({'status':'completed','text':json.dumps({'judgments':js})},['x','y','z'])
    assert row['protocol_valid']
    assert allowed_ids(row)==['z']


def test_views_equal_base_and_private_answers_absent():
    tiktoken=pytest.importorskip('tiktoken')
    case={'source':'source','program':{'PRIVATE':'secret'},'routes':[],
          'worlds':[{'files':{},'grants':[]}],'goal':{},'catalog_closed':True,
          'truth':{'PRIVATE':'secret'},'case_id':'revealing_name'}
    nodes=[{'id':'a','op':'read'},{'id':'b','op':'write'}]
    es=[{'source':'a','target':'b','type':'DATA'}]
    views=payloads(case,nodes,es)
    bases=[]
    for v,s in views.items():
        assert 'secret' not in s and 'revealing_name' not in s
        p=json.loads(s);p.pop('attachment',None);bases.append(p)
    assert all(p==bases[0] for p in bases)
    enc=tiktoken.get_encoding('o200k_base')
    assert len(enc.encode(views['graph']))==len(enc.encode(views['padding']))
    assert views['graph']!=views['shuffled']
    triples=payloads(case,nodes,[('a','b','DATA')])
    assert triples==views
