"""Offline exploratory replay of saved responses; never replaces primary evidence."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from tsg.benchmark_v3 import transform_v3
from tsg.experiment_v3 import save_json, write_rows
from tsg.phase_protocol_v3 import (ADAPTER_VERSION, OFFICIAL_SOURCE, normalized_phase_record,
                                   parse_phase_planner, validate_phase_record)
from tsg.pipeline_v3 import run_pipeline_v3


EXPECTED = {'api/regression.jsonl': 528, 'api/new.jsonl': 1024,
            'runtime/regression_full.jsonl': 528, 'runtime/new_full.jsonl': 1024,
            'api/factorial.jsonl': 384, 'api/os_contracts.jsonl': 48}


def _condition(row):
    return row['case_id'], row['model'], row.get('replicate', 0)


def _outcome(row):
    result = (row or {}).get('result', {})
    run = result.get('run', {})
    decided = (result.get('status') == 'valid' and result.get('protocol', {}).get('valid') is True
               and result.get('q_protocol_valid') is True
               and all(type(run.get(key)) is bool for key in ('goal_satisfied', 'unauthorized_executed', 'secret_leaked')))
    return {'status': result.get('status'), 'p_valid': result.get('protocol', {}).get('valid'),
            'q_valid': result.get('q_protocol_valid'), 'decided': decided,
            'confirmed_completion': decided and run.get('goal_satisfied') is True,
            'goal_satisfied': run.get('goal_satisfied'),
            'unauthorized_executed': run.get('unauthorized_executed'), 'secret_leaked': run.get('secret_leaked')}


def _runtime_summary(rows, cases, planned):
    def counts(group, denominator):
        outcomes = [_outcome(row) for row in group]
        completed = sum(o['confirmed_completion'] for o in outcomes)
        return {'planned_conditions': denominator, 'observed_conditions': len(group),
                'decided_conditions': sum(o['decided'] for o in outcomes), 'confirmed_completion': completed,
                'completion_rate_all_planned': completed / denominator if denominator else None,
                'unauthorized_traces': sum(o['unauthorized_executed'] is True for o in outcomes),
                'leak_traces': sum(o['secret_leaked'] is True for o in outcomes)}
    groups = []
    for model, split in sorted({(r['model'], r['split']) for r in rows}):
        group = [r for r in rows if (r['model'], r['split']) == (model, split)]
        groups.append({'model': model, 'split': split,
                       **counts(group, 2 * sum(c['split'] == split for c in cases))})
    return {**counts(rows, planned), 'by_model_split': groups}


def replay(root, output_directory, *, allow_partial=False, include_real=False):
    root, output = Path(root).resolve(), Path(output_directory).resolve()
    destination_root = root / 'results/phase3/phase_protocol'
    if not output.is_relative_to(destination_root):
        raise ValueError('OUTPUT_OUTSIDE_PHASE_PROTOCOL_DIRECTORY')
    if output.exists():
        raise ValueError('REPLAY_OUTPUT_EXISTS')
    base = root / 'results/phase3'
    source_hashes, raw_cache = {}, {}

    def snapshot(path):
        data = path.read_bytes()
        source_hashes[path.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
        return data

    def rows(path):
        return [json.loads(line) for line in snapshot(path).decode('utf-8').splitlines() if line.strip()] if path.exists() else []

    expected = dict(EXPECTED)
    if include_real:
        expected['api/real.jsonl'] = 2160
    loaded = {name: rows(base / name) for name in expected}
    coverage = {name: {'expected': count, 'observed': len(loaded[name]),
                       'complete': len(loaded[name]) == count} for name, count in expected.items()}
    old_cases = rows(root / 'data/benchmark/synthetic_cases.jsonl')
    new_cases = rows(root / 'data/phase3/synthetic_cases.jsonl')
    prepared = rows(root / 'data/phase3/real_prepared.jsonl') if include_real else []
    coverage['old_cases'] = {'expected': 132, 'observed': len(old_cases), 'complete': len(old_cases) == 132}
    coverage['new_cases'] = {'expected': 256, 'observed': len(new_cases), 'complete': len(new_cases) == 256}
    if include_real:
        coverage['real_prepared'] = {'expected': 180, 'observed': len(prepared), 'complete': len(prepared) == 180}
    complete = all(item['complete'] for item in coverage.values())
    if not complete and not allow_partial:
        raise ValueError('INCOMPLETE_PHASE_REPLAY_INPUTS')
    for name, records in loaded.items():
        keys = [row.get('job_id') or _condition(row) for row in records]
        if len(keys) != len(set(keys)):
            raise ValueError('DUPLICATE_REPLAY_CONDITION: ' + name)
    cases = {case['case_id']: case for case in old_cases + new_cases}
    prepared_by_id = {row['skill_id']: row for row in prepared}

    def raw(request_hash):
        if not isinstance(request_hash, str) or len(request_hash) != 64 or any(c not in '0123456789abcdef' for c in request_hash):
            raise ValueError('INVALID_RAW_REQUEST_HASH')
        if request_hash not in raw_cache:
            record = json.loads(snapshot(base / 'api/raw' / (request_hash + '.json')))
            if record.get('request_hash') != request_hash:
                raise ValueError('RAW_REQUEST_HASH_MISMATCH')
            raw_cache[request_hash] = record
        return raw_cache[request_hash]

    def schema(record):
        value = record.get('request', {}).get('text', {}).get('format', {}).get('schema')
        if not isinstance(value, dict):
            raise ValueError('SAVED_RESPONSE_SCHEMA_MISSING')
        return value

    artifacts, comparisons, diagnostics = {}, {}, []
    for track, fixtures in (('regression', old_cases), ('new', new_cases)):
        reparsed, rerun = [], []
        primary = {_condition(row): row for row in loaded[f'runtime/{track}_full.jsonl']}
        for row in loaded[f'api/{track}.jsonl']:
            case = cases[row['case_id']]
            p_raw, q_raw = raw(row['p_request_hash']), raw(row['q_request_hash'])
            planner = parse_phase_planner(p_raw, case)
            q = validate_phase_record(q_raw, schema(q_raw))
            ids = q['prediction']['action_ids'] if q['protocol_valid'] else []
            if len(ids) != len(set(ids)):
                q = {**q, 'protocol_valid': False,
                     'diagnostic_codes': q['diagnostic_codes'] + ['Q_DUPLICATE_ACTION']}
            reparsed.append({**row, 'planner': planner, 'q': q,
                             'q_plan': ids if q['protocol_valid'] else None, 'exploratory_posthoc': True})
            result = run_pipeline_v3(case, planner, q_plan=ids if q['protocol_valid'] else [],
                                     variant='full', transform_fn=transform_v3)
            result['q_protocol_valid'] = q['protocol_valid']
            result['exploratory_posthoc'] = True
            metadata = {key: row[key] for key in ('job_id', 'case_id', 'family_id', 'split', 'scenario',
                                                  'model', 'replicate', 'track', 'p_request_hash', 'q_request_hash')}
            revised = {**metadata, 'variant': 'full', 'result': result, 'exploratory_posthoc': True,
                       'phase_selection': {'p': planner['phase_selection'], 'q': q['phase_selection']}}
            rerun.append(revised)
            previous = primary.get(_condition(row))
            if previous is not None and _outcome(previous) != _outcome(revised):
                diagnostics.append({**metadata, 'before': _outcome(previous), 'after': _outcome(revised)})
        artifacts[f'api/{track}.jsonl'] = reparsed
        artifacts[f'runtime/{track}_full.jsonl'] = rerun
        comparisons[track] = {'primary': _runtime_summary(list(primary.values()), fixtures, EXPECTED[f'api/{track}.jsonl']),
                              'phase_aware': _runtime_summary(rerun, fixtures, EXPECTED[f'api/{track}.jsonl'])}
    factorial = []
    for row in loaded['api/factorial.jsonl']:
        parsed = parse_phase_planner(raw(row['request_hash']), cases[row['case_id']])
        factorial.append({**row, 'planner': parsed, 'exploratory_posthoc': True})
    artifacts['diagnostics/factorial.jsonl'] = factorial
    os_contracts = []
    for row in loaded['api/os_contracts.jsonl']:
        record = raw(row['request_hash'])
        checked = validate_phase_record(record, schema(record))
        os_contracts.append({**row, 'primary_status': row['status'], 'status': 'valid' if checked['protocol_valid'] else 'unresolved',
                             'prediction': checked['prediction'], 'diagnostic_codes': checked['diagnostic_codes'],
                             'phase_protocol': checked, 'exploratory_posthoc': True, 'os_execution_replayed': False})
    artifacts['diagnostics/os_contracts.jsonl'] = os_contracts
    if include_real:
        from tsg.real_v3 import parse_detection_record
        real = []
        for row in loaded['api/real.jsonl']:
            if row.get('model_evaluated') is False or row.get('empty_candidate_set') is True:
                real.append({**row, 'exploratory_posthoc': True})
                continue
            record = raw(row['request_hash'])
            normalized = normalized_phase_record(record, schema(record))
            parsed = parse_detection_record(normalized, prepared_by_id[row['skill_id']], row['context'], row['variant'], row['model'])
            real.append({**parsed, 'job_id': row['job_id'], 'primary_status': row['status'],
                         'phase_protocol': validate_phase_record(record, schema(record)), 'exploratory_posthoc': True})
        artifacts['diagnostics/real.jsonl'] = real
    # Check source snapshots before creating any new output; cached records stay read-only.
    for name, digest in source_hashes.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError('REPLAY_SOURCE_CHANGED: ' + name)
    raw_changes = []
    selection_modes = Counter()
    for request_hash, record in sorted(raw_cache.items()):
        request_schema = record.get('request', {}).get('text', {}).get('format', {}).get('schema')
        checked = validate_phase_record(record, request_schema)
        selection_modes[checked['phase_selection']['selection_mode']] += 1
        if checked['protocol_valid'] != checked['original_protocol_valid']:
            raw_changes.append({'request_hash': request_hash, 'before_valid': checked['original_protocol_valid'],
                                'after_valid': checked['protocol_valid'], 'phase_selection': checked['phase_selection'],
                                'before_diagnostic_codes': checked['original_diagnostic_codes'],
                                'after_diagnostic_codes': checked['diagnostic_codes']})
    summary = {'adapter_version': ADAPTER_VERSION, 'exploratory_posthoc': True,
               'analysis_status': 'complete' if complete else 'partial', 'complete': complete,
               'official_source': OFFICIAL_SOURCE, 'coverage': coverage, 'include_real': include_real,
               'interpretation': 'Retrospective phase-aware replay of the same saved responses; no new independent samples or prospective validation.',
               'additional_api_requests': 0, 'additional_api_cost_usd': 0, 'os_execution_replayed': False,
               'primary_files_modified': False, 'comparisons': comparisons,
               'unique_raw_requests': len(raw_cache), 'selection_mode_counts': dict(selection_modes),
               'changed_unique_raw_requests': raw_changes, 'changed_runtime_conditions': diagnostics,
               'factorial_protocol_valid_before': sum(row['planner']['protocol_valid'] for row in loaded['api/factorial.jsonl']),
               'factorial_protocol_valid_after': sum(row['planner']['protocol_valid'] for row in factorial),
               'os_contracts_valid_before': sum(row['status'] == 'valid' for row in loaded['api/os_contracts.jsonl']),
               'os_contracts_valid_after': sum(row['status'] == 'valid' for row in os_contracts),
               'source_sha256': source_hashes}
    if include_real:
        summary['real_valid_before'] = sum(row['status'] == 'valid' for row in loaded['api/real.jsonl'])
        summary['real_valid_after'] = sum(row['status'] == 'valid' for row in artifacts['diagnostics/real.jsonl'])
    output.mkdir(parents=True)
    for name, records in artifacts.items():
        write_rows(output / name, records)
    save_json(output / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--include-real', action='store_true')
    args = parser.parse_args()
    output = args.output or args.root / 'results/phase3/phase_protocol'
    summary = replay(args.root, output, allow_partial=args.allow_partial, include_real=args.include_real)
    print(json.dumps({key: summary[key] for key in ('analysis_status', 'unique_raw_requests', 'additional_api_requests')}, sort_keys=True))


if __name__ == '__main__':
    main()
