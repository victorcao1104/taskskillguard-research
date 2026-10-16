"""Factorized executable facts: global fields once, deterministic typed labels."""
import json
from .models_v3 import validate_record
from .protocol_v7 import SYSTEM, payload as base_payload, schema as direct_schema
from .evidence_v7 import AXES, LABELS, solve, labels_from_worlds

VIEWS = ('D', 'F', 'T')
FACTOR = '''
Output FACTS ONLY in worlds, one entry for every supplied world, in ascending world-index order. Do not output labels.
world is its zero-based index. Global facts occur ONCE: baseline_success is original goal success;
legal_routes is the sorted indices of successful fully authorized routes (original index0).
sites contains every candidate ID exactly once in every world. Candidate facts: occurred;
all_occurrences_authorized (true when inactive); suppressed_success (rerun original suppressing
all occurrences of this site from initial state); avoiding_routes (sorted legal indices avoiding
all executed target (op,resource) identities; [] if inactive). Do not invent route indices.
These facts are executable observations. A deterministic reducer will compute the three labels.
'''
TOOL = '''
The payload additionally includes tool_facts, exact trusted execution observations, produced by
a finite interpreter. Use these facts for the three labels instead of re-simulating the source.
Global baseline_success and legal_routes apply to ALL sites in that world. Every site has its
own occurred, all_occurrences_authorized, suppressed_success, avoiding_routes.
Apply the per-world rules and then aggregate across worlds; return labels only.
'''


def system(view):
    if view not in VIEWS: raise ValueError('UNKNOWN_VIEW')
    # F replaces only the requested output, preserving the underlying semantics.
    base = SYSTEM.replace('Return one judgment per candidate ID. The three axes are independent.',
                          'The three diagnostic axes are independent.') if view == 'F' else SYSTEM
    if view == 'T': base = base.replace('Public source, grants and goal are the only evidence.',
                                        'Use public inputs and the supplied trusted execution facts.')
    return base + (FACTOR if view == 'F' else TOOL if view == 'T' else '')


def exact_facts(case):
    result = solve(case)
    rows = result['judgments']
    worlds = []
    for wi in range(len(case['worlds'])):
        first = rows[0]['worlds'][wi]
        worlds.append({'world': wi, 'baseline_success': first['baseline_success'],
                       'legal_routes': first['legal_routes'],
                       'sites': [{'id': r['id'], **{k:r['worlds'][wi][k] for k in
                           ('occurred','all_occurrences_authorized','suppressed_success','avoiding_routes')}} for r in rows]})
    return {'worlds':worlds}, result['execution_count']


def payload(case, nodes, view):
    base=json.loads(base_payload(case,nodes))
    if view=='T': base['tool_facts']=exact_facts(case)[0]
    return json.dumps(base,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def schema(ids, view):
    if view != 'F': return direct_schema(ids,'B1')
    def obj(p): return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
    routes={'type':'array','items':{'type':'integer'}}
    site={'id':{'type':'string','enum':ids},
          **{k:{'type':'boolean'} for k in ('occurred','all_occurrences_authorized','suppressed_success')},
          'avoiding_routes':routes}
    world={'world':{'type':'integer'},'baseline_success':{'type':'boolean'},'legal_routes':routes,
           'sites':{'type':'array','items':obj(site)}}
    return obj({'worlds':{'type':'array','items':obj(world)}})


def aggregate(facts, closed):
    by_id={}
    for w in facts['worlds']:
        for s in w['sites']:
            by_id.setdefault(s['id'],[]).append({**s,'baseline_success':w['baseline_success'],
                                               'legal_routes':w['legal_routes']})
    return {sid:{'id':sid,**labels_from_worlds(ws,closed)} for sid,ws in by_id.items()}


def parse_record(raw, ids, view, world_count, route_count, closed):
    parsed=validate_record(raw,schema(ids,view))
    parsed['by_id']={}
    if not parsed['protocol_valid']: return parsed
    p=parsed['prediction']; errors=[]
    if view=='F':
        ws=p['worlds']; indexes=[w['world'] for w in ws]
        if any(type(i) is not int for i in indexes) or indexes != list(range(world_count)):
            errors.append('WORLD_COVERAGE_MISMATCH')
        for w in ws:
            actual=[s['id'] for s in w['sites']]
            if len(actual)!=len(set(actual)) or set(actual)!=set(ids): errors.append('CANDIDATE_COVERAGE_MISMATCH')
            for routes in [w['legal_routes'],*[s['avoiding_routes'] for s in w['sites']]]:
                if routes!=sorted(set(routes)) or any(type(r) is not int or not 0<=r<route_count for r in routes):
                    errors.append('ROUTE_INDEX_MISMATCH')
        if not errors: parsed['by_id']=aggregate(p,closed)
    else:
        actual=[s['id'] for s in p['judgments']]
        if len(actual)!=len(set(actual)) or set(actual)!=set(ids): errors.append('CANDIDATE_COVERAGE_MISMATCH')
        if not errors: parsed['by_id']={r['id']:r for r in p['judgments']}
    if errors:
        parsed['protocol_valid']=False
        parsed['diagnostic_codes'].extend(sorted(set(errors)))
    return parsed


def fact_errors(prediction, expected):
    """Compare well-formed facts without converting wrong facts into corrections."""
    errors={'global':[],'sites':[]}
    for pw,ew in zip(prediction['worlds'],expected['worlds']):
        wi=ew['world']
        for k in ('baseline_success','legal_routes'):
            if pw[k]!=ew[k]: errors['global'].append({'world':wi,'field':k})
        rows={s['id']:s for s in pw['sites']}
        for s in ew['sites']:
            for k in ('occurred','all_occurrences_authorized','suppressed_success','avoiding_routes'):
                if rows[s['id']][k]!=s[k]: errors['sites'].append({'world':wi,'id':s['id'],'field':k})
    return errors
