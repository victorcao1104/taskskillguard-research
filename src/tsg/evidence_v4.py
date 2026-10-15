"""Provenance objects and bounded, outcome-independent evidence selection.

These are analysis records, never execution evidence or permission grants.
"""
from collections import defaultdict, deque
from copy import deepcopy
import hashlib
import json


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def make_node(file, start, end, operation, resource, summary, *, execution_role,
              analysis_kind, resource_status='unknown', evidence=None,
              effect_index=0, kind='CODE_ACTION', **extra):
    if not isinstance(file, str) or not file:
        raise ValueError('nonempty provenance file required')
    if type(start) is not int or type(end) is not int or start < 1 or end < start:
        raise ValueError('invalid source span')
    if execution_role not in {'source_code', 'example', 'instruction'}:
        raise ValueError('invalid execution role')
    if type(effect_index) is not int or effect_index < 0:
        raise ValueError('invalid effect index')
    if not all(isinstance(x, str) and x for x in (kind, operation, analysis_kind)):
        raise ValueError('kind/operation/analysis_kind must be nonempty strings')
    protected = {'id', 'provenance', 'invocation_proven', 'authorization_source',
                 'privilege_relevant', 'resource_evidence'}
    if protected & extra.keys():
        raise ValueError('cannot override evidence invariants')
    if not isinstance(resource, str):
        raise ValueError('resource must be a string; unknown is explicit')
    if resource_status == 'unknown':
        resource = 'unknown'
    elif resource == 'unknown' or not resource:
        raise ValueError('resolved resource must be nonempty')
    span = {'file': file, 'line_start': start, 'line_end': end}
    resource_evidence = deepcopy(evidence) if evidence is not None else ([span.copy()] if resource_status != 'unknown' else [])
    identity = [file, start, end, kind, operation, resource, execution_role,
                analysis_kind, str(summary), effect_index]
    return {'id': 'v4_' + _digest(identity)[:24], 'kind': kind, 'operation': operation,
            'resource': resource, 'resource_status': resource_status,
            'summary': str(summary), 'provenance': span,
            'execution_role': execution_role, 'analysis_kind': analysis_kind,
            'invocation_proven': False, 'authorization_source': False,
            'privilege_relevant': kind in {'CODE_ACTION', 'INSTRUCTION'},
            'resource_evidence': resource_evidence, **extra}


def select_graph(graph, max_actions=12, max_nodes=128, max_edges=256):
    """Stratify action selection, then retain predecessors before spare support.

    Selected actions and dependency-action nodes are distinct: the latter can
    appear in evidence without becoming additional model response targets.
    Every cap loss is explicit. A complete closure is only within this partial
    extraction, never a whole-program completeness guarantee.
    """
    if any(type(n) is not int or n < 0 for n in (max_actions, max_nodes, max_edges)):
        raise ValueError('caps must be nonnegative integers')
    nodes = graph.get('nodes', [])
    by_id = {n['id']: n for n in nodes}
    if len(by_id) != len(nodes):
        raise ValueError('duplicate node ID')
    edges = graph.get('edges', [])
    if any(e['source'] not in by_id or e['target'] not in by_id for e in edges):
        raise ValueError('dangling edge')
    candidates = [n for n in nodes if n.get('privilege_relevant', n.get('kind') == 'CODE_ACTION')]
    strata = defaultdict(list)
    for n in candidates:
        key = (n.get('execution_role', 'unknown'), n['operation'],
               'unknown' if n.get('resource_status', 'unknown') == 'unknown' else 'resolved')
        strata[key].append(n)
    # First rotate roles, then rotate operation/resolution strata within each
    # role. A role with many strata cannot consume the entire action cap.
    roles = defaultdict(deque)
    for k in sorted(strata):
        roles[k[0]].append(deque(sorted(strata[k], key=lambda n: _digest(n['id']))))
    chosen = []
    while roles and len(chosen) < min(max_actions, max_nodes):
        for role in sorted(list(roles)):
            if len(chosen) >= min(max_actions, max_nodes):
                break
            queue = roles[role].popleft()
            chosen.append(queue.popleft())
            if queue:
                roles[role].append(queue)
            if not roles[role]:
                del roles[role]
    chosen_ids = {n['id'] for n in chosen}
    predecessors = defaultdict(set)
    for e in edges:
        if e.get('type') != 'ORDER':
            predecessors[e['target']].add(e['source'])
    closure = set(chosen_ids)
    ordered_dependencies, pending = [], deque(sorted(chosen_ids))
    while pending:
        target = pending.popleft()
        for source in sorted(predecessors[target]):
            if source not in closure:
                closure.add(source)
                ordered_dependencies.append(source)
                pending.append(source)
    retained = list(n['id'] for n in chosen)
    retained.extend(ordered_dependencies[:max_nodes - len(retained)])
    spare = sorted(n['id'] for n in nodes if n['id'] not in set(retained) and not n.get('privilege_relevant', n.get('kind') == 'CODE_ACTION'))
    retained.extend(spare[:max_nodes - len(retained)])
    kept_ids = set(retained)
    eligible_edges = [e for e in edges if e['source'] in kept_ids and e['target'] in kept_ids]
    eligible_edges.sort(key=lambda e: (e.get('type') == 'ORDER', not(e['source'] in closure and e['target'] in closure), _digest(e)))
    kept_edges = eligible_edges[:max_edges]
    closure_edges = [e for e in edges if e.get('type') != 'ORDER' and e['source'] in closure and e['target'] in closure]
    kept_edge_digests = {_digest(e) for e in kept_edges}
    missing_dependency_edges = [e for e in closure_edges if _digest(e) not in kept_edge_digests]
    coverage = {
        'actions_total': len(candidates), 'actions_selected': len(chosen),
        'actions_omitted': len(candidates) - len(chosen),
        'action_ids_selected': [n['id'] for n in chosen],
        'graph_nodes_total': len(nodes), 'graph_nodes_selected': len(kept_ids),
        'graph_nodes_omitted': len(nodes) - len(kept_ids),
        'graph_edges_total': len(edges), 'graph_edges_selected': len(kept_edges),
        'graph_edges_omitted': len(edges) - len(kept_edges),
        'dependency_nodes_omitted': sorted(closure - kept_ids),
        'dependency_edges_omitted': missing_dependency_edges,
        'dependency_closure_complete': closure <= kept_ids and not missing_dependency_edges,
        'closure_scope': 'partial extracted non-ORDER dependencies only; source order is optional context',
        'selection': 'nested role-first round robin then operation/resolution; deterministic digest order; predecessor closure priority',
    }
    bounded = {**deepcopy(graph), 'nodes': [deepcopy(by_id[i]) for i in retained],
               'edges': deepcopy(kept_edges), 'selection_coverage': coverage}
    return bounded, deepcopy(chosen), coverage
