import pytest
from analyze import request_cost,bootstrap
from reproduce import compare


def test_interrupted_response_cost_is_not_dropped():
    assert request_cost({'status':'interrupted_unknown'},{},{'reservation_upper_usd':.01})==.01
    with pytest.raises(ValueError,match='UNACCOUNTED_REQUEST'):
        request_cost({'status':'ok'},{},{'reservation_upper_usd':.01})


def test_settled_cost_and_family_weighting():
    assert request_cost({'reservation_id':'a'},{'a':{'cost_usd':.002,'reserved_usd':.01}}, {})==.002
    result=bootstrap({'a':[1]*100,'b':[-1]})
    assert result['difference']==0 and result['clusters']==2


def test_replay_rejects_missing_original_and_extra_record(tmp_path):
    original=tmp_path/'original';replay=tmp_path/'replay';original.mkdir();replay.mkdir()
    (replay/'task--method.json').write_text('{}')
    result=compare(original,replay)
    assert 'EMPTY_ORIGINAL_CAMPAIGN' in result['mismatches']
    assert 'task--method.json' in result['mismatches']
