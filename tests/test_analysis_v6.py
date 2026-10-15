from tsg.analysis_v6 import paired_interval, label_counts


def test_family_balance_not_condition_pseudoreplication():
    rows=[{'family':'many','difference':1.0} for _ in range(100)]+[{'family':'one','difference':-1.0}]
    result=paired_interval(rows,draws=100)
    assert result['families']==2
    assert result['estimate']==0
    assert result['conditions']==101


def test_unknown_and_protocol_missing_are_distinct():
    rows=[('unknown','yes'),('unknown','unknown'),('unknown',None),('yes','unknown'),('yes','yes')]
    result=label_counts(rows)
    assert result['correct']==2 and result['total']==5
    assert result['gold_unknown']==3 and result['unsupported_decision']==1
    assert result['missing']==1 and result['false_unknown']==1
