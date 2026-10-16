"""Incremental, paid atomic queries and strict public selection protocols.

Only consume() invokes an interpreter. Reduction and stopping use cached paid
observations, retaining the frozen v9 diagnostic semantics and handoff boundary.
"""
from copy import deepcopy
import json

from .models_v3 import validate_record
from .protocol_v7 import payload as base_payload
from .query_v9 import _reduce, _run_counted, query_catalog, query_system
from .runtime_v6 import candidates, edges, parse_source


PROTOCOLS = ('full', 'batch', 'next')
OBJECTIVES = ('diagnostic', 'execution')
REPRESENTATIONS = ('source', 'graph', 'padding')
STOP_MODES = ('fixed', 'diagnostic', 'authorization')


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _ids(value, *, empty=True):
    return (isinstance(value, (list, tuple)) and (empty or bool(value))
            and all(type(item) is str for item in value) and len(set(value)) == len(value))


def _configuration(protocol, objective='diagnostic', limit=None):
    if protocol not in PROTOCOLS:
        raise ValueError('UNKNOWN_QUERY_PROTOCOL')
    if objective not in OBJECTIVES:
        raise ValueError('UNKNOWN_QUERY_OBJECTIVE')
    if limit is not None and (type(limit) is not int or limit < 1 or (protocol == 'batch' and limit > 4)):
        raise ValueError('INVALID_SELECTION_LIMIT')


def selection_system(protocol, objective):
    """The same workflow semantics with a protocol and objective instruction."""
    _configuration(protocol, objective)
    # Preserve the frozen semantic definitions, replacing its permutation-only
    # selection instruction rather than presenting conflicting output formats.
    semantic = query_system(False).split('\nYour output is ONLY an order')[0]
    output = {
        'full': 'Return ONLY {"order":[...]}: a permutation of ALL remaining_ids.',
        'batch': 'Return ONLY {"queries":[...]}: 1..the requested limit unique remaining_ids (at most 4).',
        'next': 'Return ONLY {"query_id":"..."}: one remaining ID.',
    }[protocol]
    objective_text = (
        'Prioritize resolving the independent diagnostic labels across candidates and worlds; '
        'mixed per-world labels can prove intrinsic unknown.' if objective == 'diagnostic' else
        'Prioritize completed original authorization evidence for EVERY public world. '
        'Only a base query at route 0 with error null supplies this handoff evidence. '
        'A global authorization label, suppression, alternate route, or incomplete original is insufficient.'
    )
    return semantic + '\n' + output + '\n' + objective_text + '''
Every selected ID costs one fresh interpreter invocation; entered steps are counted.
Use only public source, routes, worlds, goals and already paid observations. Base
queries run a world/route. Suppress queries run the original suppressing every
occurrence of one site. Do not repeat consumed IDs or invent IDs. No truth or
future facts are supplied. A graph is a deterministic static source representation.
Representation kind padding is explicitly inert; its content is not evidence.
Return no labels, reasons, extra fields or fallback selections.
'''


def selection_payload(case, remaining_ids, observations, protocol, objective, representation='source'):
    """Serialize public inputs and paid facts; never read private case fields."""
    _configuration(protocol, objective)
    if representation not in REPRESENTATIONS:
        raise ValueError('UNKNOWN_QUERY_REPRESENTATION')
    original = parse_source(case['source'])
    sites = candidates(original)
    catalog = query_catalog(case)
    catalog_ids = {q['id'] for q in catalog}
    if not _ids(remaining_ids) or not set(remaining_ids) <= catalog_ids:
        raise ValueError('INVALID_REMAINING_IDS')
    if not isinstance(observations, dict) or not set(observations) <= catalog_ids - set(remaining_ids):
        raise ValueError('INVALID_PAID_OBSERVATIONS')
    value = json.loads(base_payload(case, sites))
    value.update(queries=[q for q in catalog if q['id'] in remaining_ids],
                 remaining_ids=list(remaining_ids), observations=deepcopy(observations),
                 protocol=protocol, objective=objective)
    if representation == 'source':
        return _dump(value)
    value['representation'] = {'kind': 'graph', 'edges': edges(original),
                               'note': 'Static source representation, not observations.'}
    graph = _dump(value)
    if representation == 'graph':
        return graph
    value['representation'] = {'kind': 'padding', 'inert': '', 'note': 'Inert padding.'}
    length = len(graph) - len(_dump(value))
    value['representation']['inert'] = '.' * length
    return _dump(value)


def selection_schema(remaining_ids, protocol, limit):
    """Strict JSON shape, including uniqueness and full/bounded cardinality."""
    if limit is None:
        raise ValueError('INVALID_SELECTION_LIMIT')
    _configuration(protocol, limit=limit)
    if not _ids(remaining_ids):
        raise ValueError('INVALID_REMAINING_IDS')
    item = {'type': 'string', 'enum': list(remaining_ids)}
    if protocol == 'next':
        field, specification = 'query_id', item
    else:
        field = 'order' if protocol == 'full' else 'queries'
        minimum = len(remaining_ids) if protocol == 'full' else 1
        maximum = len(remaining_ids) if protocol == 'full' else min(limit, len(remaining_ids))
        specification = {'type': 'array', 'items': item, 'minItems': minimum,
                         'maxItems': maximum, 'uniqueItems': True}
    return {'type': 'object', 'properties': {field: specification},
            'required': [field], 'additionalProperties': False}


def parse_selection(raw, remaining_ids, protocol, limit):
    """Preserve invalid evidence without repair, fallback, or hidden evaluation."""
    parsed = validate_record(raw, selection_schema(remaining_ids, protocol, limit))
    parsed['selected_ids'] = []
    if parsed['protocol_valid']:
        prediction = parsed['prediction']
        selected = ([prediction['query_id']] if protocol == 'next' else
                    prediction['order' if protocol == 'full' else 'queries'])
        if not selected:
            parsed['protocol_valid'] = False
            parsed['diagnostic_codes'].append('EMPTY_QUERY_SELECTION')
        else:
            parsed['selected_ids'] = list(selected)
    parsed['diagnostics'] = list(parsed['diagnostic_codes'])
    return parsed


class QuerySession:
    """Own a fresh paid cache. Returned values are independent snapshots."""

    def __init__(self, case):
        self._case = deepcopy({key: case[key] for key in
                               ('source', 'routes', 'worlds', 'goal', 'catalog_closed')})
        if not self._case['worlds']:
            raise ValueError('EMPTY_WORLD_CATALOG')
        self._original = parse_source(self._case['source'])
        self._sites = candidates(self._original)
        self._catalog = query_catalog(self._case)
        self._queries = {q['id']: q for q in self._catalog}
        self._cache, self._trace, self._authorization = {}, [], {}
        self._steps = 0
        self._reduced = _reduce(self._case, self._sites, self._cache)

    @property
    def remaining_ids(self):
        return [q['id'] for q in self._catalog if q['id'] not in self._cache]

    @property
    def observations(self):
        return deepcopy(self._cache)

    def consume(self, ids):
        """Validate atomically, then buy each selected run once, in given order."""
        if not _ids(ids, empty=False) or not set(ids) <= set(self.remaining_ids):
            raise ValueError('INVALID_QUERY_SELECTION')
        for query_id in ids:
            query = self._queries[query_id]
            wi = query['world']
            program = (self._original if query['kind'] == 'suppress' or query['route'] == 0
                       else self._case['routes'][query['route'] - 1])
            observation = _run_counted(program, self._case['worlds'][wi], self._case['goal'],
                                       suppress=query.get('site'))
            self._cache[query_id] = observation
            self._steps += observation['interpreter_steps']
            if query['kind'] == 'base' and query['route'] == 0 and observation['error'] is None:
                facts = []
                for site in self._sites:
                    events = [e for e in observation['trace'] if e['id'] == site['id']]
                    facts.append({'id': site['id'], 'occurred': bool(events),
                                  'all_occurrences_authorized': all(e['authorized'] for e in events)})
                self._authorization[str(wi)] = facts
            self._reduced = _reduce(self._case, self._sites, self._cache)
            self._trace.append({**query, 'interpreter_steps': observation['interpreter_steps'],
                                'cumulative_steps': self._steps, 'executions': len(self._cache),
                                'resolved': self._reduced['resolved'],
                                'goal': observation['goal'], 'error': observation['error']})
        return self.result()

    def stop_ready(self, mode):
        """Pure sufficient-evidence check. Fixed mode never stops early."""
        if mode not in STOP_MODES:
            raise ValueError('UNKNOWN_QUERY_STOP_MODE')
        if mode == 'fixed':
            return False
        if mode == 'diagnostic':
            return self._reduced['resolved'] == self._reduced['total_labels']
        return len(self._authorization) == len(self._case['worlds'])

    def result(self):
        result = deepcopy(self._reduced)
        count = len(self._cache)
        result.update(protocol_valid=True, diagnostic_codes=[], diagnostics=[], executions=count,
                      interpreter_steps=self._steps, trace=deepcopy(self._trace), observations=self.observations,
                      authorization_evidence=deepcopy(self._authorization), budget=count,
                      query_count=len(self._catalog), full_query_count=len(self._catalog),
                      all_queries_executed=count == len(self._catalog),
                      authorization_complete=self.stop_ready('authorization'),
                      completed_original_worlds=sorted(int(w) for w in self._authorization),
                      budget_unknown=result['total_labels'] - result['resolved'],
                      first_fully_resolved_at=next((q['executions'] for q in self._trace
                          if q['resolved'] == result['total_labels']), None))
        return result


def evaluate_stream(case, ids, budget, stop_mode='fixed'):
    """Actually stop buying a unique acquired stream at the evidence threshold.

    A partial/empty stream is valid. Invalid streams execute nothing and retain
    an explicit protocol failure; no baseline-first or other fallback is used.
    """
    if budget != 'full' and (type(budget) is not int or budget < 0):
        raise ValueError('INVALID_QUERY_BUDGET')
    if stop_mode not in STOP_MODES:
        raise ValueError('UNKNOWN_QUERY_STOP_MODE')
    session = QuerySession(case)
    valid = _ids(ids) and set(ids) <= set(session.remaining_ids)
    limit = (len(ids) if budget == 'full' else min(budget, len(ids))) if valid else 0
    stopped = False
    for query_id in list(ids)[:limit] if valid else []:
        if session.stop_ready(stop_mode):
            stopped = True
            break
        session.consume([query_id])
    result = session.result()
    result.update(protocol_valid=valid, diagnostic_codes=[] if valid else ['INVALID_QUERY_STREAM'],
                  budget=budget, requested_budget=budget, stop_mode=stop_mode,
                  stopped_early=stopped, stop_reason=stop_mode if stopped else
                  ('protocol_invalid' if not valid else 'budget' if limit < len(ids) else 'stream_exhausted'))
    result['diagnostics'] = list(result['diagnostic_codes'])
    return result
