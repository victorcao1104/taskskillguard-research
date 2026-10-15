"""Conservative cache-write-aware budget; frozen historical ledger stays intact."""
import hashlib
import json
import uuid
from .models import Budget, utcnow

# Official model pages opened 2026-10-16. No discounts are credited.
# Luna uses highest short-context input rate (all tokens treated as cache writes).
UPPER_PRICES = {'gpt-6-luna': (.125, .50), 'gpt-4.1-mini': (.40, 1.60)}
PRICE_SOURCES = ['https://developers.openai.com/api/docs/models/gpt-6-luna',
                 'https://developers.openai.com/api/docs/models/gpt-4.1-mini']


def corrected_prefix(data):
    if not data.endswith(b'\n'):
        raise ValueError('INVALID_LEDGER_TERMINATOR')
    latest = {r['reservation_id']: r for r in map(json.loads, data.decode('utf-8').splitlines())}
    original = sum(r.get('cost_usd', r['reserved_usd']) for r in latest.values())
    additions = []
    for rid, old in latest.items():
        if old['model'] != 'gpt-6-luna':
            continue
        new = {**old, 'cost_basis': 'v4_conservative_cache_write_reconciliation',
               'prior_record_sha256': hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()}
        if old['status'] == 'settled':
            usage = old['usage']
            new['cost_usd'] = max(old['cost_usd'],
                (usage['input_tokens'] * .125 + usage['output_tokens'] * .50) / 1e6)
        else:
            # Unknown usage lacks the historical input/output split. Increasing
            # the entire reservation 25% safely includes the input surcharge.
            new['reserved_usd'] = old['reserved_usd'] * 1.25
        additions.append(new)
    combined = {**latest, **{r['reservation_id']: r for r in additions}}
    corrected = sum(r.get('cost_usd', r['reserved_usd']) for r in combined.values())
    return data + ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in additions).encode('utf-8'), {
        'original_exposure_usd': original, 'corrected_exposure_upper_usd': corrected,
        'correction_usd': corrected - original, 'adjusted_reservations': len(additions),
        'original_prefix_bytes': len(data), 'original_prefix_sha256': hashlib.sha256(data).hexdigest(),
        'sources': PRICE_SOURCES, 'basis': 'all Luna input at cache-write rate; no cache-hit discounts; unknown reservations uplifted25%',
        'is_provider_invoice': False}


class BudgetV4(Budget):
    def reserve(self, model, input_token_upper, output_max):
        if model not in UPPER_PRICES:
            raise ValueError('UNAUTHORIZED_MODEL')
        if any(type(n) is not int or n < 0 for n in (input_token_upper, output_max)):
            raise ValueError('INVALID_TOKEN_BOUND')
        if input_token_upper > 272000:
            raise ValueError('SHORT_CONTEXT_PRICE_BOUND_EXCEEDED')
        with self.lock:
            ip, op = UPPER_PRICES[model]
            amount = (input_token_upper * ip + output_max * op) / 1e6
            if self.total_cost + amount > self.limit:
                raise RuntimeError('BUDGET_LIMIT')
            rid = uuid.uuid4().hex
            self._write({'reservation_id': rid, 'timestamp': utcnow(), 'model': model,
                         'status': 'reserved', 'reserved_usd': amount,
                         'cost_basis': 'v4_all_input_at_max_short_context_rate'})
            return rid

    def settle(self, rid, usage):
        with self.lock:
            old = self.entries[rid]
            if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                                                  for k in ('input_tokens', 'output_tokens')):
                self._write({**old, 'status': 'unknown_usage'})
                return
            ip, op = UPPER_PRICES[old['model']]
            # Input bytes + headroom reservation should dominate token count.
            # An unexpected larger usage is retained, then stops future work.
            cost = (usage['input_tokens'] * ip + usage['output_tokens'] * op) / 1e6
            self._write({**old, 'status': 'settled', 'usage': usage, 'cost_usd': cost})
            if self.total_cost > self.limit:
                raise RuntimeError('USAGE_EXCEEDED_RESERVED_BOUND')


def initialize_campaign(root):
    """User revision: USD15 remaining from before any Phase4 paid request."""
    from pathlib import Path
    root = Path(root)
    old = (root/'results/phase3_followup/api/budget.jsonl').read_bytes()
    prefix, audit = corrected_prefix(old)
    audit.update({'authorization': '实验剩余上限改为15刀', 'authorized_date': '2026-10-16',
                  'phase4_calls_before_revision': 0, 'additional_budget_usd': 15,
                  'cumulative_cap_usd': audit['corrected_exposure_upper_usd'] + 15,
                  'supersedes': 'earlier cumulative USD20 limit'})
    manifest = root/'results/phase4/provenance/budget_revision.json'
    encoded = (json.dumps(audit, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    manifest.parent.mkdir(parents=True, exist_ok=True)
    if manifest.exists() and manifest.read_bytes() != encoded:
        raise ValueError('BUDGET_REVISION_MISMATCH')
    if not manifest.exists():
        manifest.write_bytes(encoded)
    ledger = root/'results/phase4/api/budget.jsonl'
    ledger.parent.mkdir(parents=True, exist_ok=True)
    if ledger.exists():
        if not ledger.read_bytes().startswith(prefix):
            raise ValueError('BUDGET_PREFIX_MISMATCH')
    else:
        ledger.write_bytes(prefix)
    return BudgetV4(ledger, audit['cumulative_cap_usd']), audit
