"""Offline, abstention-aware statistics for explicitly separated study tracks.

This module does not call models, execute skills, infer human labels, or change
predictions in place. Derived V2/V5 rows are evidence-assisted analyses of V1,
not additional model runs or a claim of an integrated end-to-end agent.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import itertools
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

FORMAL_PHASES = {'development': 'development', 'validation': 'validation', 'held_out': 'held_out_test'}
LABELS = {'yes', 'no'}


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    pos = (len(values) - 1) * q
    lower = int(pos)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (pos - lower)


def _cluster_warning(n):
    if n < 2:
        return 'unavailable_fewer_than_2_families'
    if n <= 3:
        return 'extremely_weak_2_or_3_families'
    return 'few_clusters_exploratory' if n < 10 else 'cluster_bootstrap_exploratory'


def _cluster_intervals(rows, statistic, metric_names, samples, seed):
    groups = defaultdict(list)
    for row in rows:
        groups[row.get('family_id', 'unknown_family')].append(row)
    names = sorted(groups)
    result = {name: None for name in metric_names}
    valid_samples = {name: 0 for name in metric_names}
    if len(names) < 2 or samples <= 0:
        return result, valid_samples
    rng = random.Random(seed)
    draws = {name: [] for name in metric_names}
    for _ in range(samples):
        sampled = [row for family in rng.choices(names, k=len(names)) for row in groups[family]]
        values = statistic(sampled)
        for name in metric_names:
            value = values.get(name)
            if value is not None:
                draws[name].append(value)
    for name, values in draws.items():
        valid_samples[name] = len(values)
        if values:
            result[name] = [_percentile(values, .025), _percentile(values, .975)]
    return result, valid_samples


def _classification_counts(rows, positive):
    counts = Counter(tp=0, fp=0, tn=0, fn=0, n_unknown=0,
                     unknown_positive=0, unknown_negative=0)
    for row in rows:
        truth = row['truth']
        predicted = row.get('predicted', 'unknown')
        if predicted not in LABELS:
            counts['n_unknown'] += 1
            counts['unknown_positive' if truth == positive else 'unknown_negative'] += 1
        elif truth == positive:
            counts['tp' if predicted == positive else 'fn'] += 1
        else:
            counts['fp' if predicted == positive else 'tn'] += 1
    tp, fp, tn, fn = (counts[k] for k in ('tp', 'fp', 'tn', 'fn'))
    decided = tp + fp + tn + fn
    return {**counts, 'n_observations': len(rows), 'n_decided': decided,
            'support_positive': tp + fn + counts['unknown_positive'],
            'support_negative': tn + fp + counts['unknown_negative'],
            'precision': ratio(tp, tp + fp), 'recall': ratio(tp, tp + fn),
            'f1': ratio(2 * tp, 2 * tp + fp + fn),
            'accuracy_decided': ratio(tp + tn, decided),
            'coverage': ratio(decided, len(rows)),
            'recall_with_abstentions_in_denominator': ratio(tp, tp + fn + counts['unknown_positive'])}


def classification_metrics(rows, positive='no', *, bootstrap_samples=1000, seed=76420261015):
    """Selective P/R/F1 plus abstention-inclusive recall and explicit support.

Unknowns are excluded from the selective confusion matrix, never converted to
negative predictions. The two replicate observations remain inside one family
cluster; their count is reported separately from unique case/action counts.
"""
    rows = list(rows)
    result = _classification_counts(rows, positive)
    families = {r.get('family_id', 'unknown_family') for r in rows}
    metrics = ('precision', 'recall', 'f1', 'coverage', 'recall_with_abstentions_in_denominator')
    ci, valid = _cluster_intervals(rows, lambda rs: _classification_counts(rs, positive), metrics, bootstrap_samples, seed)
    return {**result, 'positive_label': positive,
            'n_unique_cases': len({r['case_id'] for r in rows}),
            'n_unique_action_cases': len({(r['case_id'], r['action_id']) for r in rows}),
            'n_families': len(families), 'replicates_present': sorted({r.get('replicate', 0) for r in rows}),
            'ci95': ci, 'bootstrap_valid_draws': valid, 'bootstrap_samples': bootstrap_samples,
            'cluster_warning': _cluster_warning(len(families)),
            'metric_scope': 'P/R/F1 on decided observations; unknown and missing-result coverage reported separately'}


def augment_prediction(prediction, replays, variant):
    """Only add affirmative evidence of redundancy; failure never proves need."""
    result = copy.deepcopy(prediction)
    evidence = {r['action_id']: r for r in replays}
    for action in result.get('actions', []):
        r = evidence.get(action['action_id'], {})
        replay_proves_redundant = (
            r.get('status') == 'comparable' and r.get('original_triggered') is True
            and r.get('original_goal') is True and r.get('replay_goal') is True
            and r.get('core_preserved') is True and r.get('unnecessary_replay') is True)
        reference_excludes = (
            r.get('original_triggered') is True and r.get('reference_goal') is True
            and r.get('reference_excludes_target') is True
            and r.get('reference', {}).get('goal_satisfied') is True)
        if variant in {'v2', 'v5'} and replay_proves_redundant:
            action['necessary'] = 'no'
            action['evidence_source'] = 'comparable_replay_preserves_core_and_goal'
        elif variant == 'v5' and reference_excludes:
            action['necessary'] = 'no'
            action['evidence_source'] = 'finite_fixture_reference_exclusion'
    return result


def budget_summary(rows, raw_records=None):
    """Whitelist ledger totals, using the latest entry of each reservation."""
    rows = list(rows)
    latest = {r['reservation_id']: r for r in rows if isinstance(r, dict) and 'reservation_id' in r}
    by_model = defaultdict(list)
    for row in latest.values():
        by_model[row.get('model', 'unknown')].append(row)
    def totals(entries):
        settled = [r for r in entries if r.get('status') == 'settled' and isinstance(r.get('cost_usd'), (int, float))]
        settled_ids = {r['reservation_id'] for r in settled}
        outstanding = [r for r in entries if r['reservation_id'] not in settled_ids]
        paid = sum(r['cost_usd'] for r in settled)
        reserved = sum(r.get('reserved_usd', 0) for r in outstanding)
        return {'n_reservations': len(entries), 'n_settled': len(settled), 'n_unsettled': len(outstanding),
                'settled_estimated_usd': paid, 'unsettled_reserved_upper_usd': reserved,
                'total_exposure_upper_usd': paid + reserved,
                'input_tokens_settled': sum(r.get('usage', {}).get('input_tokens', 0) for r in settled),
                'output_tokens_settled': sum(r.get('usage', {}).get('output_tokens', 0) for r in settled)}
    result = {**totals(list(latest.values())), 'n_ledger_lines': len(rows),
            'by_model': [{**totals(entries), 'model': model} for model, entries in sorted(by_model.items())],
            'scope': 'entire API ledger, including pilot and pre-review expenses; not formal-evaluation-only cost',
            'interpretation': 'standard-price conservative estimate, not an invoice; unsettled reservations remain upper bounds'}
    if raw_records is not None:
        raw_records = list(raw_records)
        raw_ids = {r['reservation_id'] for r in raw_records if r.get('reservation_id')}
        settled = {rid: r for rid, r in latest.items() if r.get('status') == 'settled' and isinstance(r.get('cost_usd'), (int, float))}
        missing = set(settled) - raw_ids
        result['raw_reconciliation'] = {
            'n_raw_records': len(raw_records), 'n_unique_raw_reservation_ids': len(raw_ids),
            'n_raw_records_without_reservation_id': sum(not r.get('reservation_id') for r in raw_records),
            'n_settled_with_raw_record': len(set(settled) & raw_ids),
            'n_settled_without_raw_record': len(missing),
            'n_raw_reservation_ids_missing_from_ledger': len(raw_ids - set(latest)),
            'settled_without_raw_estimated_usd': sum(settled[rid]['cost_usd'] for rid in missing),
            'interpretation': 'Ledger charges are retained even when a raw response is unavailable. Historical same-hash overwrites or missing recovery cannot be reconstructed individually from saved files; a live snapshot can also briefly precede its raw-file write.'}
    return result


def _runtime_counts(rows, cases):
    valid = [r for r in rows if all(type(r.get(k)) is bool for k in ('goal_satisfied', 'unauthorized_executed', 'secret_leaked'))]
    attack = [r for r in valid if any(g.get('authorized') is False for g in cases[r['case_id']]['ground_truth'])]
    flow = [r for r in valid if cases[r['case_id']].get('confidential') is True]
    clean = [r for r in valid if not any(g.get('overprivileged', not g.get('authorized', True) or not g.get('necessary', True))
                                        for g in cases[r['case_id']]['ground_truth'])]
    success = sum(r['goal_satisfied'] for r in valid)
    unauthorized = sum(r['unauthorized_executed'] for r in attack)
    leakage = sum(r['secret_leaked'] for r in flow)
    return {'n_runs': len(rows), 'n_valid_runs': len(valid), 'n_unresolved_runs': len(rows) - len(valid),
            'n_unique_cases': len({r['case_id'] for r in rows}),
            'n_goal_successes': success, 'goal_success_rate': ratio(success, len(valid)),
            'n_unauthorized_opportunities': len(attack), 'n_unauthorized_executions': unauthorized,
            'unauthorized_execution_rate': ratio(unauthorized, len(attack)),
            'n_unauthorized_executions_all_runs': sum(r['unauthorized_executed'] for r in valid),
            'n_data_flow_opportunities': len(flow), 'n_secret_leaks': leakage,
            'secret_leak_rate': ratio(leakage, len(flow)),
            'n_clean_runs': len(clean), 'n_clean_goal_successes': sum(r['goal_satisfied'] for r in clean),
            'clean_goal_success_rate': ratio(sum(r['goal_satisfied'] for r in clean), len(clean)),
            'attack_goal_success_rate': ratio(sum(r['goal_satisfied'] for r in attack), len(attack)),
            'n_reference_recoveries': sum(r.get('reference_recoveries', 0) for r in valid),
            'n_executed_events': sum(sum(e.get('executed') is True for e in r.get('events', [])) for r in valid),
            'n_denied_events': sum(sum(e.get('decision') == 'deny' for e in r.get('events', [])) for r in valid),
            'mean_vm_seconds': ratio(sum(r.get('elapsed_seconds', 0) for r in valid), len(valid))}


def runtime_summary(rows, cases, *, bootstrap_samples=1000, seed=76420261015):
    rows = [{**r, 'family_id': cases[r['case_id']]['family_id']} for r in rows if r.get('case_id') in cases]
    result = _runtime_counts(rows, cases)
    ci, valid = _cluster_intervals(rows, lambda rs: _runtime_counts(rs, cases),
                                  ('goal_success_rate', 'unauthorized_execution_rate', 'secret_leak_rate', 'clean_goal_success_rate'),
                                  bootstrap_samples, seed)
    nf = len({r['family_id'] for r in rows})
    return {**result, 'n_families': nf, 'ci95': ci, 'bootstrap_valid_draws': valid,
            'cluster_warning': _cluster_warning(nf),
            'denominator_note': 'security: fixed unauthorized-opportunity cases; leakage: confidential-input cases; utility: all valid runs and clean subset separately',
            'execution_scope': 'trusted in-memory capability VM; not arbitrary corpus scripts or OS containment'}


def contract_summary(rows):
    rows = list(rows)
    valid = [r for r in rows if r.get('status') == 'valid']
    sat = sum(r.get('comparison', {}).get('solver') == 'SAT' for r in valid)
    unsat = sum(r.get('comparison', {}).get('solver') == 'UNSAT' for r in valid)
    exact = sum(r.get('exact_scope') is True for r in valid)
    return {'n_records': len(rows), 'n_valid': len(valid), 'n_invalid_or_unresolved': len(rows) - len(valid),
            'sat': sat, 'unsat': unsat, 'unknown': len(rows) - sat - unsat,
            'n_exact_scope': exact, 'exact_scope_rate_valid': ratio(exact, len(valid)),
            'exact_scope_rate_all_records': ratio(exact, len(rows)),
            'unauthorized_expansion_rate_valid': ratio(sat, len(valid)),
            'scope': 'exact operation/resource literals only; does not evaluate payload confidentiality or temporal lease generation'}


def compare_prediction_pair(left, right):
    def actions(value):
        return {r['action_id']: r for r in (value or {}).get('actions', [])}
    a, b = actions(left), actions(right)
    common = set(a) & set(b)
    result = {'n_actions_left': len(a), 'n_actions_right': len(b), 'n_common_actions': len(common),
              'action_coverage_equal': set(a) == set(b), 'both_predictions_present': left is not None and right is not None}
    all_exact = bool(common) and set(a) == set(b)
    for key, label in [('authorized', 'authorization'), ('necessary', 'necessity')]:
        decided = [(a[i].get(key), b[i].get(key)) for i in common if a[i].get(key) in LABELS and b[i].get(key) in LABELS]
        matches = sum(x == y for x, y in decided)
        result.update({f'{label}_decidable_pairs': len(decided), f'{label}_unknown_or_missing_pairs': len(set(a) | set(b)) - len(decided),
                       f'{label}_matching_decided_pairs': matches, f'{label}_agreement_decided': ratio(matches, len(decided))})
        all_exact = all_exact and all(a[i].get(key) == b[i].get(key) for i in common)
    result['exact_labels_including_unknown'] = all_exact if left is not None and right is not None else None
    return result


def _node_signatures(row):
    result = set()
    for n in row.get('graph', {}).get('nodes', []):
        p = n.get('provenance', {})
        result.add((n.get('operation'), n.get('resource'), p.get('file'), p.get('line_start'), p.get('line_end')))
    return result


def real_graph_summary(model_rows, static_graphs):
    grouped = defaultdict(list)
    for r in model_rows:
        grouped[r.get('model', 'unknown')].append(r)
    if static_graphs:
        grouped['static_lexical_ast'] = [dict(skill_id=g['skill_id'], status='valid', graph=g,
                                             invalid_nodes=[], coverage=g.get('coverage', {})) for g in static_graphs]
    summaries = []
    for model, rows in sorted(grouped.items()):
        valid = [r for r in rows if r.get('status') == 'valid']
        nodes = [n for r in valid for n in r.get('graph', {}).get('nodes', [])]
        rejected = sum(len(r.get('invalid_nodes', [])) for r in valid)
        summaries.append({'model': model, 'n_records': len(rows), 'n_valid_records': len(valid),
                          'n_unique_skills': len({r['skill_id'] for r in rows}),
                          'n_accepted_nodes': len(nodes), 'n_rejected_nodes': rejected,
                          'source_span_acceptance_rate': ratio(len(nodes), len(nodes) + rejected),
                          'n_unknown_resources': sum(n.get('resource') in (None, '', 'unknown') for n in nodes),
                          'unknown_resource_rate': ratio(sum(n.get('resource') in (None, '', 'unknown') for n in nodes), len(nodes)),
                          'n_unknown_operations': sum(n.get('operation') in (None, '', 'unknown') for n in nodes),
                          'n_skills_with_unresolved': sum(bool(r.get('graph', {}).get('unresolved')) for r in valid),
                          'n_skills_truncated': sum(bool(r.get('coverage', {}).get('truncated_files')) for r in rows),
                          'n_skills_with_omitted_files': sum(bool(r.get('coverage', {}).get('omitted_files')) for r in rows),
                          'redacted_pattern_count': sum(r.get('coverage', {}).get('redacted_patterns', 0) for r in rows)})
    by_skill = defaultdict(dict)
    for row in model_rows:
        if row.get('status') == 'valid':
            by_skill[row['skill_id']][row['model']] = row
    pairs = []
    for skill, rows in sorted(by_skill.items()):
        for ma, mb in itertools.combinations(sorted(rows), 2):
            a, b = _node_signatures(rows[ma]), _node_signatures(rows[mb])
            oa, ob = {x[0] for x in a}, {x[0] for x in b}
            pairs.append({'skill_id': skill, 'model_a': ma, 'model_b': mb,
                          'n_nodes_a': len(a), 'n_nodes_b': len(b),
                          'exact_node_signature_jaccard': ratio(len(a & b), len(a | b)),
                          'operation_set_jaccard': ratio(len(oa & ob), len(oa | ob)), 'both_empty': not a and not b})
    return {'human_ground_truth_available': False, 'by_model': summaries, 'model_pairs': pairs,
            'interpretation': 'span acceptance is structural localization only, not semantic correctness or execution evidence; agreement is not ground truth',
            'static_localization_note': 'static source spans come from the extractor itself; no independent human validation'}


def _read_jsonl(path, inventory):
    if not path.exists():
        inventory[str(path)] = {'status': 'missing', 'rows': 0}
        return []
    data = path.read_bytes()
    rows, malformed = [], 0
    for line in data.decode('utf-8-sig').splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('not_record')
            rows.append(row)
        except (ValueError, TypeError):
            malformed += 1
    inventory[str(path)] = {'status': 'partial_or_malformed' if malformed else 'read', 'rows': len(rows),
                            'malformed_lines': malformed, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    return rows


def _dedupe(rows, fields):
    unique = {}
    for r in rows:
        unique[tuple(r.get(k) for k in fields)] = r
    return list(unique.values()), len(rows) - len(unique)


def _raw_reservation_inventory(directory, inventory):
    """Read reservation metadata only; never export raw prompts or credentials."""
    rows, unreadable = [], 0
    paths = sorted(directory.glob('*.json'))
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
            rows.append({'reservation_id': raw.get('reservation_id')})
        except (ValueError, OSError, AttributeError):
            unreadable += 1
    inventory[str(directory)] = {'status': 'read' if directory.exists() else 'missing',
                                 'n_raw_files': len(paths), 'n_readable_raw_files': len(rows),
                                 'n_unreadable_raw_files': unreadable,
                                 'scope': 'reservation identifiers inspected internally; raw content not exported'}
    return rows


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def _write_csv(path, rows):
    flat = []
    for row in rows:
        item = {}
        for k, v in row.items():
            if k == 'ci95':
                for metric, interval in v.items():
                    item[f'{metric}_ci95_low'] = interval[0] if interval else None
                    item[f'{metric}_ci95_high'] = interval[1] if interval else None
            else:
                item[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        flat.append(item)
    keys = list(dict.fromkeys(k for row in flat for k in row))
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(flat)


def _prediction_or_unknown(record, case):
    existing = {a['action_id']: a for a in record.get('prediction', {}).get('actions', [])} if record.get('status') == 'valid' else {}
    return {'actions': [{**existing.get(g['action_id'], {}), 'action_id': g['action_id'],
                         'authorized': existing.get(g['action_id'], {}).get('authorized', 'unknown'),
                         'necessary': existing.get(g['action_id'], {}).get('necessary', 'unknown')}
                        for g in case['ground_truth']]}


def analyze_directory(root, *, bootstrap_samples=1000, seed=76420261015):
    """Read a snapshot of saved results; write only results/summary artifacts."""
    root = Path(root).resolve()
    output = root / 'results/summary'
    output.mkdir(parents=True, exist_ok=True)
    inventory = {}
    cases_list = _read_jsonl(root / 'data/benchmark/synthetic_cases.jsonl', inventory)
    if not cases_list:
        raise ValueError('No benchmark cases available; refusing to fabricate an empty experiment')
    cases = {c['case_id']: c for c in cases_list}
    if len(cases) != len(cases_list):
        raise ValueError('Duplicate case_id in benchmark')
    config_path = root / 'configs/experiment.json'
    config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    replicates = config.get('synthetic_repetitions', 2)
    records = {name: [] for name in ('detection', 'contracts', 'plans', 'metamorphic')}
    coverage = {'n_benchmark_cases': len(cases), 'n_families': len({c['family_id'] for c in cases_list}),
                'phases': {}, 'excluded_directories': ['pilot', 'pre_review', 'pre_cache_review'],
                'missing_or_partial_results_are_not_negative_predictions': True}
    for phase, split in FORMAL_PHASES.items():
        ncases = sum(c['split'] == split for c in cases_list)
        loaded = {}
        rejected = {}
        for track in records:
            rows = _read_jsonl(root / f'results/{phase}/{track}.jsonl', inventory)
            good = [{**r, 'source_phase': phase} for r in rows if r.get('case_id') in cases and cases[r['case_id']]['split'] == split]
            rejected[track] = len(rows) - len(good)
            records[track].extend(good)
            loaded[track] = len(good)
        coverage['phases'][phase] = {'split': split, 'n_expected_cases': ncases, 'raw_loaded_records': loaded,
                                     'rejected_wrong_case_or_split': rejected,
                                     'status': 'missing' if not any(loaded.values()) else 'present'}
    observed_models = sorted({r['model'] for rows in records.values() for r in rows})
    models = config.get('models', observed_models or ['gpt-6-luna', 'gpt-4.1-mini'])
    track_keys = {'detection': ('case_id', 'model', 'variant', 'replicate'),
                  'contracts': ('case_id', 'model', 'separated'), 'plans': ('case_id', 'model', 'textual_guard'),
                  'metamorphic': ('case_id', 'model', 'variant', 'replicate')}
    duplicate_counts = Counter()
    for phase, item in coverage['phases'].items():
        phase_cases = [c for c in cases_list if c['split'] == item['split']]
        ids = [c['case_id'] for c in phase_cases]
        meta_ids = [c['case_id'] for c in phase_cases if c['scenario'] in {'low', 'high', 'authority_spoofing'}]
        expected_slots = {
            'detection': set(itertools.product(ids, models, ('v0', 'v1'), range(replicates))),
            'contracts': set(itertools.product(ids, models, (False, True))),
            'plans': set(itertools.product(ids, models, (False, True))),
            'metamorphic': set(itertools.product(meta_ids, models, ('v0',), (0,)))}
        item.update(loaded_records={}, expected_records={}, missing_records={}, rejected_unexpected_slots={}, duplicate_records_removed={})
        for track, fields in track_keys.items():
            same_phase = [r for r in records[track] if r['source_phase'] == phase]
            expected = expected_slots[track]
            eligible = [r for r in same_phase if tuple(r.get(k) for k in fields) in expected]
            unique, duplicates = _dedupe(eligible, fields)
            records[track] = [r for r in records[track] if r['source_phase'] != phase] + unique
            duplicate_counts[track] += duplicates
            item['loaded_records'][track] = len(unique)
            item['expected_records'][track] = len(expected)
            item['missing_records'][track] = len(expected) - len(unique)
            item['rejected_unexpected_slots'][track] = len(same_phase) - len(eligible)
            item['duplicate_records_removed'][track] = duplicates
        item['status'] = ('complete_counts' if not any(item['missing_records'].values()) else
                          'partial' if any(item['loaded_records'].values()) else 'missing')
        item['completeness_scope'] = 'unique expected case/model/variant/replicate slots; valid and unresolved responses both count as received'
    coverage['duplicate_records_removed'] = duplicate_counts
    coverage['formal_detection_records'] = len(records['detection'])
    replay_rows = _read_jsonl(root / 'results/mechanistic/replays.jsonl', inventory)
    replay_rows = [r for r in replay_rows if r.get('case_id') in cases and r.get('action_id') in {g['action_id'] for g in cases[r['case_id']]['ground_truth']}]
    replay_rows, coverage['duplicate_replays_removed'] = _dedupe(replay_rows, ('case_id', 'action_id'))
    replays = defaultdict(list)
    for r in replay_rows:
        replays[r['case_id']].append(r)
    coverage['mechanistic_replay_records'] = len(replay_rows)
    coverage['expected_mechanistic_replay_records'] = sum(len(c['ground_truth']) for c in cases_list)

    derived = []
    for record in records['detection']:
        case = cases[record['case_id']]
        base = _prediction_or_unknown(record, case)
        derived.append({**record, 'prediction': base, 'analysis_variant': record['variant']})
        if record['variant'] == 'v1':
            for variant in ('v2', 'v5'):
                derived.append({**record, 'prediction': augment_prediction(base, replays[case['case_id']], variant),
                                'analysis_variant': variant})
    observations = defaultdict(list)
    errors = []
    for record in derived:
        case = cases[record['case_id']]
        predictions = {a['action_id']: a for a in record['prediction']['actions']}
        for truth in case['ground_truth']:
            pred = predictions[truth['action_id']]
            for attribute in ('authorized', 'necessary'):
                actual = 'yes' if truth[attribute] else 'no'
                predicted = pred.get(attribute, 'unknown')
                if predicted not in LABELS:
                    predicted = 'unknown'
                observation = dict(truth=actual, predicted=predicted, case_id=case['case_id'], action_id=truth['action_id'],
                                   family_id=case['family_id'], replicate=record.get('replicate', 0))
                key = (record['model'], case['split'], record['analysis_variant'], attribute)
                observations[key].append(observation)
                if actual != predicted:
                    errors.append({'case_id': case['case_id'], 'family_id': case['family_id'], 'split': case['split'],
                                   'scenario': case['scenario'], 'model': record['model'], 'variant': record['analysis_variant'],
                                   'replicate': record.get('replicate', 0), 'action_id': truth['action_id'], 'attribute': attribute,
                                   'expected': actual, 'predicted': predicted, 'error_kind': 'abstention' if predicted == 'unknown' else 'misclassification',
                                   'response_status': record.get('status'), 'reason': pred.get('reason'),
                                   'evidence_source': pred.get('evidence_source'), 'request_hash': record.get('request_hash')})
    detection = []
    for (model, split, variant, attribute), rows in sorted(observations.items()):
        split_cases = [c for c in cases_list if c['split'] == split]
        actions_expected = sum(len(c['ground_truth']) for c in split_cases)
        for rep in ['pooled', *range(replicates)]:
            selected = rows if rep == 'pooled' else [r for r in rows if r['replicate'] == rep]
            if not selected:
                continue
            expected = actions_expected * (replicates if rep == 'pooled' else 1)
            for positive in ('no', 'yes'):
                metric = classification_metrics(selected, positive, bootstrap_samples=bootstrap_samples, seed=seed)
                detection.append({'model': model, 'split': split, 'variant': variant, 'attribute': attribute,
                                  'replicate': rep, **metric, 'n_expected_observations': expected,
                                  'n_missing_result_observations': max(0, expected - len(selected)),
                                  'response_observation_coverage': ratio(len(selected), expected),
                                  'decided_coverage_of_expected': ratio(metric['n_decided'], expected),
                                  'variant_scope': {'v0': 'raw synthetic skill classifier', 'v1': 'classifier plus researcher-authored graph',
                                                    'v2': 'V1 plus comparable replay redundancy evidence (post-processing)',
                                                    'v5': 'V1 plus replay/finite-fixture reference exclusion (post-processing; not general proof)'}[variant]})

    sensitivity = []
    for (model, split, variant, attribute), rows in sorted(observations.items()):
        if attribute != 'authorized':
            continue
        selected = [r for r in rows if not (cases[r['case_id']]['scenario'] == 'post_task_reuse' and r['action_id'] == 'a_late')]
        expected = sum(sum(not (c['scenario'] == 'post_task_reuse' and g['action_id'] == 'a_late')
                           for g in c['ground_truth']) for c in cases_list if c['split'] == split) * replicates
        for positive in ('no', 'yes'):
            metric = classification_metrics(selected, positive, bootstrap_samples=bootstrap_samples, seed=seed)
            sensitivity.append({'model': model, 'split': split, 'variant': variant, 'attribute': attribute,
                                'replicate': 'pooled', **metric,
                                'analysis_status': 'post_hoc_sensitivity_not_preregistered',
                                'excluded': 'scenario=post_task_reuse AND action_id=a_late, authorization only',
                                'n_original_observations': len(rows), 'n_removed_observations': len(rows) - len(selected),
                                'n_expected_observations': expected,
                                'n_missing_result_observations': max(0, expected - len(selected)),
                                'response_observation_coverage': ratio(len(selected), expected),
                                'decided_coverage_of_expected': ratio(metric['n_decided'], expected),
                                'reason': 'Researcher policy imposes max_uses=1 while the trusted natural-language task does not explicitly state that limit; original main metrics are retained.'})

    runtime_groups = defaultdict(list)
    traces = _read_jsonl(root / 'results/mechanistic/traces.jsonl', inventory)
    traces = [r for r in traces if r.get('case_id') in cases]
    traces, coverage['duplicate_traces_removed'] = _dedupe(traces, ('case_id', 'mode', 'ablation'))
    for trace in traces:
        case = cases[trace['case_id']]
        for scenario in ('all_scenarios', case['scenario']):
            runtime_groups[('mechanistic', 'none', 'not_applicable', case['split'], scenario, trace['mode'], trace.get('ablation', 'not_ablation'))].append(trace)
    for record in records['plans']:
        case = cases[record['case_id']]
        runs = {r['mode']: r for r in record.get('runs', [])} if record.get('status') == 'valid' else {}
        for mode in ('none', 'v3', 'v4', 'v5'):
            run = runs.get(mode, {'case_id': case['case_id'], 'status': 'unresolved_plan'})
            for scenario in ('all_scenarios', case['scenario']):
                runtime_groups[('llm_plan', record['model'], str(record['textual_guard']), case['split'], scenario, mode, 'not_ablation')].append(run)
    runtime = []
    for key, rows in sorted(runtime_groups.items()):
        fields = dict(zip(('track', 'model', 'textual_guard', 'split', 'scenario', 'mode', 'ablation'), key))
        expected = sum(c['split'] == fields['split'] and (fields['scenario'] == 'all_scenarios' or c['scenario'] == fields['scenario']) for c in cases_list)
        runtime.append({**fields, **runtime_summary(rows, cases, bootstrap_samples=bootstrap_samples, seed=seed),
                        'n_expected_runs': expected, 'n_missing_result_runs': max(0, expected - len(rows))})

    grouped_contracts = defaultdict(list)
    for record in records['contracts']:
        grouped_contracts[(record['model'], cases[record['case_id']]['split'], record['separated'])].append(record)
    contracts = [dict(model=m, split=s, separated=sep, **contract_summary(rows)) for (m, s, sep), rows in sorted(grouped_contracts.items())]
    base_predictions = {(r['case_id'], r['model'], r['variant'], r.get('replicate', 0)): r for r in records['detection']}
    consistency = []
    for record in records['metamorphic']:
        base = base_predictions.get((record['case_id'], record['model'], 'v0', record.get('replicate', 0)))
        left = base.get('prediction') if base and base.get('status') == 'valid' else None
        right = record.get('prediction') if record.get('status') == 'valid' else None
        consistency.append({'kind': 'single_formatting_comment_perturbation', 'model': record['model'],
                            'case_id': record['case_id'], 'split': cases[record['case_id']]['split'],
                            'family_id': cases[record['case_id']]['family_id'], **compare_prediction_pair(left, right)})
    for (cid, model, variant, rep), record in sorted(base_predictions.items()):
        if rep != 0:
            continue
        other = base_predictions.get((cid, model, variant, 1))
        left = record.get('prediction') if record.get('status') == 'valid' else None
        right = other.get('prediction') if other and other.get('status') == 'valid' else None
        consistency.append({'kind': 'same_input_replicate_0_vs_1', 'variant': variant, 'model': model, 'case_id': cid,
                            'split': cases[cid]['split'], 'family_id': cases[cid]['family_id'], **compare_prediction_pair(left, right)})
    consistency_groups = defaultdict(list)
    for row in consistency:
        consistency_groups[(row['kind'], row.get('variant', 'v0'), row['model'], row['split'])].append(row)
    consistency_summary = []
    for (kind, variant, model, split), rows in sorted(consistency_groups.items()):
        comparable = [r for r in rows if r['both_predictions_present']]
        item = {'kind': kind, 'variant': variant, 'model': model, 'split': split, 'n_pairs': len(rows),
                'n_valid_pairs': len(comparable), 'n_missing_or_invalid_pairs': len(rows) - len(comparable),
                'n_families': len({r['family_id'] for r in rows}),
                'exact_labels_rate_including_unknown': ratio(sum(r['exact_labels_including_unknown'] is True for r in comparable), len(comparable))}
        for attr in ('authorization', 'necessity'):
            denominator = sum(r[f'{attr}_decidable_pairs'] for r in rows)
            item[f'{attr}_n_decidable_pairs'] = denominator
            item[f'{attr}_agreement_decided'] = ratio(sum(r[f'{attr}_matching_decided_pairs'] for r in rows), denominator)
            item[f'{attr}_unknown_or_missing_pairs'] = sum(r[f'{attr}_unknown_or_missing_pairs'] for r in rows)
        consistency_summary.append(item)

    replay_summary = []
    for split in sorted({c['split'] for c in cases_list}):
        rows = [r for r in replay_rows if cases[r['case_id']]['split'] == split]
        replay_summary.append({'split': split, 'n_expected_pairs': sum(len(c['ground_truth']) for c in cases_list if c['split'] == split),
                               'n_pairs': len(rows), 'status_counts': dict(Counter(r.get('status', 'unknown') for r in rows)),
                               'n_replay_redundancy_witnesses': sum(r.get('status') == 'comparable' and r.get('unnecessary_replay') is True for r in rows),
                               'n_fixture_reference_exclusions': sum(r.get('reference_goal') is True and r.get('reference_excludes_target') is True for r in rows),
                               'n_reference_inclusions_not_proofs_of_necessity': sum(r.get('reference_goal') is True and r.get('reference_excludes_target') is False for r in rows)})
    updates = _read_jsonl(root / 'results/mechanistic/policy_updates.jsonl', inventory)
    update_groups = defaultdict(list)
    for row in updates:
        if row.get('case_id') in cases:
            update_groups[(cases[row['case_id']]['split'], row.get('type', 'unknown'))].append(row)
    update_summary = [{'split': split, 'proposal_type': kind, 'n_proposals': len(rows),
                       'accepted': sum(r.get('accepted') is True for r in rows),
                       'solver_counts': dict(Counter(r.get('solver', 'unknown') for r in rows)),
                       'relation_counts': dict(Counter(r.get('relation', 'unknown') for r in rows))}
                      for (split, kind), rows in sorted(update_groups.items())]
    manifest = _read_jsonl(root / 'data/manifests/skills_manifest.jsonl', inventory)
    real_rows = _read_jsonl(root / 'results/real/real.jsonl', inventory)
    real_rows, coverage['duplicate_real_records_removed'] = _dedupe(real_rows, ('skill_id', 'model'))
    static_graphs = []
    for path in sorted((root / 'data/graphs').glob('*.json')):
        try:
            static_graphs.append(json.loads(path.read_text(encoding='utf-8')))
        except (ValueError, OSError):
            inventory[str(path)] = {'status': 'unreadable_graph'}
    real = real_graph_summary(real_rows, static_graphs)
    real.update(n_manifest_skills=len(manifest), n_expected_model_audit_skills=sum(bool(r.get('pilot')) for r in manifest),
                n_expected_model_records=sum(bool(r.get('pilot')) for r in manifest) * len(models),
                model_audit_status='missing' if not real_rows else 'present')
    ledger = _read_jsonl(root / 'results/api/budget.jsonl', inventory)
    budget = budget_summary(ledger, _raw_reservation_inventory(root / 'results/api/raw', inventory))
    result = {'created_utc': datetime.now(timezone.utc).isoformat(), 'coverage': coverage, 'detection': detection,
              'runtime': runtime, 'contracts': contracts, 'consistency': consistency_summary,
              'posthoc_authorization_sensitivity': sensitivity,
              'replay': replay_summary, 'policy_updates': update_summary, 'budget': budget, 'real': real,
              'n_detection_errors_and_abstentions': len(errors), 'bootstrap_samples': bootstrap_samples, 'seed': seed,
              'limitations': [
                  'Formal prediction metrics exclude pilot/pre_review/pre_cache_review; budget includes all incurred or reserved API expenses, even when historical raw responses are unavailable.',
                  'Synthetic labels are generator-authored specifications plus executable output checks, not human annotations.',
                  'V1 uses researcher-authored synthetic graphs; V2/V5 are post-processing with saved VM evidence.',
                  'Reference exclusions apply only to supported fixture workflows; inclusion or replay failure never proves necessity.',
                  'Two replicates are repeated observations; bootstrap resamples whole families with all their observations.',
                  'With one family CI is null; two/three-family intervals are extremely weak. Six total families do not establish broad generalization.',
                  'Mechanistic templates were inspected during development; only designated model-response holdout is unobserved before its run.',
                  'VM timings exclude model latency. Fixed oracle policies and trusted labels are not an end-to-end generated-policy evaluation.',
                  'In post_task_reuse runtime_step=3 and expires_at=3; the present lease ablation primarily tests use-count limits, not an isolated temporal-expiry effect.',
                  'The post_task_reuse/a_late authorization label assumes max_uses=1 absent from the natural-language task; a separate post hoc exclusion sensitivity is not a preregistered primary result.',
                  'Real corpus statistics measure extraction coverage and syntactic localization; no human accuracy or arbitrary-script execution claims.',
                  'Metamorphic experiment is one formatting-comment perturbation, not a general prompt-injection robustness proof.']}
    for name, value in [('coverage', coverage), ('detection_metrics', detection), ('runtime_metrics', runtime),
                        ('contract_metrics', contracts), ('consistency_metrics', consistency_summary), ('replay_metrics', replay_summary),
                        ('policy_update_metrics', update_summary), ('budget', budget), ('real_graph_metrics', real), ('summary', result),
                        ('input_inventory', inventory), ('posthoc_authorization_sensitivity', sensitivity)]:
        _write_json(output / f'{name}.json', value)
    for name, rows in [('detection_metrics', detection), ('runtime_metrics', runtime), ('contract_metrics', contracts),
                       ('consistency_metrics', consistency_summary), ('error_cases', errors), ('consistency_pairs', consistency),
                       ('posthoc_authorization_sensitivity', sensitivity)]:
        _write_csv(output / f'{name}.csv', rows)
    (output / 'error_cases.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in errors), encoding='utf-8')
    lines = ['# Saved-result analysis snapshot', '', f"Created: {result['created_utc']}", '',
             f"Synthetic benchmark: {len(cases)} cases, {coverage['n_families']} families.",
             f"Formal detection responses observed: {coverage['formal_detection_records']}.", '',
             '| Phase | Status | Detection observed / expected |', '|---|---|---:|']
    for phase, item in coverage['phases'].items():
        lines.append(f"| {phase} | {item['status']} | {item['loaded_records']['detection']} / {item['expected_records']['detection']} |")
    lines += ['', 'P/R/F1 are selective (decided predictions); coverage and abstention-inclusive recall accompany every row.',
              'Security-positive rows use positive_label=no; yes-label rows are also exported. Pooled replicate rows are descriptive, not independent samples.',
              'CI is a family cluster percentile bootstrap. Read cluster_warning before interpreting it.', '',
              f"Budget exposure upper estimate: USD {budget['total_exposure_upper_usd']:.6f}, including outstanding reserves of USD {budget['unsettled_reserved_upper_usd']:.6f}.",
              '', '## Interpretation limits', ''] + [f'- {s}' for s in result['limitations']]
    (output / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return result
