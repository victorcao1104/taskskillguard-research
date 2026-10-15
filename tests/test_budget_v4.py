import json
import pytest
from tsg.budget_v4 import BudgetV4, corrected_prefix


def test_legacy_correction_preserves_original_bytes_and_is_conservative():
    old = [{'reservation_id': 'a', 'model': 'gpt-6-luna', 'status': 'settled',
            'reserved_usd': 2, 'cost_usd': .6, 'usage': {'input_tokens': 1000000, 'output_tokens': 1000000}},
           {'reservation_id': 'b', 'model': 'gpt-6-luna', 'status': 'reserved', 'reserved_usd': 1}]
    data = ''.join(json.dumps(r)+'\n' for r in old).encode()
    prefix, audit = corrected_prefix(data)
    assert prefix.startswith(data)
    assert audit['corrected_exposure_upper_usd'] == pytest.approx(1.875)
    assert audit['correction_usd'] == pytest.approx(.275)


def test_luna_reservation_uses_cache_write_upper_rate(tmp_path):
    budget = BudgetV4(tmp_path/'ledger.jsonl', .07)
    rid = budget.reserve('gpt-6-luna', 100000, 100000)
    assert budget.total_cost == pytest.approx(.0625)
    with pytest.raises(RuntimeError, match='BUDGET_LIMIT'):
        budget.reserve('gpt-6-luna', 100000, 0)
    budget.settle(rid, {'input_tokens': 100000, 'output_tokens': 100000})
    assert budget.total_cost == pytest.approx(.0625)


def test_invalid_usage_never_releases_reservation(tmp_path):
    budget = BudgetV4(tmp_path/'ledger.jsonl', 20)
    rid = budget.reserve('gpt-4.1-mini', 2000, 1000)
    before = budget.total_cost
    budget.settle(rid, {})
    assert budget.total_cost == before


def test_reject_long_context_and_invalid_counts(tmp_path):
    budget = BudgetV4(tmp_path/'ledger.jsonl', 20)
    with pytest.raises(ValueError):
        budget.reserve('gpt-6-luna', 272001, 1)
    with pytest.raises(ValueError):
        budget.reserve('gpt-4.1-mini', -1, 1)
