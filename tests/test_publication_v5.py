from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publish_phase5 import audit_requests, decompose_pairs


def test_cache_usage_counts_physical_request_once():
    parsed = {'protocol_valid': True}
    observations = [{'request_hash': 'h', 'parsed': parsed, 'job_id': j, 'case_id': 'q'}
                    for j in ('auto', 'oracle')]
    raw = {'h': {'status': 'completed', 'usage': {'input_tokens': 10, 'output_tokens': 4, 'total_tokens': 14}}}
    audit = audit_requests(observations, raw)
    assert audit['unique_requests'] == 1
    assert audit['reused_condition_count'] == 1
    assert audit['provider_reported_unique_request_usage']['total_tokens'] == 14
    assert audit['condition_attributed_usage_not_actual_billing']['total_tokens'] == 28


def test_protocol_decomposition_keeps_failure_penalty_separate():
    rows = []
    for i in range(2):
        for v in ('table', 'auto', 'oracle', 'shuffled', 'length_control'):
            valid = v == 'table' or i == 0
            rows.append({'model': 'm', 'axis': 'task', 'case_id': 'q', 'context': 'allow',
                         'candidate_id': str(i), 'view': v, 'eligible': True, 'gold': 'yes',
                         'prediction': 'yes' if valid else None,
                         'protocol_status': 'valid' if valid else 'invalid'})
    result = decompose_pairs(rows)[0]
    assert result['planned_pairs'] == 2
    assert result['net_correct'] == -1
    assert result['strata']['both_valid']['net_correct'] == 0
    assert result['strata']['right_only_valid']['net_correct'] == -1
