"""Matched 2 x 2 facts/judgments records with two offline reducer levels.

The first view bit selects global-fact deduplication; the second selects an
exact-fact tool control. Reducer 0 and reducer 1 consume the SAME response.
No proposed observation is corrected using tool facts during parsing.
"""
from copy import deepcopy
import json

from .evidence_v7 import AXES, LABELS
from .models_v3 import validate_record
from .protocol_v7 import SYSTEM, payload as base_payload
from .protocol_v8 import aggregate, exact_facts


VIEWS = ('A00', 'A01', 'A10', 'A11')
SITE_FIELDS = ('occurred', 'all_occurrences_authorized', 'suppressed_success', 'avoiding_routes')
GLOBAL_FIELDS = ('baseline_success', 'legal_routes')
FACT_RULES = '''
Return BOTH proposed executable facts in worlds AND your own labels in judgments.
Each world occurs exactly once in ascending zero-based world order. Every world
contains sites with every candidate ID exactly once. judgments contains every
candidate ID exactly once and all three typed axes.
Facts: occurred; all_occurrences_authorized (true for an inactive site);
baseline_success (original route success); suppressed_success (original route
rerun from the same initial world with ALL occurrences of that site suppressed);
legal_routes (sorted indices of goal-successful fully authorized routes, original
index 0); avoiding_routes (sorted legal route indices avoiding ALL executed target
(op,resource) identities, [] if inactive). Do not invent route indices.
Derive your judgments from the proposed facts using the per-world rules and
across-world aggregation. Return only the requested schema JSON.
'''


def _view(view):
    if view not in VIEWS:
        raise ValueError('UNKNOWN_VIEW')
    return view[1] == '1', view[2] == '1'


def system(view):
    dedup, tool = _view(view)
    base = SYSTEM.replace('Return one judgment per candidate ID. The three axes are independent.',
                          'The three axes are independent.')
    if tool:
        base = base.replace('Public source, grants and goal are the only evidence.',
                            'Use public inputs and the supplied trusted execution facts.')
    placement = ('Store baseline_success and legal_routes ONCE on each world. '
                 'Do not duplicate these globals inside sites.' if dedup else
                 'Store baseline_success and legal_routes inside EVERY site row in each world. '
                 'These globals describe that same world and MUST agree across all its site rows.')
    extra = ('\nThe payload supplies tool_facts: exact execution observations from a complete '
             'finite interpreter solve. Use these observations for both proposed facts and '
             'judgments. This tool control has additional computation cost.' if tool else '')
    return base + FACT_RULES + placement + extra


def payload(case, nodes, view):
    _, tool = _view(view)
    value = json.loads(base_payload(case, nodes))
    if tool:
        value['tool_facts'] = exact_facts(case)[0]
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def schema(ids, view):
    dedup, _ = _view(view)
    def obj(properties):
        return {'type': 'object', 'properties': properties, 'required': list(properties),
                'additionalProperties': False}
    routes = {'type': 'array', 'items': {'type': 'integer'}}
    globals_ = {'baseline_success': {'type': 'boolean'}, 'legal_routes': routes}
    site = {'id': {'type': 'string', 'enum': list(ids)},
            **{name: {'type': 'boolean'} for name in SITE_FIELDS[:-1]}, 'avoiding_routes': routes}
    if not dedup:
        site.update(globals_)
    world = {'world': {'type': 'integer'}}
    if dedup:
        world.update(globals_)
    world['sites'] = {'type': 'array', 'items': obj(site)}
    judgment = {'id': {'type': 'string', 'enum': list(ids)},
                **{axis: {'type': 'string', 'enum': list(LABELS)} for axis in AXES}}
    return obj({'worlds': {'type': 'array', 'items': obj(world)},
                'judgments': {'type': 'array', 'items': obj(judgment)}})


def _coverage(rows, ids):
    actual = [row['id'] for row in rows]
    return len(actual) == len(set(actual)) and set(actual) == set(ids)


def parse_record(raw, ids, view, world_count, route_count, closed):
    """Validate shape, exact coverage, route bounds and redundant agreement.

    Well-formed but incorrect facts remain incorrect. Invalid records have empty
    judgment maps; raw prediction and diagnostic details remain available.
    """
    dedup, _ = _view(view)
    if type(world_count) is not int or world_count < 1 or type(route_count) is not int or route_count < 1:
        raise ValueError('INVALID_CATALOG_SIZE')
    parsed = validate_record(raw, schema(ids, view))
    parsed.update(by_id={}, reduced_by_id={}, normalized_facts=None,
                  redundancy_consistent=None if dedup else True, diagnostics=[])
    if not parsed['protocol_valid']:
        parsed['diagnostics'] = list(parsed['diagnostic_codes'])
        return parsed
    value = parsed['prediction']
    errors = []
    worlds = value['worlds']
    indexes = [world['world'] for world in worlds]
    if any(type(index) is not int for index in indexes) or indexes != list(range(world_count)):
        errors.append('WORLD_COVERAGE_MISMATCH')
    if not _coverage(value['judgments'], ids):
        errors.append('JUDGMENT_COVERAGE_MISMATCH')
    normalized = []
    for world in worlds:
        sites = world['sites']
        if not _coverage(sites, ids):
            errors.append('CANDIDATE_COVERAGE_MISMATCH')
        global_rows = [world] if dedup else sites
        if not dedup and not sites:
            errors.append('MISSING_GLOBAL_FACTS')
        if not dedup and sites and any(
                any(site[field] != sites[0][field] for field in GLOBAL_FIELDS) for site in sites[1:]):
            errors.append('REDUNDANCY_INCONSISTENT')
            parsed['redundancy_consistent'] = False
        for routes in [row['legal_routes'] for row in global_rows] + [site['avoiding_routes'] for site in sites]:
            if (any(type(index) is not int or not 0 <= index < route_count for index in routes)
                    or routes != sorted(set(routes))):
                errors.append('ROUTE_INDEX_MISMATCH')
        if global_rows:
            normalized.append({'world': world['world'],
                **{field: deepcopy(global_rows[0][field]) for field in GLOBAL_FIELDS},
                'sites': [{'id': site['id'], **{field: deepcopy(site[field]) for field in SITE_FIELDS}}
                          for site in sites]})
    if errors:
        parsed['protocol_valid'] = False
        parsed['diagnostic_codes'].extend(sorted(set(errors)))
    else:
        parsed['normalized_facts'] = {'worlds': normalized}
        parsed['by_id'] = {row['id']: deepcopy(row) for row in value['judgments']}
        parsed['reduced_by_id'] = aggregate(parsed['normalized_facts'], closed)
    parsed['diagnostics'] = list(parsed['diagnostic_codes'])
    return parsed
