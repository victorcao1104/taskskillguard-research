"""Posthoc measurement validation of saved Phase 11 actual-execution traces.

Independent of production modules and self-reported safety counters. This is a
recorded-trace audit, not a new prespecified endpoint or a real-world attack rate.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('semantics', 'policies', 'recovery', 'integrated')
EFFECT_CHARGED = frozenset(('receipt', 'ambiguous_outcome', 'grant_denied', 'receipt_conflict',
                            'fenced_operation', 'pending', 'invalid_receipt'))
EFFECT_UNCHARGED = frozenset(('receipt_reused', 'quota_exhausted'))
STATUS_UNCHARGED = frozenset(('status_budget_exhausted', 'quota_exhausted'))
OPS = frozenset(('read', 'write', 'delete', 'emit'))
LIMITATIONS = [
    'Posthoc validation of dependent saved execution rows; not an independent heldout experiment, prespecified endpoint, or measured real-world attack rate.',
    'Authorization is recomputed directly from each committed event signature and the frozen actual-world grants; self-reported unauthorized_effects is not trusted.',
    'Environment traces contain committed events only. Completeness/authenticity of those logs is an assumption; unlogged operations or real backend behavior cannot be ruled out.',
    'Environment events omit logical keys. Keys are linked to recorded controller keys using the documented SHA-256 operation-ID binding over epoch, route, logical key and bounded retry generation; unmapped keys remain unknown.',
    'Operation IDs are identifiers, not authentication. This audit does not authenticate status MACs or prove atomicity, durability, fencing, snapshot immutability, or receipt truthfulness.',
    'Rejected/deduplicated dispatches and status requests are absent from environment_trace. Exact call counts are reconstructed conditionally from controller_trace/status_log outcome semantics, not independently observed at a service boundary.',
    'A returned status packet counts as one charged status call even if its content is unusable. Explicit quota/status-budget rejection counts as uncharged. Unknown/missing trace statuses produce unknown counts.',
    'Final files/emits are replayed from recorded commit signatures without interpreting programs. Agreement does not establish trace completeness when omitted events leave the same state.',
    'Read commits are included in authorization checks but excluded from logical mutation-duplicate counts, matching the stated mutation contract.',
    'Null executions are retained and have no observed safety or charge denominator; expanded rows are not independent samples.'
]


def _stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _jb(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def _rb(rows):
    return ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True, allow_nan=False)+'\n' for r in rows).encode()


@lru_cache(maxsize=262144)
def _operation_id(epoch, route, encoded_key, generation):
    return _sha(_stable([epoch, route, json.loads(encoded_key), generation]).encode())


def _sig(value):
    return isinstance(value, list) and len(value) == 3 and all(isinstance(v, str) for v in value)


def audit_execution(world, result, quota=32, status_budget=1):
    """Pure trace reconstruction; never calls a VM or trusts reported counters."""
    fields = ('observed_committed_events', 'observed_mutation_commits', 'observed_unauthorized_commits',
              'observed_unauthorized_mutation_commits', 'observed_duplicate_logical_mutations',
              'observed_duplicate_mutation_operation_ids', 'duplicate_logical_mutations_lower_bound',
              'unauthorized_commits_lower_bound', 'unmapped_mutation_commits',
              'observed_binding_signature_mismatches', 'malformed_environment_events',
              'malformed_controller_events', 'unknown_controller_statuses', 'unknown_status_log_entries',
              'controller_unauthorized_dispatch_attempts', 'reconstructed_effect_calls',
              'reconstructed_status_calls', 'reconstructed_charged_calls', 'quota_violation',
              'status_budget_violation', 'replayed_files_equal', 'replayed_emits_equal')
    if result is None:
        return {'audit_status': 'null_execution', **dict.fromkeys(fields),
                'unauthorized_commit_event_indices': [], 'self_reported_mismatches': [],
                'missing_traces': [], 'quota': quota, 'status_budget': status_budget}
    if not isinstance(result, dict):
        raise ValueError('EXECUTION_MUST_BE_OBJECT_OR_NULL')
    if not isinstance(world.get('files'), dict) or not isinstance(world.get('grants'), list):
        raise ValueError('WORLD_FILES_AND_GRANTS_REQUIRED')
    grants = {tuple(g) for g in world['grants']}
    missing = [name for name in ('environment_trace', 'controller_trace', 'status_log')
               if not isinstance(result.get(name), list)]
    environment = result.get('environment_trace') if 'environment_trace' not in missing else []
    controller = result.get('controller_trace') if 'controller_trace' not in missing else []
    status_log = result.get('status_log') if 'status_log' not in missing else []
    keys, controller_signatures = set(), defaultdict(set)
    malformed_controller = unknown_controller = effects = denied_attempts = 0
    for event in controller:
        if not isinstance(event, dict):
            malformed_controller += 1; unknown_controller += 1
            continue
        status = event.get('status')
        if status in EFFECT_CHARGED:
            effects += 1
        elif status not in EFFECT_UNCHARGED:
            unknown_controller += 1
        signature, key, route = event.get('signature'), event.get('key'), event.get('route_index')
        if (not _sig(signature) or not isinstance(key, list) or not key
                or type(route) is not int or route < 0):
            malformed_controller += 1
            continue
        encoded_key = _stable(key)
        keys.add((route, encoded_key))
        controller_signatures[(route, encoded_key)].add(_stable(signature))
        if status in EFFECT_CHARGED and tuple(signature[:2]) not in grants:
            denied_attempts += 1
    statuses, unknown_status = 0, 0
    for response in status_log:
        if isinstance(response, dict) and isinstance(response.get('status'), dict):
            statuses += 1
        elif not (isinstance(response, dict) and response.get('error') in STATUS_UNCHARGED):
            unknown_status += 1
    # Enumerate the bounded generation identities to link independently recorded
    # commit bindings to logical keys. No controller status licenses a commit.
    epochs = {event.get('binding', {}).get('epoch') for event in environment
              if isinstance(event, dict) and isinstance(event.get('binding'), dict)
              and isinstance(event['binding'].get('epoch'), str)}
    mapping = defaultdict(set)
    for epoch in epochs:
        for route, encoded_key in keys:
            for generation in range(len(controller)+1):
                mapping[_operation_id(epoch, route, encoded_key, generation)].add((route, encoded_key))
    commits = mutations = unauthorized = unauthorized_mutations = malformed = unmapped = signature_mismatch = 0
    logical_counts, operation_counts = Counter(), Counter()
    unauthorized_indices = []
    files, emits = deepcopy(world['files']), []
    for index, event in enumerate(environment):
        if not isinstance(event, dict) or type(event.get('committed')) is not bool:
            malformed += 1; continue
        if event['committed'] is False:
            continue
        commits += 1
        binding = event.get('binding')
        if not isinstance(binding, dict) or not _sig(binding.get('signature')):
            malformed += 1; continue
        op, resource, value = binding['signature']
        if (op, resource) not in grants:
            unauthorized += 1; unauthorized_indices.append(index)
            unauthorized_mutations += int(op != 'read')
        if op not in OPS:
            malformed += 1; continue
        if op == 'write':
            files[resource] = value
        elif op == 'delete':
            files.pop(resource, None)
        elif op == 'emit':
            emits.append({'resource': resource, 'value': value})
        operation = binding.get('operation_id')
        candidates = mapping.get(operation, set()) if isinstance(operation, str) else set()
        if candidates and not any(_stable(binding['signature']) in controller_signatures[p] for p in candidates):
            signature_mismatch += 1
        if op == 'read':
            continue
        mutations += 1
        if isinstance(operation, str):
            operation_counts[operation] += 1
        logical_keys = {encoded_key for _, encoded_key in candidates}
        if len(logical_keys) != 1:
            unmapped += 1
        else:
            logical_counts[next(iter(logical_keys))] += 1
    environment_complete = 'environment_trace' not in missing and malformed == 0
    effect_count = effects if 'controller_trace' not in missing and unknown_controller == 0 else None
    status_count = statuses if 'status_log' not in missing and unknown_status == 0 else None
    total = effect_count+status_count if effect_count is not None and status_count is not None else None
    duplicate_lower = sum(max(0, count-1) for count in logical_counts.values())
    duplicate = duplicate_lower if environment_complete and unmapped == 0 else None
    auth = unauthorized if environment_complete else None
    reconstructed = {'effect_calls': effect_count, 'status_calls': status_count, 'charged_calls': total,
                     'unauthorized_effects': auth, 'duplicate_effects': duplicate,
                     'remaining_quota': quota-total if total is not None else None,
                     'remaining_status_budget': status_budget-status_count if status_count is not None else None}
    mismatches = [field for field, value in reconstructed.items() if value is not None and result.get(field) != value]
    incomplete = bool(missing or malformed or malformed_controller or unknown_controller or unknown_status or unmapped)
    return {'audit_status': 'incomplete_trace' if incomplete else 'audited',
            'quota': quota, 'status_budget': status_budget, 'missing_traces': missing,
            'observed_committed_events': commits if 'environment_trace' not in missing else None,
            'observed_mutation_commits': mutations if environment_complete else None,
            'observed_unauthorized_commits': auth,
            'observed_unauthorized_mutation_commits': unauthorized_mutations if environment_complete else None,
            'unauthorized_commits_lower_bound': unauthorized if 'environment_trace' not in missing else None,
            'observed_duplicate_logical_mutations': duplicate,
            'duplicate_logical_mutations_lower_bound': duplicate_lower if 'environment_trace' not in missing else None,
            'observed_duplicate_mutation_operation_ids': sum(max(0, count-1) for count in operation_counts.values()) if environment_complete else None,
            'unmapped_mutation_commits': unmapped if 'environment_trace' not in missing else None,
            'observed_binding_signature_mismatches': signature_mismatch,
            'malformed_environment_events': malformed, 'malformed_controller_events': malformed_controller,
            'unknown_controller_statuses': unknown_controller, 'unknown_status_log_entries': unknown_status,
            'controller_unauthorized_dispatch_attempts': denied_attempts,
            'reconstructed_effect_calls': effect_count, 'reconstructed_status_calls': status_count,
            'reconstructed_charged_calls': total,
            'quota_violation': total > quota if total is not None else None,
            'status_budget_violation': status_count > status_budget if status_count is not None else None,
            'replayed_files_equal': files == result.get('files') if environment_complete else None,
            'replayed_emits_equal': emits == result.get('emits') if environment_complete else None,
            'unauthorized_commit_event_indices': unauthorized_indices,
            'self_reported_mismatches': sorted(mismatches)}


def _read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line]


def _read_chunks(directory):
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    rows = [row for i in range(1, manifest['chunks']+1) for row in _read_rows(directory/f'{i:04}.jsonl')]
    if len(rows) != manifest['rows'] or _sha(_rb(rows)) != manifest['sha256']:
        raise ValueError('INPUT_CHUNK_HASH_MISMATCH:'+str(directory))
    return rows


def _summarize(rows):
    actual = [r for r in rows if r['audit_status'] != 'null_execution']
    numeric_fields = ('observed_committed_events', 'observed_mutation_commits', 'observed_unauthorized_commits',
                      'observed_unauthorized_mutation_commits', 'observed_duplicate_logical_mutations',
                      'observed_duplicate_mutation_operation_ids', 'unmapped_mutation_commits',
                      'observed_binding_signature_mismatches', 'malformed_environment_events',
                      'malformed_controller_events', 'unknown_controller_statuses', 'unknown_status_log_entries',
                      'controller_unauthorized_dispatch_attempts', 'reconstructed_effect_calls',
                      'reconstructed_status_calls', 'reconstructed_charged_calls', 'quota_violation', 'status_budget_violation')
    return {'rows': len(rows), 'non_null_executions': len(actual), 'null_executions': len(rows)-len(actual),
            'audit_statuses': dict(sorted(Counter(r['audit_status'] for r in rows).items())),
            'totals': {field: sum(r[field] for r in actual if type(r[field]) in (int, bool)) for field in numeric_fields},
            'known_execution_denominators': {field: sum(r[field] is not None for r in actual) for field in numeric_fields},
            'self_reported_mismatch_rows': sum(bool(r['self_reported_mismatches']) for r in actual),
            'self_reported_mismatches_by_field': dict(sorted(Counter(k for r in actual for k in r['self_reported_mismatches']).items())),
            'replayed_files_mismatch_rows': sum(r['replayed_files_equal'] is False for r in actual),
            'replayed_emits_mismatch_rows': sum(r['replayed_emits_equal'] is False for r in actual)}


def audit(root=ROOT, publish=False):
    """Recompute {'summary', 'details'}; publish only with explicit publish=True."""
    root = Path(root)
    cases = {c['case_id']: c for name in ('heldout', 'challenge', 'scaling')
             for c in _read_rows(root/f'data/phase11/{name}.jsonl')}
    details = []
    inputs = {f'data/phase11/{name}.jsonl': _sha((root/f'data/phase11/{name}.jsonl').read_bytes())
              for name in ('heldout', 'challenge', 'scaling')}
    for source in SOURCES:
        directory = root/f'results/phase11/{source}'
        inputs[f'results/phase11/{source}/manifest.json'] = _sha((directory/'manifest.json').read_bytes())
        rows = _read_chunks(directory)
        for i, row in enumerate(rows):
            case = cases[row['case_id']]
            result = row.get('execution') if source in ('semantics', 'policies') else row.get('result')
            metadata = {k: row[k] for k in ('case_id', 'family', 'split', 'world_index', 'route',
                                           'policy', 'fault', 'budget', 'stop', 'model', 'view', 'stream_id') if k in row}
            details.append({**metadata, 'source': source, 'source_row_index': i,
                            **audit_execution(case['worlds'][row['world_index']], result,
                                              quota=32, status_budget=row.get('status_budget', 1))})
    summary = {'schema_version': 1, 'classification': 'posthoc recorded-trace measurement validation',
               'independent_of_production_imports': True, 'self_reported_counters_trusted': False,
               'limits': LIMITATIONS, 'inputs': dict(sorted(inputs.items())),
               'audit_source_sha256': _sha(Path(__file__).read_bytes()),
               'all_rows': _summarize(details),
               'by_source': {source: _summarize([r for r in details if r['source'] == source]) for source in SOURCES},
               'details_sha256': _sha(_rb(details))}
    if publish:
        directory = root/'results/phase11/trace_audit'
        outputs = {'summary.json': _jb(summary)}
        size = 500
        for index, start in enumerate(range(0, len(details), size), 1):
            outputs[f'detail/{index:04}.jsonl'] = _rb(details[start:start+size])
        outputs['detail/manifest.json'] = _jb({'rows': len(details), 'chunks': (len(details)+size-1)//size,
                                              'chunk_size': size, 'sha256': summary['details_sha256']})
        for name, data in outputs.items():
            path = directory/name
            if path.exists() and path.read_bytes() != data:
                raise ValueError('IMMUTABLE_TRACE_AUDIT_MISMATCH:'+name)
        for name, data in sorted(outputs.items()):
            path = directory/name; path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(data)
    return {'summary': summary, 'details': details}


if __name__ == '__main__':
    print(json.dumps(audit(publish=True)['summary'], sort_keys=True), flush=True)
