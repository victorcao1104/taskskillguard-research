import importlib.util


def test_new_transformations_have_independent_literal_oracles():
    assert importlib.util.find_spec('tsg.benchmark_v3') is not None, 'new benchmark is not implemented'
    from tsg.benchmark_v3 import FIXTURES, transform_v3
    assert len(FIXTURES) == 16
    for kind, examples in FIXTURES.items():
        assert len(examples) == 2
        for text, expected in examples:
            assert transform_v3(kind, text) == expected, kind


def test_new_cases_split_by_family_and_preserve_attack_effects():
    from tsg.benchmark_v3 import build_cases_v3
    cases = build_cases_v3()
    assert len(cases) == 256
    assert len({c['case_id'] for c in cases}) == 256
    for split, count in [('development', 4), ('validation', 4), ('held_out_test', 8)]:
        assert len({c['family_id'] for c in cases if c['split'] == split}) == count
    assert all(c['benchmark_origin'] == 'new_finite_transform_family' for c in cases)
    for c in cases:
        assert c['input_path'].endswith(c['task_kind'] + '-' + str(c['fixture_index']) + '.txt')
        assert c['task_kind'] in c['trusted_prompt']
        if c['scenario'] == 'artificial_dependency':
            assert any(a.get('requires') == 'token' for a in c['actions'])
        if c['scenario'] in ('derived_summary', 'data_flow_misuse'):
            assert c['confidential'] and c['require_send']


def test_transform_invalid_input_is_not_reported_as_success():
    import pytest
    from tsg.benchmark_v3 import transform_v3
    with pytest.raises(ValueError):
        transform_v3('json_inventory', 'not JSON')
    with pytest.raises(ValueError):
        transform_v3('invented', 'hello')
