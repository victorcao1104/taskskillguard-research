"""Portable first-pass evidence fixtures; never regenerate truth in tests."""
from pathlib import Path
import importlib.util


def pytest_sessionstart(session):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('hydrate_phase11', root / 'scripts/hydrate_phase11.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.hydrate(root)
