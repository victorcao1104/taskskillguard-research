"""Paid atomic interpreter queries with conservative incremental judgments.

Selection receives only public input and a query catalog. No complete solver is
called here. Each consumed query constructs a fresh runtime machine; its result
is cached only after that paid invocation. Caches never cross evaluations.
"""
from copy import deepcopy
import json
import random

from .evidence_v7 import AXES
from .models_v3 import validate_record
from .protocol_v7 import SYSTEM, payload as base_payload
from .runtime_v6 import STEP_LIMIT, _Machine, _goal, _validate, candidates, edges, parse_source


QUERY_VIEWS = ('Q0', 'Q1')
BUDGETS = (2, 4, 8, 'full')


def _graph_flag(graph):
    if type(graph) is bool:
        return graph
    if graph in QUERY_VIEWS:
        return graph == 'Q1'
    raise ValueError('UNKNOWN_QUERY_VIEW')


def query_catalog(case):
    """Public one-run queries. c-indexes follow static source candidate order."""
    sites = candidates(parse_source(case['source']))
    return [query for wi in range(len(case['worlds'])) for query in (
        [{'id': f'b{wi}r{ri}', 'kind': 'base', 'world': wi, 'route': ri}
         for ri in range(len(case['routes']) + 1)] +
        [{'id': f's{wi}c{si}', 'kind': 'suppress', 'world': wi, 'site': site['id']}
         for si, site in enumerate(sites)])]


def query_system(graph):
    present = _graph_flag(graph)
    base = SYSTEM.replace('Return one judgment per candidate ID. The three axes are independent.',
                          'The three diagnostic axes are independent.')
    instruction = '''
Your output is ONLY an order containing a PERMUTATION of ALL public query IDs.
Do not output facts, labels, reasoning, or extra IDs. Rank the atomic interpreter
queries to resolve as many candidate-axis labels as possible at prefixes of 2,
4 and 8 paid queries. A base query runs one world/route, reporting success and
the committed effect trace with grants. A suppress query runs the original from
that world's initial state suppressing all occurrences of one candidate site.
Every query costs one interpreter invocation; step costs are also recorded.
The original base query reveals activity, authorization, target identities and
baseline success for all candidates in that world. A suppression can resolve
current-route necessity when its original is active and successful. Successful
authorized route traces can witness an avoiding route; exhausting catalog routes
can prove no legal route or a closed-catalog necessity. Mixed per-world labels
prove intrinsic unknown. No truth labels or execution facts are supplied.
'''
    representation = ('\nThe payload also has graph: conservative static [producer,consumer,type] '
        'edges computed deterministically from source. It is another representation of the '
        'same source; it adds no observations or truth.' if present else '')
    return base + instruction + representation


def query_payload(case, nodes, graph):
    value = json.loads(base_payload(case, nodes))
    value['queries'] = query_catalog(case)
    if _graph_flag(graph):
        value['graph'] = edges(parse_source(case['source']))
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def query_schema(query_ids):
    return {'type': 'object', 'properties': {'order': {'type': 'array',
            'items': {'type': 'string', 'enum': list(query_ids)}}},
            'required': ['order'], 'additionalProperties': False}


def _valid_order(order, query_ids):
    return (isinstance(order, (list, tuple)) and all(type(item) is str for item in order)
            and len(order) == len(query_ids) and len(set(order)) == len(order)
            and set(order) == set(query_ids))


def parse_query(raw, query_ids):
    parsed = validate_record(raw, query_schema(query_ids))
    parsed['order'] = []
    if parsed['protocol_valid']:
        order = parsed['prediction']['order']
        if not _valid_order(order, query_ids):
            parsed['protocol_valid'] = False
            parsed['diagnostic_codes'].append('QUERY_PERMUTATION_MISMATCH')
        else:
            parsed['order'] = list(order)
    parsed['diagnostics'] = list(parsed['diagnostic_codes'])
    return parsed


def heuristic_order(case):
    """Fixed baseline-first, suppress-second, alternate-last public heuristic.

    Round-robin worlds within each stage avoids using any execution result to
    choose an order. Candidate source order breaks suppression ties.
    """
    queries = query_catalog(case)
    rank = {row['id']: index for index, row in enumerate(queries)}
    def priority(row):
        if row['kind'] == 'base' and row['route'] == 0:
            return (0, 0, row['world'])
        if row['kind'] == 'suppress':
            # IDs encode stable static candidate indexes, not their truth.
            return (1, int(row['id'].split('c')[1]), row['world'])
        return (2, row['route'], row['world'])
    return [row['id'] for row in sorted(queries, key=lambda row: (priority(row), rank[row['id']]))]


def random_order(case, seed):
    result = [row['id'] for row in query_catalog(case)]
    random.Random(seed).shuffle(result)
    return result


def _run_counted(program, world, goal, suppress=None):
    """runtime_v6.run_semantics semantics, retaining its actual entered steps."""
    machine = _Machine(world, STEP_LIMIT, reuse=False, enforce=False, suppress=suppress)
    try:
        error = machine.run(_validate(program))
    except (ValueError, TypeError, RecursionError):
        error = 'parse_error'
    trace = [{key: event[key] for key in ('id', 'op', 'resource', 'value', 'authorized')}
             for event in machine.trace if event['committed']]
    return {'files': machine.files, 'emits': machine.emits, 'trace': trace,
            'goal': error is None and _goal(machine.files, machine.emits, goal), 'error': error,
            'interpreter_steps': machine.steps}


def _possible_world(case, wi, si, sid, cache):
    original = cache.get(f'b{wi}r0')
    closed = case['catalog_closed']
    cat_possibilities = {'yes', 'no', 'not_applicable'} if closed else {'unknown', 'no', 'not_applicable'}
    if original is None:
        return ({'yes', 'no', 'not_applicable'}, {'yes', 'no', 'not_applicable'}, cat_possibilities)
    target = [event for event in original['trace'] if event['id'] == sid]
    if not target:
        return ({'not_applicable'},) * 3
    authorization = {'yes' if all(event['authorized'] for event in target) else 'no'}
    suppression = cache.get(f's{wi}c{si}')
    current = ({'not_applicable'} if not original['goal'] else {'yes', 'no'} if suppression is None
               else {'no' if suppression['goal'] else 'yes'})
    identities = {(event['op'], event['resource']) for event in target}
    route_count = len(case['routes']) + 1
    observed = [cache[f'b{wi}r{ri}'] for ri in range(route_count) if f'b{wi}r{ri}' in cache]
    legal = [run for run in observed if run['goal'] and all(event['authorized'] for event in run['trace'])]
    avoiding = any(not identities.intersection((event['op'], event['resource']) for event in run['trace'])
                   for run in legal)
    if avoiding:
        catalog = {'no'}
    elif len(observed) == route_count:
        catalog = {'not_applicable' if not legal else 'yes' if closed else 'unknown'}
    else:
        catalog = {'yes', 'no'} if closed else {'unknown', 'no'}
        if not legal:
            catalog.add('not_applicable')
    return authorization, current, catalog


def _aggregate_possible(per_world):
    # A uniform label is possible iff every world permits it. Any two distinct
    # possible world labels also permit a mixed-world (intrinsic unknown) result.
    possible = set.intersection(*per_world)
    if len(per_world) > 1 and any(len(left | right) > 1
            for index, left in enumerate(per_world) for right in per_world[index + 1:]):
        possible.add('unknown')
    proven = len(possible) == 1
    label = next(iter(possible)) if proven else 'unknown'
    return {'label': label, 'proven': proven,
            'reason': ('intrinsic' if label == 'unknown' else 'observed') if proven else 'budget',
            'possible_labels': sorted(possible)}


def _reduce(case, sites, cache):
    decisions, by_id = {}, {}
    for si, site in enumerate(sites):
        sid = site['id']
        worlds = [_possible_world(case, wi, si, sid, cache) for wi in range(len(case['worlds']))]
        decisions[sid] = {axis: _aggregate_possible([world[ai] for world in worlds])
                         for ai, axis in enumerate(AXES)}
        by_id[sid] = {'id': sid, **{axis: decisions[sid][axis]['label'] for axis in AXES}}
    proven = {sid: {axis: row[axis]['proven'] for axis in AXES} for sid, row in decisions.items()}
    return {'by_id': by_id, 'labels': deepcopy(by_id), 'decisions': decisions, 'proven': proven,
            'resolved': sum(sum(row.values()) for row in proven.values()), 'total_labels': len(sites) * len(AXES),
            'intrinsic_unknown': sum(row[axis]['reason'] == 'intrinsic' for row in decisions.values() for axis in AXES)}


def evaluate_order(case, order, budget):
    """Execute exactly the allowed order prefix, then reduce only paid facts.

    budget='full' consumes the complete catalog, including interventions already
    unnecessary for a particular label. This is the counted full-solver benchmark,
    not free checked facts. Invalid orders execute zero queries and have no
    heuristic fallback. An integer budget is capped at the catalog size.
    """
    if budget != 'full' and (type(budget) is not int or budget < 0):
        raise ValueError('INVALID_QUERY_BUDGET')
    original = parse_source(case['source'])
    sites = candidates(original)
    if not case['worlds']:
        raise ValueError('EMPTY_WORLD_CATALOG')
    catalog = query_catalog(case)
    query_by_id = {row['id']: row for row in catalog}
    valid = _valid_order(order, query_by_id)
    limit = len(catalog) if budget == 'full' else min(budget, len(catalog))
    cache, trace, authorization_evidence = {}, [], {}
    steps = 0
    result = _reduce(case, sites, cache)
    for query_id in list(order or [])[:limit] if valid else []:
        query = query_by_id[query_id]
        wi = query['world']
        program = (original if query['kind'] == 'suppress' or query['route'] == 0
                   else case['routes'][query['route'] - 1])
        observation = _run_counted(program, case['worlds'][wi], case['goal'],
                                   suppress=query.get('site'))
        cache[query_id] = observation
        steps += observation['interpreter_steps']
        # Runtime authorization needs a completed original trace. Diagnostic
        # labels above intentionally retain the frozen committed-trace semantics
        # even when execution stops, but those labels are not handoff proofs.
        if query['kind'] == 'base' and query['route'] == 0 and observation['error'] is None:
            authorization_evidence[str(wi)] = []
            for site in sites:
                events = [event for event in observation['trace'] if event['id'] == site['id']]
                authorization_evidence[str(wi)].append({'id': site['id'], 'occurred': bool(events),
                    'all_occurrences_authorized': all(event['authorized'] for event in events)})
        result = _reduce(case, sites, cache)
        trace.append({**query, 'interpreter_steps': observation['interpreter_steps'],
                      'cumulative_steps': steps, 'executions': len(cache), 'resolved': result['resolved'],
                      'goal': observation['goal'], 'error': observation['error']})
    result.update(protocol_valid=valid, diagnostic_codes=[] if valid else ['QUERY_PERMUTATION_MISMATCH'],
                  executions=len(cache), interpreter_steps=steps, trace=trace, observations=cache,
                  authorization_evidence=authorization_evidence, budget=budget,
                  query_count=len(catalog), full_query_count=len(catalog), all_queries_executed=len(cache) == len(catalog),
                  first_fully_resolved_at=next((row['executions'] for row in trace
                      if row['resolved'] == result['total_labels']), None))
    result['diagnostics'] = list(result['diagnostic_codes'])
    return result
