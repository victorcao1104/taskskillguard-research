"""No outcome masking: precise optional dependency boundary and strict job guard."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('artifact_dependency_policy', ROOT / 'conftest.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def test_installed_dependency_never_skips_an_assertion():
    assert policy.dependency_skips(policy.TOKEN_TESTS, installed=True, required=False) == set()
    assert policy.dependency_skips(policy.TOKEN_TESTS, installed=True, required=True) == set()


def test_missing_optional_dependency_skips_only_exact_node_ids():
    unrelated = 'tests/test_acquisition_v11.py::test_distinct_stream_ids_and_replications'
    near_miss = next(iter(policy.TOKEN_TESTS)) + '_different'
    nodes = [*policy.TOKEN_TESTS, unrelated, near_miss]
    assert policy.dependency_skips(nodes, installed=False, required=False) == set(policy.TOKEN_TESTS)
    assert len(policy.TOKEN_TESTS) == 3


def test_required_dependency_is_an_error_not_a_skip():
    with pytest.raises(RuntimeError, match='REQUIRED_TOKENIZER_MISSING'):
        policy.dependency_skips(policy.TOKEN_TESTS, installed=False, required=True)


def test_installed_broken_dependency_is_not_silently_skipped(monkeypatch):
    class Config:
        def getoption(self, name):
            return False
    def broken_package(name):
        raise ImportError('broken installed package metadata')
    monkeypatch.setattr(policy.importlib.util, 'find_spec', broken_package)
    with pytest.raises(ImportError, match='broken installed package'):
        policy.pytest_collection_modifyitems(Config(), [])


def test_amendment_manifest_covers_policy_and_tests():
    import json
    manifest = json.loads((ROOT / 'amendments/phase11-ci-portability/manifest.json').read_text())
    assert {'conftest.py', 'tests/test_optional_dependency_policy.py'} <= set(manifest['files'])
    policy.verify_amendment()
