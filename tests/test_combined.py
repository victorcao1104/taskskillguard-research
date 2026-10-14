import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_combined import overprivileged_label


def test_three_valued_overprivilege_does_not_hide_unknowns():
    assert overprivileged_label('unknown','no')=='yes'
    assert overprivileged_label('no','unknown')=='yes'
    assert overprivileged_label('yes','unknown')=='unknown'
    assert overprivileged_label('yes','yes')=='no'
