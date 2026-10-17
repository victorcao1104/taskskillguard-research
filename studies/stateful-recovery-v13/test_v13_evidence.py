import pytest
from sr13.io import save,read
from sr13.campaign import request_job
from sr13.data import make_case,make_inputs
from sr13.methods import offline_trial


def test_evidence_cannot_be_silently_replaced(tmp_path):
    p=tmp_path/'evidence.json';save(p,{'value':1});save(p,{'value':1})
    with pytest.raises(ValueError,match='IMMUTABLE'):save(p,{'value':2})
    assert read(p)=={'value':1}


def test_request_cap_rejects_before_paid_dispatch():
    with pytest.raises(ValueError,match='INPUT_BYTE_CAP'):
        request_job('gpt-4.1-mini','a'*19000,method='repair',case_id='x',replicate=0,iteration=0)


def test_catalogue_is_a_separate_explicit_answer():
    c=make_case('dev_sum','unused_forbidden');inp=[make_inputs(c,101)]
    with pytest.raises(ValueError,match='PREPARED_CATALOGUE_REQUIRED'):
        offline_trial('catalogue_oracle',c,inp,inp)
    p=offline_trial('goal_direct',c,inp,inp)['deployed_program']
    assert offline_trial('catalogue_oracle',c,inp,inp,catalogue_program=p)['evaluation']['safe_complete']
