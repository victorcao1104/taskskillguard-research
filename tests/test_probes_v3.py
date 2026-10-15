import importlib.util


def test_body_and_taint_have_separate_reachable_positive_controls():
    assert importlib.util.find_spec('tsg.component_probes_v3') is not None, 'component probes not implemented'
    from tsg.component_probes_v3 import run_probes
    rows = {(r['probe'],r['variant']):r['result'] for r in run_probes()}
    assert len(rows) == 6
    assert not rows['public_wrong_body','full']['unauthorized_executed']
    assert rows['public_wrong_body','no_body']['unauthorized_executed']
    assert not rows['public_wrong_body','no_taint']['unauthorized_executed']
    assert not rows['confidential_same_literal','full']['secret_leaked']
    assert rows['confidential_same_literal','no_taint']['secret_leaked']
    assert not rows['confidential_same_literal','no_body']['secret_leaked']
