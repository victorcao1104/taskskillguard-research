"""Append-only optional-dependency policy for historical CI environments.

The scientific Phase 11 job must run with tiktoken. Older frozen jobs install
only their historical requirements and explicitly skip three dependent tests.
No test assertion, production function, or recorded evidence is replaced.
"""
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent
TOKEN_TESTS = frozenset({
    'tests/test_acquisition_v11.py::test_online_actual_dispatch_stops_before_next_request',
    'tests/test_acquisition_v11.py::test_failure_retains_paid_prefix_no_fallback',
    'tests/test_acquisition_v11.py::test_surrogate_token_matched_padding',
})
PHASE11_WORKFLOW = 'Phase eleven executable evidence contract'


def dependency_skips(node_ids, *, installed, required):
    if not installed and required:
        raise RuntimeError('REQUIRED_TOKENIZER_MISSING: install configs/phase5-requirements.txt')
    return set() if installed else set(node_ids) & TOKEN_TESTS


def verify_amendment(root=ROOT):
    root = Path(root)
    manifest = json.loads((root / 'amendments/phase11-ci-portability/manifest.json').read_text(encoding='utf-8'))
    for path, digest in manifest['files'].items():
        if sha256((root / path).read_bytes()).hexdigest() != digest:
            raise RuntimeError('AMENDMENT_HASH_CHANGED:' + path)
    if sha256((root / 'results/phase11/provenance/release_hashes.json').read_bytes()).hexdigest() != manifest['original_release_manifest_sha256']:
        raise RuntimeError('ORIGINAL_PHASE11_RELEASE_MANIFEST_CHANGED')


def pytest_addoption(parser):
    parser.addoption('--require-tokenizer', action='store_true',
                     help='Require the full Phase11 tokenizer dependency; never skip its tests.')


def pytest_sessionstart(session):
    verify_amendment()


def pytest_collection_modifyitems(config, items):
    installed = importlib.util.find_spec('tiktoken') is not None
    required = config.getoption('--require-tokenizer') or os.environ.get('GITHUB_WORKFLOW') == PHASE11_WORKFLOW
    try:
        skipped = dependency_skips((item.nodeid for item in items), installed=installed, required=required)
    except RuntimeError as exc:
        raise pytest.UsageError(str(exc)) from exc
    for item in items:
        if item.nodeid in skipped:
            item.add_marker(pytest.mark.skip(reason='Optional tiktoken absent in historical CI; dedicated Phase11 job requires and runs this test. See amendments/phase11-ci-portability/README.md.'))
