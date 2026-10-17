"""Shared outcome-blind transport normalization, never a semantic program repair."""
from copy import deepcopy
import json
from sr13.campaign import Provider,validate_record
from sr13.protocol import SCHEMA,parse
from tsg.models_v3 import _unique_object,_reject_constant
from sr13.io import read


def decode(raw):
    validation=validate_record(raw,SCHEMA);changes=[]
    if not validation['protocol_valid']:
        if set(validation['diagnostic_codes'])!={'MULTIPLE_OUTPUT_TEXT'}:
            return None,changes
        # No refusal, incomplete output or malformed envelope is allowed through.
        texts=[c['text'] for item in raw['response']['output'] if item.get('type')=='message'
               for c in item['content'] if c.get('type')=='output_text']
        normalized=deepcopy(raw)
        normalized['response']['output']=[{'type':'message','role':'assistant','status':'completed',
                                          'content':[{'type':'output_text','text':texts[-1]}]}]
        validation=validate_record(normalized,SCHEMA)
        changes.append('last_complete_output_text:'+str(len(texts)))
        if not validation['protocol_valid']:return None,changes
    obj=deepcopy(validation['prediction'])
    if obj['status']!='candidate':return parse(obj),changes
    source=obj['program_json'].strip()
    try:
        program,end=json.JSONDecoder(object_pairs_hook=_unique_object,parse_constant=_reject_constant).raw_decode(source)
        suffix=source[end:].strip()
        # A complete array followed only by one stray punctuation mark is unambiguous.
        if not isinstance(program,list) or suffix not in {'','}',','}:return None,changes
        if suffix:changes.append('remove_single_trailing:'+suffix)
        obj['program_json']=json.dumps(program,ensure_ascii=False)
        answer=parse(obj)
        return (answer if answer['status']!='invalid' else None),changes
    except (ValueError,TypeError,RecursionError):return None,changes


class NormalizedProvider(Provider):
    def propose(self,*args,**kwargs):
        answer=super().propose(*args,**kwargs)
        if not answer.get('request'):return answer
        raw=read(self.api/'raw'/f"{answer['request']['hash']}.json")
        normalized,changes=decode(raw)
        request={**answer['request'],'transport_normalization':changes}
        if normalized is None:
            return {'status':'invalid','program':None,'reason':'NORMALIZED_PROTOCOL_REJECTED','request':request}
        return {**normalized,'request':request}
