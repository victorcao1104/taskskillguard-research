import copy
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_phase5 import price_job
from verify_phase5_release import verify_job
from tsg.models import make_request
from tsg.reasoning_v5 import schema,parse_record,AXES

def saved():
    job=price_job({'job_id':'one','model':'gpt-4.1-mini','system':'s','prompt':'p',
                  'max_output':3000,'replicate':0,'schema':schema(['c1']),'ids':['c1']})
    request=make_request(job['model'],'s','p',3000)
    request['text']['format']={'type':'json_schema','name':'tsg_response_v3','strict':True,'schema':job['schema']}
    raw={'request':request,'request_hash':job['expected_request_hash'],'replicate':0,'status':'completed',
         'text':json.dumps({'judgments':[{'candidate_id':'c1',**dict.fromkeys(AXES,'yes'),'reason':'r','unknowns':[]}]})}
    observation={'request_hash':raw['request_hash'],'parsed':parse_record(raw,['c1'])}
    return job,observation,raw

def test_reparse_catches_wrapper_truth_tampering():
    job,obs,raw=saved(); assert verify_job(job,obs,raw)
    obs['parsed']['judgments'][0]['authorized']='no'
    with pytest.raises(ValueError,match='PARSED'): verify_job(job,obs,raw)

def test_raw_request_rehash_catches_metadata_only_consistency():
    job,obs,raw=saved(); raw['request']['input'][1]['content']='changed prompt'
    with pytest.raises(ValueError,match='RAW_REQUEST'): verify_job(job,obs,raw)
