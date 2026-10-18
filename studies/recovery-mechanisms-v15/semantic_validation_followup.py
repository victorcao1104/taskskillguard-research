"""EXPLORATORY semantic-counterexample supplement; frozen v15 core untouched.

Inputs are declarative specification examples. Mutation recipes are knowingly
chosen to test those semantics; this is common-authorship diagnostic evidence,
not blinded generalization or a confirmatory comparison with the core study.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from copy import deepcopy
from pathlib import Path

from rm15.tasks import TEMPLATES, instance, oracle, solver, specification, structure
from rm15.validation_study import (aggregate, canonical_bytes, code_digest, digest,
                                   evaluate_program, source_hashes, suite_status)

ROOT = Path(__file__).resolve().parent
STRATEGIES = ('random', 'semantic_challenge')


def _rows(*values):
    return [{'id': chr(97 + i), **value} for i, value in enumerate(values)]


def _edges(*values):
    return [{'u': p[0], 'v': p[1], **({'weight': p[2]} if len(p) == 3 else {})} for p in values]


def declarative_examples():
    """Four valid specification-derived examples/template; no candidate access."""
    return {
        'aggregation.group_totals': [
            ('empty_rows', {'rows': []}),
            ('zero_quantity_discount_per_row', {'rows': _rows({'group': 'g', 'qty': 0, 'price': 7, 'discount': 2})}),
            ('repeated_group_per_row_discount', {'rows': _rows({'group': 'g', 'qty': 3, 'price': 4, 'discount': 2}, {'group': 'g', 'qty': 2, 'price': 1, 'discount': 1})}),
            ('zero_price_distinct_groups', {'rows': _rows({'group': 'g', 'qty': 2, 'price': 0, 'discount': 1}, {'group': 'h', 'qty': 1, 'price': 4, 'discount': 0})})],
        'aggregation.running_balance': [
            ('empty_negative_opening', {'opening': -3, 'rows': []}),
            ('zero_delta', {'opening': 2, 'rows': _rows({'time': 0, 'delta': 0})}),
            ('opening_in_minimum', {'opening': 5, 'rows': _rows({'time': 0, 'delta': 3}, {'time': 1, 'delta': 2})}),
            ('negative_then_recover', {'opening': -2, 'rows': _rows({'time': 1, 'delta': 4}, {'time': 0, 'delta': -3})})],
        'aggregation.interval_union': [
            ('empty_intervals', {'rows': []}),
            ('touching_intervals', {'rows': _rows({'start': 0, 'end': 2}, {'start': 2, 'end': 5})}),
            ('negative_overlapping_intervals', {'rows': _rows({'start': -4, 'end': 1}, {'start': -1, 'end': 3})}),
            ('gap_not_covered', {'rows': _rows({'start': 0, 'end': 1}, {'start': 3, 'end': 4})})],
        'aggregation.weighted_histogram': [
            ('empty_histogram', {'bounds': [0, 2], 'rows': []}),
            ('zero_weight_still_counted', {'bounds': [0, 2], 'rows': _rows({'value': 0, 'weight': 0})}),
            ('maximum_boundary_is_outside', {'bounds': [0, 2, 4], 'rows': _rows({'value': 4, 'weight': 3}, {'value': 2, 'weight': 1})}),
            ('weights_not_counts_unsorted_bounds', {'bounds': [4, 0, 2], 'rows': _rows({'value': -1, 'weight': 2}, {'value': 1, 'weight': 3})})],
        'graph.shortest_paths': [
            ('singleton_start', {'nodes': ['a'], 'start': 'a', 'edges': []}),
            ('unreachable_node', {'nodes': ['a', 'b', 'c'], 'start': 'a', 'edges': _edges(('a', 'b', 2))}),
            ('cheaper_indirect_path', {'nodes': ['a', 'b', 'c'], 'start': 'a', 'edges': _edges(('a', 'c', 9), ('b', 'c', 2), ('a', 'b', 2))}),
            ('edge_direction_matters', {'nodes': ['a', 'b'], 'start': 'a', 'edges': _edges(('b', 'a', 1))})],
        'graph.components': [
            ('empty_nodes', {'nodes': [], 'edges': []}),
            ('singleton_component', {'nodes': ['a'], 'edges': []}),
            ('isolated_node_included', {'nodes': ['a', 'b', 'c'], 'edges': _edges(('a', 'b'))}),
            ('transitive_connectivity', {'nodes': ['a', 'b', 'c', 'd'], 'edges': _edges(('c', 'd'), ('b', 'c'), ('a', 'b'))})],
        'graph.topo_layers': [
            ('empty_dag', {'nodes': [], 'edges': []}),
            ('isolated_source_included', {'nodes': ['a', 'b', 'c'], 'edges': _edges(('a', 'b'))}),
            ('longest_path_not_indegree', {'nodes': ['a', 'b', 'c', 'd'], 'edges': _edges(('c', 'd'), ('b', 'c'), ('a', 'b'))}),
            ('multiple_sources', {'nodes': ['a', 'b', 'c'], 'edges': _edges(('a', 'c'), ('b', 'c'))})],
        'graph.triangle_counts': [
            ('empty_graph', {'nodes': [], 'edges': []}),
            ('open_wedge_not_triangle', {'nodes': ['a', 'b', 'c'], 'edges': _edges(('a', 'b'), ('b', 'c'))}),
            ('triangle_with_isolated_node', {'nodes': ['a', 'b', 'c', 'd'], 'edges': _edges(('a', 'b'), ('a', 'c'), ('b', 'c'))}),
            ('shared_edge_two_triangles', {'nodes': ['a', 'b', 'c', 'd'], 'edges': _edges(('a', 'b'), ('a', 'c'), ('b', 'c'), ('a', 'd'), ('b', 'd'))})],
        'reports.stock_reconciliation': [
            ('unmoved_item_included', {'items': [{'id': 'x', 'opening': 4, 'minimum': 2}], 'rows': []}),
            ('exact_minimum_is_low', {'items': [{'id': 'x', 'opening': 5, 'minimum': 2}], 'rows': _rows({'item': 'x', 'delta': -3})}),
            ('signed_opening_and_movement', {'items': [{'id': 'x', 'opening': -2, 'minimum': 0}], 'rows': _rows({'item': 'x', 'delta': 4})}),
            ('movements_stay_with_item', {'items': [{'id': 'x', 'opening': 2, 'minimum': 0}, {'id': 'y', 'opening': 5, 'minimum': 1}], 'rows': _rows({'item': 'x', 'delta': -2}, {'item': 'y', 'delta': 2})})],
        'reports.invoice_balances': [
            ('unpaid_invoice_included', {'invoices': [{'id': 'x', 'amount': 4}], 'rows': []}),
            ('separate_debt_and_credit', {'invoices': [{'id': 'x', 'amount': 5}, {'id': 'y', 'amount': 5}], 'rows': _rows({'invoice': 'x', 'amount': 10})}),
            ('zero_invoice_zero_payment', {'invoices': [{'id': 'x', 'amount': 0}], 'rows': _rows({'invoice': 'x', 'amount': 0})}),
            ('multiple_payments_per_invoice', {'invoices': [{'id': 'x', 'amount': 5}, {'id': 'y', 'amount': 7}], 'rows': _rows({'invoice': 'x', 'amount': 2}, {'invoice': 'x', 'amount': 4}, {'invoice': 'y', 'amount': 3})})],
        'reports.department_payroll': [
            ('empty_payroll', {'rows': []}),
            ('zero_hours_bonus_payable', {'rows': _rows({'department': 'x', 'hours': 0, 'rate': 4, 'bonus': 3})}),
            ('zero_rate_bonus_payable', {'rows': _rows({'department': 'x', 'hours': 2, 'rate': 0, 'bonus': 3})}),
            ('departments_reconcile_separately', {'rows': _rows({'department': 'x', 'hours': 2, 'rate': 4, 'bonus': 1}, {'department': 'y', 'hours': 1, 'rate': 2, 'bonus': 0})})],
        'reports.sensor_audit': [
            ('unread_sensor_included', {'sensors': [{'id': 'x', 'low': 0, 'high': 2}], 'rows': []}),
            ('zero_width_band_is_valid', {'sensors': [{'id': 'x', 'low': 2, 'high': 2}], 'rows': _rows({'sensor': 'x', 'value': 2})}),
            ('both_endpoints_inclusive', {'sensors': [{'id': 'x', 'low': 0, 'high': 2}], 'rows': _rows({'sensor': 'x', 'value': 0}, {'sensor': 'x', 'value': 2})}),
            ('deviation_stays_with_sensor', {'sensors': [{'id': 'x', 'low': 0, 'high': 2}, {'id': 'y', 'low': -2, 'high': 0}], 'rows': _rows({'sensor': 'x', 'value': -1}, {'sensor': 'y', 'value': 2})})],
        'service.stock_allocation': [
            ('empty_orders', {'stock': 0, 'rows': []}),
            ('exact_stock', {'stock': 2, 'rows': _rows({'priority': 2, 'qty': 2})}),
            ('oversized_order_does_not_block_later', {'stock': 2, 'rows': _rows({'priority': 3, 'qty': 3}, {'priority': 2, 'qty': 2})}),
            ('priority_objective_not_smallest_first', {'stock': 3, 'rows': _rows({'priority': 2, 'qty': 3}, {'priority': 1, 'qty': 1}, {'priority': 1, 'qty': 2})})],
        'service.invoice_batch': [
            ('empty_batch', {'rows': []}),
            ('zero_quantity_is_valid', {'rows': _rows({'qty': 0, 'price': 3, 'tax_bps': 5000})}),
            ('round_per_invoice', {'rows': _rows({'qty': 1, 'price': 1, 'tax_bps': 5000}, {'qty': 1, 'price': 1, 'tax_bps': 5000})}),
            ('zero_tax_is_valid', {'rows': _rows({'qty': 2, 'price': 3, 'tax_bps': 0})})],
        'service.quota_schedule': [
            ('empty_schedule', {'rows': []}),
            ('finish_exactly_due', {'rows': _rows({'duration': 2, 'due': 2})}),
            ('zero_due_is_valid', {'rows': _rows({'duration': 2, 'due': 0})}),
            ('sum_lateness_across_jobs', {'rows': _rows({'duration': 3, 'due': 1}, {'duration': 2, 'due': 1})})],
        'service.refund_batch': [
            ('empty_refunds', {'rows': []}),
            ('zero_entitlement_excluded', {'rows': _rows({'paid': 5, 'used': 3, 'fee': 2})}),
            ('negative_entitlement_clamped', {'rows': _rows({'paid': 1, 'used': 3, 'fee': 0}, {'paid': 8, 'used': 2, 'fee': 1})}),
            ('zero_payment_valid', {'rows': _rows({'paid': 0, 'used': 0, 'fee': 0})})],
    }


def _parameter_variant(value):
    if isinstance(value, dict):
        return {key: _parameter_variant(item) if key != 'tax_bps' else item for key, item in value.items()}
    if isinstance(value, list):
        return [_parameter_variant(item) for item in value]
    if type(value) is int:
        return value * 3
    if isinstance(value, str):
        return 'final_' + value
    return value


def _case(template, group, index, data, principle, seed=None):
    expected = oracle(template, data)
    return {'case_id': f'{template}/{group}/{index:02d}', 'principle': principle,
            'seed': seed, 'data': deepcopy(data), 'expected': expected,
            'data_sha256': digest(data), 'expected_sha256': digest(expected)}


def challenge_cases(template, *, final_variant=False):
    group = 'final_parameterized' if final_variant else 'semantic_challenge'
    return [_case(template, group, i, _parameter_variant(data) if final_variant else data, principle)
            for i, (principle, data) in enumerate(declarative_examples()[template])]


ASSUMPTIONS = {
    'aggregation.group_totals': ("any([r['qty'] == 0 for r in data['rows']])", 'quantity_must_be_positive'),
    'aggregation.running_balance': ("data['opening'] < 0", 'opening_balance_must_be_nonnegative'),
    'aggregation.interval_union': ("any([r['start'] < 0 for r in data['rows']])", 'coordinates_must_be_nonnegative'),
    'aggregation.weighted_histogram': ("any([r['weight'] == 0 for r in data['rows']])", 'weight_must_be_positive'),
    'graph.shortest_paths': ("any([all([e['u'] != n and e['v'] != n for e in data['edges']]) for n in data['nodes']])", 'isolated_nodes_forbidden'),
    'graph.components': ("any([len(c) == 1 for c in result['main']])", 'singleton_components_forbidden'),
    'graph.topo_layers': ("len(result['main']) > 0 and len(result['main'][0]) > 1", 'only_one_source_allowed'),
    'graph.triangle_counts': ("any([r['triangles'] == 0 for r in result['main']['nodes']])", 'every_node_must_belong_to_triangle'),
    'reports.stock_reconciliation': ("any([d['closing'] == i['minimum'] for d in result['detail'] for i in data['items'] if d['id'] == i['id']])", 'exact_minimum_forbidden'),
    'reports.invoice_balances': ("result['summary']['credit'] > 0", 'overpayment_forbidden'),
    'reports.department_payroll': ("any([r['hours'] == 0 for r in data['rows']])", 'hours_must_be_positive'),
    'reports.sensor_audit': ("any([s['low'] == s['high'] for s in data['sensors']])", 'sensor_band_must_have_positive_width'),
    'service.stock_allocation': ("result['main']['remaining'] == 0", 'positive_stock_reserve_required'),
    'service.invoice_batch': ("any([r['tax_bps'] == 0 for r in data['rows']])", 'tax_rate_must_be_positive'),
    'service.quota_schedule': ("any([r['due'] == 0 for r in data['rows']])", 'deadline_must_be_positive'),
    'service.refund_batch': ("any([r['paid'] < r['used'] + r['fee'] for r in data['rows']])", 'negative_raw_entitlement_forbidden'),
}


RELATION_REPLACEMENTS = {
    'aggregation.group_totals': ("r['qty'] * r['price'] - r['discount']", "r['qty'] * (r['price'] - r['discount'])", 'discount_per_unit'),
    'aggregation.running_balance': ('lowest = balance', 'lowest = 1000000000', 'minimum_excludes_opening'),
    'aggregation.weighted_histogram': ("sum([r['weight'] for r in rows])", 'len(rows)', 'weights_confused_with_counts'),
    'graph.components': ("range(len(data['nodes']))", 'range(1)', 'one_pass_connectivity'),
    'graph.topo_layers': ("range(len(data['nodes']))", 'range(1)', 'one_pass_dependency_depth'),
    'graph.triangle_counts': ("b < c and [a, c] in pairs and [b, c] in pairs", "b < c and ([a, c] in pairs or [b, c] in pairs)", 'open_wedges_counted_as_triangles'),
    'reports.stock_reconciliation': ("if r['item'] == item['id']", '', 'global_movements_applied_to_each_item'),
    'reports.department_payroll': ("row['hours'] * row['rate'] + row['bonus']", "row['hours'] * (row['rate'] + row['bonus'])", 'bonus_per_hour'),
    'reports.sensor_audit': ("if r['sensor'] == sensor['id']", '', 'global_readings_in_each_sensor_summary'),
    'service.stock_allocation': ("[-r['priority'], r['id']]", "[r['qty'], r['id']]", 'smallest_order_objective'),
    'service.quota_schedule': ("sum([r['late'] for r in slots])", "max([0] + [r['late'] for r in slots])", 'maximum_instead_of_total_lateness'),
    'service.refund_batch': ("row['paid'] - row['used'] - row['fee']", "row['paid'] - row['used']", 'fee_omitted_from_entitlement'),
}


def programs(template):
    """New concrete recipes; broad categories can overlap the core taxonomy."""
    correct = solver(template)
    result = []

    def add(code, family, stratum, description, applicable=True):
        result.append({'program_id': f'{template}/{family}', 'kind': 'correct' if family == 'correct' else 'mutant',
            'family': family, 'stratum': stratum, 'description': description,
            'applicable': applicable, 'code': code, 'code_sha256': code_digest(code)})

    add(correct, 'correct', 'correct_control', 'Unchanged bounded reference solver')
    field = 'edges' if structure(template) == 'graph' else 'rows'
    add(correct + f"if len(data[{field!r}]) == 0:\n    stop('NONEMPTY_ASSUMPTION')\n",
        'nonempty_assumption', 'anticipated_assumptions', 'Reject a valid empty record/edge collection')
    predicate, description = ASSUMPTIONS[template]
    add(correct + f"if {predicate}:\n    stop('EXTRA_DOMAIN_ASSUMPTION')\n",
        'domain_assumption', 'anticipated_assumptions', description)
    if template in RELATION_REPLACEMENTS:
        before, after, description = RELATION_REPLACEMENTS[template]
        applicable = correct.count(before) == 1
        relation = correct.replace(before, after, 1) if applicable else correct
    else:
        applicable = True
        if template == 'aggregation.interval_union':
            description = 'bounding_span_includes_gaps'
            relation = correct + "span = max([r['end'] for r in data['rows']]) - min([r['start'] for r in data['rows']]) if len(data['rows']) > 0 else 0\nresult = putmap(result, 'main', putmap(result['main'], 'covered', span))\n"
        elif template == 'graph.shortest_paths':
            description = 'directed_edges_treated_as_undirected'
            first, rest = correct.split('\n', 1)
            relation = first + "\ndata = putmap(data, 'edges', data['edges'] + [{'u': e['v'], 'v': e['u'], 'weight': e['weight']} for e in data['edges']])\n" + rest
        elif template == 'reports.invoice_balances':
            description = 'cross_invoice_credit_nets_debt'
            relation = correct + "pooled_due = max(result['summary']['amount'] - result['summary']['paid'], 0)\nresult = putmap(result, 'summary', putmap(result['summary'], 'due', pooled_due))\n"
        elif template == 'service.invoice_batch':
            description = 'round_tax_once_for_batch'
            relation = correct + "batch_tax = sum([r['qty'] * r['price'] * r['tax_bps'] for r in data['rows']]) // 10000\ncharge = sum([r['subtotal'] for r in result['main']['invoices']]) + batch_tax\nresult = putmap(result, 'main', putmap(result['main'], 'total_charge', charge))\n"
        else:
            raise AssertionError(template)
    add(relation, 'semantic_relation', 'exploratory_transfer', description, applicable)
    return result


def supplement_hashes():
    return {**source_hashes(), 'semantic_validation_followup.py':
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def build_definition():
    # Materialize the entire input strategy before constructing any mutants.
    cases = {}
    for template in TEMPLATES:
        validation = [_case(template, 'random', i, instance(template, seed), 'ordinary_generator', seed)
                      for i, seed in enumerate(range(6001, 6005))]
        challenges = challenge_cases(template)
        final_random = [_case(template, 'final_random', i, instance(template, seed), 'fresh_random_seed', seed)
                        for i, seed in enumerate(range(7001, 7009))]
        final_random += [_case(template, 'final_random_scale', i, instance(template, seed, scale=True), 'fresh_scale_seed', seed)
                         for i, seed in enumerate(range(7101, 7105))]
        final_challenge = challenge_cases(template, final_variant=True)
        seen = {case['data_sha256'] for case in validation + challenges}
        for case in final_random + final_challenge:
            case['exact_validation_input_overlap'] = case['data_sha256'] in seen
        cases[template] = {'random': validation, 'semantic_challenge': challenges,
                           'final_random': final_random, 'final_parameterized': final_challenge}
    return {'schema': 'rm15-semantic-followup-v1', 'exploratory': True, 'confirmatory': False,
        'templates': list(TEMPLATES), 'source_hashes': supplement_hashes(),
        'specifications': {t: specification(t) for t in TEMPLATES},
        'structures': {t: structure(t) for t in TEMPLATES}, 'cases': cases,
        'programs': {t: programs(t) for t in TEMPLATES},
        'protocol': {
            'core_relationship': 'Separate exploratory supplement after observing the frozen core generic-strategy comparison; core unchanged.',
            'strategy_generation': 'Four declarative valid-domain examples per template, fixed before candidate execution; no mutant evaluation chooses cases.',
            'developer_knowledge': 'Challenge designer and mutant author share knowledge of specifications and intended unsupported assumptions.',
            'transfer_stratum': 'Semantic relationship recipes are reported separately from anticipated assumption guards; not blind or natural-error holdout.',
            'mutation_relationship': 'All concrete recipes differ from the six core recipes; broad mechanism categories can overlap.',
            'random_seeds': [6001, 6002, 6003, 6004], 'tests_per_strategy': 4,
            'final_random_seeds': list(range(7001, 7009)), 'final_scale_seeds': list(range(7101, 7105)),
            'final_parameterization': 'Multiply integer values by 3 except tax_bps; prefix string values final_. Empty cases may exactly overlap and are flagged.',
            'step_limit_per_trial': 50000, 'first_failure_cost': 'Prefix through first observed semantic defect; every suite still executes all cases.',
            'budget_curve': [1000, 5000, 20000, 50000],
            'wall_time': 'Observed timings separate from deterministic logical outcomes; includes evaluator setup and native oracle calls.',
            'oracle_cost': 'Native oracle work is not isolated or charged in logical-step counters.',
            'no_api': True, 'no_formal_api_candidates': True}}


def freeze(folder, definition):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    metadata = {'schema': 'rm15-semantic-followup-freeze-v1', 'exploratory': True,
                'contains_outcomes': False, 'definition_sha256': digest(definition),
                'source_hashes': definition['source_hashes']}
    files = {'frozen_definition.json': definition, 'freeze_metadata.json': metadata}
    for name, value in files.items():
        path = folder / name
        if path.exists() and path.read_bytes() != canonical_bytes(value):
            raise RuntimeError('Supplement definition changed; preserve frozen results and choose a new folder: ' + str(path))
    for name, value in files.items():
        (folder / name).write_bytes(canonical_bytes(value))
    return metadata


def _row(template, program, runs):
    all_trials = [trial for trials in runs.values() for trial in trials]
    finals = runs['final_random'] + runs['final_parameterized']
    demonstrated = program['kind'] == 'mutant' and any(trial['defect_detected'] for trial in all_trials)
    empirical = ('correct_control' if program['kind'] == 'correct' else
                 'structurally_inapplicable_identity' if not program['applicable'] else
                 'counterexample_observed' if demonstrated else 'no_counterexample_observed')
    return {key: deepcopy(program[key]) for key in ('program_id', 'kind', 'family', 'stratum', 'applicable', 'description')} | {
        'template': template, 'structure': structure(template),
        'empirically_non_equivalent': demonstrated, 'empirical_status': empirical,
        'final_failed': any(not trial['passed'] for trial in finals),
        'final_partitions': {suite: {'cases': len(runs[suite]),
            'failed': any(not t['passed'] for t in runs[suite]),
            'semantic_failure_cases': sum(t['defect_detected'] for t in runs[suite]),
            'resource_failure_cases': sum(t['resource_exhausted'] for t in runs[suite])}
            for suite in ('final_random', 'final_parameterized')},
        'validation': {s: suite_status(runs[s]) for s in STRATEGIES},
        'curves': {s: {**{f'cases_{n}': suite_status(runs[s][:n]) for n in range(1, 5)},
                       **{f'steps_{n}': suite_status(runs[s], budget=n) for n in (1000, 5000, 20000, 50000)}}
                   for s in STRATEGIES}}


def summarize(definition, rows, trials, metadata):
    mutants = [row for row in rows if row['kind'] == 'mutant']
    groups = {'all': rows}
    for field in ('stratum', 'family', 'template', 'structure'):
        for value in sorted({r[field] for r in mutants}):
            selected = [r for r in mutants if r[field] == value]
            templates = {r['template'] for r in selected}
            groups[f'{field}:{value}'] = selected + [r for r in rows if r['kind'] == 'correct' and r['template'] in templates]
    partitioned = {}
    for name, group in groups.items():
        partitioned[name] = {}
        for suite in ('final_random', 'final_parameterized'):
            partition_rows = [dict(row, final_failed=row['final_partitions'][suite]['failed']) for row in group]
            partitioned[name][suite] = {s: aggregate(partition_rows, s) for s in STRATEGIES}
    return {'schema': 'rm15-semantic-followup-summary-v1', 'exploratory': True, 'confirmatory': False,
        'freeze': metadata, 'templates': len(TEMPLATES), 'correct_programs': 16,
        'engineered_mutants': len(mutants),
        'empirically_non_equivalent': sum(r['empirically_non_equivalent'] for r in mutants),
        'status_counts': {status: sum(r['empirical_status'] == status for r in mutants)
                          for status in sorted({r['empirical_status'] for r in mutants})},
        'equal_count': {name: {s: aggregate(group, s) for s in STRATEGIES} for name, group in groups.items()},
        'final_partition_results': partitioned,
        'cost_curves': {s: {curve: aggregate(rows, s, curve=curve) for curve in
            [f'cases_{n}' for n in range(1, 5)] + [f'steps_{n}' for n in (1000, 5000, 20000, 50000)]} for s in STRATEGIES},
        'actual_work': {'executions': len(trials), 'charged_steps': sum(t['charged_steps'] for t in trials),
            'refused_ticks': sum(t['refused_ticks'] for t in trials),
            'validation_executions': sum(t['suite'] in STRATEGIES for t in trials),
            'final_executions': sum(t['suite'] not in STRATEGIES for t in trials),
            'curve_additional_executions': 0},
        'exact_final_input_overlap_count': sum(c['exact_validation_input_overlap'] for suites in definition['cases'].values()
            for name in ('final_random', 'final_parameterized') for c in suites[name]),
        'limitations': [
            'Exploratory follow-up was designed after the core comparison; it is not confirmatory or a replacement for core results.',
            'Common authorship and developer knowledge intentionally align valid semantic cases with anticipated unsupported assumptions.',
            'Concrete mutation recipes are new but broad defect categories overlap the core taxonomy.',
            'The semantic-relation stratum is an exploratory transfer diagnostic, not a blinded held-out population.',
            'Engineered mutants are not natural model errors; a favorable result would not establish directed testing as generally best.',
            'Fresh random seeds are independent of validation seeds; parameterized semantic finals reuse example structures and can exactly repeat empty cases.',
            'Semantic cases are much smaller than ordinary generated inputs; equal test count does not imply equal logical work or input diversity.',
            'Every mutant, including inapplicable or untriggered recipes, remains in the all-mutant denominator.',
            'The observed-counterexample denominator is conditional on this finite corpus and is not an equivalence proof.',
            'Native oracle cost is not isolated in logical counters; observed wall time includes setup and is machine dependent.',
            'The sixteen related templates and repeated mutants do not constitute independent inferential samples.',
            'No formal API candidate was inspected, no API calls were made, and effect correctness is outside this computational supplement.']}


def run(folder=None):
    folder = Path(folder) if folder else ROOT / 'results' / 'semantic_validation'
    started = time.perf_counter()
    definition = build_definition()
    prepared = time.perf_counter()
    metadata = freeze(folder, definition)
    trials, timings, rows = [], [], []
    cumulative = 0

    def evaluate(template, program):
        nonlocal cumulative
        suites = {}
        for suite, cases in definition['cases'][template].items():
            suites[suite] = []
            for case in cases:
                before = time.perf_counter()
                trial = evaluate_program(program['code'], template, case)
                elapsed = time.perf_counter() - before
                suites[suite].append(trial)
                cumulative += trial['charged_steps']
                trials.append({'program_id': program['program_id'], 'template': template,
                    'family': program['family'], 'suite': suite, **trial,
                    'cumulative_executions': len(trials) + 1, 'cumulative_charged_steps': cumulative})
                timings.append({'program_id': program['program_id'], 'case_id': case['case_id'],
                                'trial_wall_seconds_including_setup': elapsed})
        return suites

    # All controls pass before any mutant executes. Only definitions are left
    # behind if input-domain construction or a reference control fails.
    for template in TEMPLATES:
        correct = definition['programs'][template][0]
        suites = evaluate(template, correct)
        if any(not t['passed'] for ts in suites.values() for t in ts):
            raise RuntimeError('Correct-control construction failure: ' + template)
        rows.append(_row(template, correct, suites))
    for template in TEMPLATES:
        for program in definition['programs'][template][1:]:
            rows.append(_row(template, program, evaluate(template, program)))
    if supplement_hashes() != definition['source_hashes']:
        raise RuntimeError('Study source changed during execution; no results written')
    summary = summarize(definition, rows, trials, metadata)
    timing = {'exploratory': True, 'preparation_wall_seconds': prepared - started,
        'evaluation_and_analysis_wall_seconds': time.perf_counter() - prepared,
        'oracle_cost_isolated': False, 'trial_timings': timings}
    for name, value in [('trials.json', trials), ('program_summary.json', rows),
                        ('summary.json', summary), ('observed_timing.json', timing)]:
        (folder / name).write_bytes(canonical_bytes(value))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-folder', type=Path, default=ROOT / 'results' / 'semantic_validation')
    args = parser.parse_args()
    summary = run(args.output_folder)
    print(json.dumps({'exploratory': True, 'mutants': summary['engineered_mutants'],
        'equal_count': summary['equal_count']['all'], 'actual_work': summary['actual_work'],
        'summary': str(args.output_folder / 'summary.json')}, indent=2))


if __name__ == '__main__':
    main()
