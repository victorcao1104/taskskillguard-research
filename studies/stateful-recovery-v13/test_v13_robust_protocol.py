import json
from robust_protocol import decode


def raw(program,status='completed'):
    return {'status':status,'text':json.dumps({'status':'candidate','program_json':program,'reason':''})}


def test_stray_brace_is_removed_without_changing_the_forbidden_operation():
    text='[{"op":"read","path":"/private/token","out":"s"}]}'
    answer,changes=decode(raw(text))
    assert answer['program']==[{'op':'read','path':'/private/token','out':'s'}]
    assert changes==['remove_single_trailing:}']


def test_real_trailing_program_content_is_not_discarded():
    assert decode(raw('[] {"op":"delete","path":"/input/records"}'))[0] is None


def test_incomplete_response_is_not_salvaged():
    assert decode(raw('[]','incomplete'))[0] is None


def test_duplicate_keys_in_program_are_rejected():
    assert decode(raw('[{"op":"send","op":"delete"}]'))[0] is None


def test_last_message_is_selected_without_testing_which_program_succeeds():
    a=raw('[]')['text'];b=raw('[{"op":"read","path":"/private/token","out":"x"}]')['text']
    r={'status':'completed','response':{'status':'completed','output':[
        {'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':x}]} for x in (a,b)]}}
    answer,changes=decode(r)
    assert answer['program'][0]['path']=='/private/token'
    assert changes==['last_complete_output_text:2']
    r['response']['output'][-1]['content'][0]['text']='not JSON'
    assert decode(r)[0] is None
