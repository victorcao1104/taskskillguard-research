"""Explicit follow-up trials; default preparation makes no API calls or key reads."""
import argparse
import copy
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from tsg.models import Budget, PRICES, load_key, make_request
from tsg.models_v3 import ClientV3
from tsg.phase_protocol_v3 import ADAPTER_VERSION, normalized_phase_record
from tsg.real_v3 import parse_detection_record

MODELS = ('gpt-6-luna', 'gpt-4.1-mini')
EXPECTED_SKILLS = 180
EXPECTED_COUNTS = {'regression.jsonl': 528, 'new.jsonl': 1024, 'factorial.jsonl': 384,
                   'os_contracts.jsonl': 48, 'real.jsonl': 2160}
BUDGET_LIMIT = 20
FOLLOWUP_VERSION = 'phase3_real_followup_v1'


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def _rows_bytes(values):
    return ''.join(json.dumps(value, ensure_ascii=False) + '\n' for value in values).encode('utf-8')


def _fingerprint(request, replicate):
    return hashlib.sha256(json.dumps({'request': request, 'replicate': replicate},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _credit_error(raw):
    return (raw.get('status') == 'api_error' and raw.get('http_status') == 429
            and raw.get('error_code') == 'credit_balance_exhausted')


def _call_spec(raw, row, max_output):
    request = raw['request']
    messages = request.get('input')
    if (not isinstance(messages, list) or len(messages) != 2
            or [m.get('role') for m in messages] != ['developer', 'user']
            or any(not isinstance(m.get('content'), str) for m in messages)):
        raise ValueError('UNSUPPORTED_SAVED_REQUEST')
    schema = request.get('text', {}).get('format', {}).get('schema')
    if not isinstance(schema, dict) or request.get('model') != row['model']:
        raise ValueError('UNSUPPORTED_SAVED_REQUEST')
    original = make_request(row['model'], messages[0]['content'], messages[1]['content'],
                            request['max_output_tokens'])
    original['text']['format'] = {'type': 'json_schema', 'name': 'tsg_response_v3',
                                'strict': True, 'schema': copy.deepcopy(schema)}
    if original != request:
        raise ValueError('SAVED_REQUEST_RECONSTRUCTION_MISMATCH')
    revised = copy.deepcopy(original)
    revised['max_output_tokens'] = max_output
    replicate = raw.get('replicate', 0)
    if type(replicate) is not int or replicate < 0:
        raise ValueError('INVALID_SAVED_REPLICATE')
    return {'model': row['model'], 'system': messages[0]['content'], 'prompt': messages[1]['content'],
            'response_schema': schema, 'replicate': replicate, 'max_output': max_output}, revised


def _read_rows(data):
    return [json.loads(line) for line in data.decode('utf-8').splitlines() if line.strip()]


def _verify_sources(root, hashes):
    for name, digest in hashes.items():
        if _sha((root / name).read_bytes()) != digest:
            raise ValueError('PRIMARY_SOURCE_CHANGED: ' + name)


def _immutable_write(path, data, error):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(error)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)


def _prepare(root):
    sources = {}

    def read(name):
        data = (root / name).read_bytes()
        sources[name] = _sha(data)
        return data

    inputs = {}
    for name, expected in EXPECTED_COUNTS.items():
        inputs[name] = _read_rows(read('results/phase3/api/' + name))
        if len(inputs[name]) != expected:
            raise ValueError('INCOMPLETE_PRIMARY_ACQUISITION: ' + name)
    prepared_rows = _read_rows(read('data/phase3/real_prepared.jsonl'))
    prepared = {r['skill_id']: r for r in prepared_rows}
    if len(prepared) != EXPECTED_SKILLS or len(prepared_rows) != EXPECTED_SKILLS:
        raise ValueError('INCOMPLETE_PRIMARY_ACQUISITION: prepared skills')
    expected_jobs = {f'real-{p["skill_id"]}-{context}-{variant}-{model}':
        (p['skill_id'], context, variant, model)
        for p in prepared_rows for context in p['contexts'] for variant in ('raw', 'graph_v2') for model in MODELS}
    primary = inputs['real.jsonl']
    if (len(primary) != len(expected_jobs) or {r['job_id'] for r in primary} != set(expected_jobs)
            or any((r['skill_id'], r['context'], r['variant'], r['model']) != expected_jobs[r['job_id']]
                   for r in primary)):
        raise ValueError('PRIMARY_CONDITION_GRID_MISMATCH')
    trials, calls = [], {}
    for row in primary:
        # Eligibility is based on original failures, never on semantic labels or posthoc success.
        if row.get('status') != 'unresolved':
            continue
        digest = row.get('request_hash')
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('INVALID_ORIGINAL_REQUEST_HASH')
        raw_ref = 'results/phase3/api/raw/' + digest + '.json'
        raw = json.loads(read(raw_ref))
        if raw.get('request_hash') != digest or _fingerprint(raw.get('request'), raw.get('replicate', 0)) != digest:
            raise ValueError('REQUEST_HASH_MISMATCH')
        response = raw.get('response') or {}
        incomplete = response.get('incomplete_details') or {}
        truncation = (raw.get('status') == 'incomplete' and response.get('status') == 'incomplete'
                      and incomplete.get('reason') == 'max_output_tokens')
        if not _credit_error(raw) and not truncation:
            continue
        reason = 'max_output_tokens' if truncation else 'credit_balance_exhausted'
        original_cap = raw['request']['max_output_tokens']
        cap = 6000 if truncation else original_cap
        if truncation and original_cap >= cap:
            raise ValueError('TRUNCATION_CAP_NOT_INCREASED')
        spec, revised = _call_spec(raw, row, cap)
        trial_id = FOLLOWUP_VERSION + '-' + _sha((row['job_id'] + ':' + digest).encode())[:24]
        new_hash = _fingerprint(revised, spec['replicate'])
        ip, op = PRICES[row['model']]
        reservation = ((len(json.dumps(revised, ensure_ascii=False).encode()) + 4096) * ip + cap * op) / 1e6
        trial = {'trial_id': trial_id, 'original_job_id': row['job_id'], 'original_request_hash': digest,
            'original_raw_ref': raw_ref, 'original_raw_sha256': sources[raw_ref],
            'skill_id': row['skill_id'], 'model': row['model'], 'context': row['context'], 'variant': row['variant'],
            'split': prepared[row['skill_id']]['split'], 'selection_reason': reason,
            'original_status': row['status'], 'original_diagnostic_codes': row.get('diagnostic_codes', []),
            'original_max_output_tokens': original_cap, 'max_output_tokens': cap,
            'adaptive_output_cap': truncation, 'expected_request_hash': new_hash,
            'new_raw_ref': 'results/phase3_followup/api/raw/' + new_hash + '.json',
            'request_change': {'max_output_tokens': [original_cap, cap]} if truncation else {},
            'replicate': spec['replicate'], 'reservation_upper_usd': reservation,
            'trial_kind': 'new_followup_sample', 'phase_adapter': ADAPTER_VERSION}
        trials.append(trial)
        calls[trial_id] = spec
    # First probe an unchanged credit-failure request; adaptive sampling comes after balance validation.
    trials.sort(key=lambda t: (t['adaptive_output_cap'], t['original_job_id']))
    budget_bytes = read('results/phase3/api/budget.jsonl')
    if not budget_bytes.endswith(b'\n'):
        raise ValueError('INVALID_PRIMARY_BUDGET_TERMINATOR')
    ledger = {r['reservation_id']: r for r in _read_rows(budget_bytes)}
    original_cost = sum(r.get('cost_usd', r['reserved_usd']) for r in ledger.values())
    manifest = {'version': FOLLOWUP_VERSION, 'execution_status': 'prepared_pending_execution',
        'trial_kind': 'new_followup_samples_after_primary_acquisition',
        'primary_results_replaced': False, 'selection_basis': 'original_raw_external_failure_or_token_truncation',
        'planned_trials': len(trials), 'selected_skills': len({r['skill_id'] for r in trials}),
        'selection_counts': dict(Counter(r['selection_reason'] for r in trials)),
        'workers': 1, 'automatic_retries': 0, 'budget_limit_usd': BUDGET_LIMIT,
        'inherited_cumulative_cost_usd': original_cost, 'primary_budget_prefix_bytes': len(budget_bytes),
        'primary_budget_sha256': _sha(budget_bytes),
        'remaining_budget_usd': BUDGET_LIMIT - original_cost,
        'additional_reservation_upper_usd': sum(r['reservation_upper_usd'] for r in trials),
        'preserved_unknown_billing_reservations': sum(r['status'] != 'settled' for r in ledger.values()),
        'primary_status_counts': dict(Counter(r['status'] for r in primary)),
        'source_sha256': sources, 'pending_trials_sha256': _sha(_rows_bytes(trials)),
        'phase_adapter': ADAPTER_VERSION,
        'interpretation': 'Separate follow-up observations; primary results and semantic model unknowns remain unchanged.'}
    _verify_sources(root, sources)
    destination = root / 'results/phase3_followup'
    _immutable_write(destination / 'manifest.json', _json_bytes(manifest), 'FOLLOWUP_MANIFEST_MISMATCH')
    _immutable_write(destination / 'pending_trials.jsonl', _rows_bytes(trials), 'FOLLOWUP_TRIALS_MISMATCH')
    budget_path = destination / 'api/budget.jsonl'
    if budget_path.exists():
        if not budget_path.read_bytes().startswith(budget_bytes):
            raise ValueError('BUDGET_PREFIX_MISMATCH')
    else:
        _immutable_write(budget_path, budget_bytes, 'BUDGET_PREFIX_MISMATCH')
    return manifest, trials, calls, prepared


def _save(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(data)
    # Only repeat the local replacement; the paid request is outside this loop.
    for attempt in range(8):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(min(0.05 * 2 ** attempt, 1.0))


def _summary(manifest, trials, completed, budget, *, execute, calls, stop_reason):
    groups = []
    for model, context in sorted({(t['model'], t['context']) for t in trials}):
        planned = [t for t in trials if (t['model'], t['context']) == (model, context)]
        observed = [r for r in completed if (r['model'], r['context']) == (model, context)]
        groups.append({'model': model, 'context': context, 'planned': len(planned), 'observed': len(observed),
                       'valid': sum(r['status'] == 'valid' for r in observed),
                       'unresolved': sum(r['status'] == 'unresolved' for r in observed)})
    return {'version': FOLLOWUP_VERSION, 'mode': 'execute' if execute else 'dry_run',
        'planned_trials': len(trials), 'completed_trials': len(completed),
        'remaining_trials': len(trials) - len(completed), 'api_calls_this_run': calls,
        'workers': 1, 'automatic_retries': 0, 'stop_reason': stop_reason,
        'status_counts': dict(Counter(r['status'] for r in completed)), 'by_model_context': groups,
        'budget_limit_usd': BUDGET_LIMIT, 'cumulative_cost_usd': budget.total_cost,
        'inherited_cumulative_cost_usd': manifest['inherited_cumulative_cost_usd'],
        'followup_cost_usd': budget.total_cost - manifest['inherited_cumulative_cost_usd'],
        'remaining_budget_usd': BUDGET_LIMIT - budget.total_cost,
        'primary_files_modified': False, 'human_annotated': False,
        'raw_references': [{'trial_id': r['trial_id'], 'original_request_hash': r['original_request_hash'],
                            'request_hash': r['request_hash'], 'raw_ref': r['raw_ref']} for r in completed]}


def resume(root, *, execute=False, env_file=None, client_factory=ClientV3, key_loader=load_key):
    root = Path(root).resolve()
    if execute and (env_file is None or not Path(env_file).is_file()):
        raise ValueError('EXPLICIT_EXISTING_ENV_FILE_REQUIRED')
    manifest, trials, specs, prepared = _prepare(root)
    destination = root / 'results/phase3_followup'
    budget = Budget(destination / 'api/budget.jsonl', BUDGET_LIMIT)
    result_path = destination / 'api/real.jsonl'
    completed = _read_rows(result_path.read_bytes()) if result_path.exists() else []
    by_trial = {r['trial_id']: r for r in completed}
    if len(by_trial) != len(completed) or not set(by_trial).issubset({t['trial_id'] for t in trials}):
        raise ValueError('FOLLOWUP_RESULT_IDENTITY_MISMATCH')
    stop = next(('credit_balance_exhausted' for r in completed if r.get('error_code') == 'credit_balance_exhausted'), None)
    calls = 0
    lock_path = destination / '.execute.lock'
    lock = None
    try:
        if execute and not stop and len(completed) < len(trials):
            lock = lock_path.open('x', encoding='utf-8')
            lock.write('One sequential follow-up writer; no automatic retry.\n')
            lock.flush()
            _verify_sources(root, manifest['source_sha256'])
            client = None
            for trial in trials:
                if trial['trial_id'] in by_trial:
                    continue
                raw_path = root / trial['new_raw_ref']
                cached = raw_path.exists()
                if not cached and budget.total_cost + trial['reservation_upper_usd'] > BUDGET_LIMIT:
                    stop = 'BUDGET_LIMIT'
                    break
                if client is None:
                    client = client_factory(key_loader(env_file), destination / 'api/raw', budget)
                spec = specs[trial['trial_id']]
                raw = client.call(**spec, tag=trial['trial_id'])
                calls += not cached
                if raw.get('request_hash') != trial['expected_request_hash']:
                    raise ValueError('FOLLOWUP_REQUEST_HASH_MISMATCH')
                normalized = normalized_phase_record(raw, spec['response_schema'])
                result = parse_detection_record(normalized, prepared[trial['skill_id']], trial['context'],
                                                trial['variant'], model=trial['model'])
                result.update(trial_id=trial['trial_id'], job_id=trial['trial_id'],
                    original_job_id=trial['original_job_id'], original_request_hash=trial['original_request_hash'],
                    raw_ref=trial['new_raw_ref'], original_raw_ref=trial['original_raw_ref'],
                    trial_kind='new_followup_sample', selection_reason=trial['selection_reason'],
                    adaptive_output_cap=trial['adaptive_output_cap'], max_output_tokens=trial['max_output_tokens'],
                    phase_selection=normalized['phase_selection'], error_code=raw.get('error_code'))
                completed.append(result)
                by_trial[trial['trial_id']] = result
                _save(result_path, _rows_bytes(completed))
                _verify_sources(root, manifest['source_sha256'])
                if _credit_error(raw):
                    stop = 'credit_balance_exhausted'
                progress = _summary(manifest, trials, completed, budget, execute=execute, calls=calls, stop_reason=stop)
                _save(destination / 'summary.json', _json_bytes(progress))
                if stop:
                    break
    finally:
        if lock is not None:
            lock.close()
            lock_path.unlink()
    _verify_sources(root, manifest['source_sha256'])
    summary = _summary(manifest, trials, completed, budget, execute=execute, calls=calls, stop_reason=stop)
    _save(destination / ('summary.json' if execute else 'dry_run_summary.json'), _json_bytes(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--execute', action='store_true', help='Make explicitly authorized new follow-up API samples.')
    parser.add_argument('--env-file', type=Path, help='Existing approved environment file; used only with --execute.')
    args = parser.parse_args()
    print(json.dumps(resume(args.root, execute=args.execute, env_file=args.env_file), indent=2))


if __name__ == '__main__':
    main()
