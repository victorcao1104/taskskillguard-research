"""Offline posthoc extraction diagnostic. Historical streams remain untouched."""
from collections import Counter
import json
import sys
from phase11_common import ROOT, jb, rb, sha, immutable
sys.path.insert(0, str(ROOT / 'src'))
from tsg.protocol_v11 import parse_selection_v11
from tsg.query_v10 import parse_selection


def reaudit():
    rows = []
    for p in sorted((ROOT / 'results/phase10/api/decisions').glob('*.json')):
        saved = json.loads(p.read_text(encoding='utf-8'))
        job = json.loads((ROOT / 'results/phase10/api/requests' / p.name).read_text(encoding='utf-8'))
        raw_path = ROOT / saved['raw_ref']
        raw = json.loads(raw_path.read_text(encoding='utf-8'))
        old = parse_selection(raw, job['remaining_ids'], job['protocol'], job['limit'])
        assert old == saved['parsed'], 'HISTORICAL_PARSER_REPLAY_DIFFERS'
        new = parse_selection_v11(raw, job['remaining_ids'], job['protocol'], job['limit'])
        rows.append({'job_id': job['job_id'], 'model': job['model'], 'cell': job['cell'],
            'raw_ref': saved['raw_ref'], 'raw_sha256': sha(raw_path.read_bytes()),
            'old_valid': old['protocol_valid'], 'new_valid': new['protocol_valid'],
            'old_diagnostics': old['diagnostics'], 'new_diagnostics': new['diagnostics'],
            'phase_selection': new['phase_selection'],
            'new_selected_ids': new['selected_ids'],
            'interpretation': 'extraction diagnostic only; no missing adaptive continuation inferred'})
    summary = {'decisions': len(rows), 'old_valid': sum(r['old_valid'] for r in rows),
        'new_valid': sum(r['new_valid'] for r in rows),
        'newly_accepted': sum(not r['old_valid'] and r['new_valid'] for r in rows),
        'newly_rejected': sum(r['old_valid'] and not r['new_valid'] for r in rows),
        'recovered_streams': 0, 'additional_provider_requests': 0,
        'newly_accepted_old_diagnostics': dict(Counter(c for r in rows
            if not r['old_valid'] and r['new_valid'] for c in r['old_diagnostics'])),
        'scope': 'posthoc diagnostic; frozen Phase10 metrics and results are unchanged'}
    immutable(ROOT / 'results/phase11/protocol_reaudit/decisions.jsonl', rb(rows))
    immutable(ROOT / 'results/phase11/protocol_reaudit/summary.json', jb(summary))
    return summary


if __name__ == '__main__':
    print(json.dumps(reaudit()))
