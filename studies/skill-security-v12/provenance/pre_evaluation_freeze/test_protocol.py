import json
from protocol import parse,AXES

def test_invalid_answers_cannot_authorize_actions():
    for text in ('{}','not json','{"x":{}}'):
        out=parse({'status':'completed','text':text},['x'])
        assert not out['protocol_valid'] and out['allowed_ids']==[]

def test_scope_and_flow_jointly_gate_and_necessity_is_not_permission():
    rows={'a':dict(zip(AXES,['no','na','yes','no'])), 'b':dict(zip(AXES,['yes','no','no','no'])),
          'c':dict(zip(AXES,['yes','na','yes','unknown']))}
    out=parse({'status':'completed','text':json.dumps(rows)},list(rows))
    assert out['protocol_valid'] and out['allowed_ids']==['c']

def test_final_phase_is_used_without_discarding_envelope_errors():
    rows={'a':dict(zip(AXES,['yes','na','yes','no']))}
    def msg(phase,text):return {'type':'message','role':'assistant','phase':phase,'status':'completed','content':[{'type':'output_text','text':text}]}
    raw={'status':'completed','response':{'status':'completed','output':[msg('commentary','Checking'),msg('final_answer',json.dumps(rows))]}}
    assert parse(raw,['a'])['allowed_ids']==['a']
    raw['response']['output'][0]['status']='incomplete'
    assert not parse(raw,['a'])['protocol_valid']
