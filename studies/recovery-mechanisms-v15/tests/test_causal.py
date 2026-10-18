from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from causal_v14 import remove_relations

def test_only_inactive_subscript_spans_change():
    s="x = rows[0]['requires']\ny = rows[0]['value']\n# keep this comment\n"
    out,edits=remove_relations(s,{'closed_dependencies':False,'no_conflicts':False},['requires'])
    assert out=="x = []\ny = rows[0]['value']\n# keep this comment\n"
    assert len(edits)==1 and edits[0]['before']=="rows[0]['requires']"

def test_active_constraint_cannot_be_removed():
    import pytest
    with pytest.raises(ValueError,match='ACTIVE'):
        remove_relations("x=r['requires']",{'closed_dependencies':True},['requires'])

def test_sham_preserves_bytes():
    s="x = 1\n"
    assert remove_relations(s,{},[])[0]==s
