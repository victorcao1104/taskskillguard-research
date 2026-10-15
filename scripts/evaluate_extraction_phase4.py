"""Paired extraction benchmark against independently authored literal fixtures."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from tsg.extraction_v4 import extract_graph_v4
from tsg.graph_v2 import extract_graph_v2
from prepare_phase4 import immutable, json_bytes, rows_bytes


def compare(fixture, graph):
    actual = deepcopy([n for n in graph['nodes'] if n.get('privilege_relevant')])
    for n in actual:
        if n['operation'] == 'secret.read' and n['resource'].startswith('env:'):
            n['operation'] = 'environment.read'
    expected = deepcopy(fixture['expected_effects'])
    for e in expected:
        if e['resource'] is None:
            e['resource'] = 'unknown'
    if fixture['id'] == 'dynpy02':
        expected.append({'effect_id': 'dynpy02:erratum-env', 'file': 'main.py',
            'line_start': 3, 'line_end': 3, 'operation': 'environment.read',
            'resource': 'env:OUTPUT', 'resource_status': 'literal',
            'execution_role': 'source_code', 'grammar_status': 'supported',
            'erratum': 'Independent source review: environment lookup is a distinct capability; sensitivity is unknown.'})
    # Maximum cardinality bipartite source-span/operation match. Target exactness
    # breaks candidate preference only; it never excuses a missed operation.
    eligible = {}
    for ei, e in enumerate(expected):
        candidates = [ai for ai, a in enumerate(actual) if a['operation'] == e['operation']
            and a['provenance']['file'] == e['file']
            and a['provenance']['line_start'] <= e['line_end']
            and a['provenance']['line_end'] >= e['line_start']]
        eligible[ei] = sorted(candidates, key=lambda ai: (actual[ai]['resource'] != e['resource'], actual[ai]['id']))
    matched = {}
    def augment(ei, visited):
        for ai in eligible[ei]:
            if ai in visited:
                continue
            visited.add(ai)
            if ai not in matched or augment(matched[ai], visited):
                matched[ai] = ei
                return True
        return False
    for ei in sorted(range(len(expected)), key=lambda i: (len(eligible[i]), expected[i]['effect_id'])):
        augment(ei, set())
    pairs = []
    for ai, ei in sorted(matched.items()):
        a, e = actual[ai], expected[ei]
        pairs.append({'effect_id': e['effect_id'], 'action_id': a['id'],
            'expected_resource': e['resource'], 'observed_resource': a['resource'],
            'binding_comparable': e['operation'] != 'command.exec',
            'resource_exact': e['resource'] == a['resource'] if e['operation'] != 'command.exec' else None,
            'false_resolved': e['operation'] != 'command.exec' and a['resource'] != 'unknown' and a['resource'] != e['resource'],
            'role_exact': a.get('execution_role') == e['execution_role'],
            'span_exact': a['provenance']['line_start'] == e['line_start'] and a['provenance']['line_end'] == e['line_end'],
            'grammar_status': e['grammar_status']})
    unmatched_expected = [e for ei, e in enumerate(expected) if ei not in matched.values()]
    unmatched_actual = [a for ai, a in enumerate(actual) if ai not in matched]
    bad_spans = [n for n in graph['nodes'] if n['provenance']['file'] not in fixture['files']
        or not (1 <= n['provenance']['line_start'] <= n['provenance']['line_end'] <=
                len(fixture['files'][n['provenance']['file']].splitlines()))]
    metrics = {'expected': len(expected), 'actual': len(actual), 'matched': len(pairs),
        'false_positive': len(unmatched_actual), 'missed': len(unmatched_expected),
        'exact_resources': sum(p['resource_exact'] is True for p in pairs),
        'binding_comparable': sum(p['binding_comparable'] for p in pairs),
        'command_binding_ontology_excluded': sum(not p['binding_comparable'] for p in pairs),
        'false_resolved': sum(p['false_resolved'] for p in pairs),
        'exact_roles': sum(p['role_exact'] for p in pairs),
        'exact_spans': sum(p['span_exact'] for p in pairs), 'invalid_spans': len(bad_spans),
        'supported_expected': sum(e['grammar_status'] == 'supported' for e in expected),
        'supported_matched': sum(p['grammar_status'] == 'supported' for p in pairs),
        'unresolved_expected': sum(e['resource'] == 'unknown' for e in expected),
        'correct_target_abstentions': sum(p['expected_resource'] == 'unknown' and p['resource_exact'] for p in pairs)}
    return {'fixture_id': fixture['id'], 'family': fixture['family'], 'split': fixture['split'],
            'metrics': metrics, 'matched': pairs, 'missed_effects': unmatched_expected,
            'extra_candidates': unmatched_actual, 'invalid_spans': bad_spans,
            'unresolved': graph.get('unresolved', []), 'analysis_complete': False}


def evaluate(out, graphs_from=None):
    fixtures = []
    sources = {}
    for path in sorted((ROOT/'data/phase4').glob('fixtures_*.jsonl')):
        data = path.read_bytes()
        sources[str(path.relative_to(ROOT)).replace('\\','/')] = hashlib.sha256(data).hexdigest()
        fixtures += [json.loads(line) for line in data.decode('utf-8').splitlines()]
    if len(fixtures) != 50:
        raise ValueError('FROZEN_FIXTURE_SIZE_MISMATCH')
    rows = []
    for fixture in fixtures:
        for version, extractor in [('v2', extract_graph_v2), ('v4', extract_graph_v4)]:
            graph = (json.loads((graphs_from/f'graphs/{version}/{fixture["id"]}.json').read_text(encoding='utf-8'))
                     if graphs_from else extractor(fixture['id'], fixture['files']))
            rows.append({**compare(fixture, graph), 'extractor': version})
            immutable(out/f'graphs/{version}/{fixture["id"]}.json', json_bytes(graph))
    groups = []
    for version in ('v2','v4'):
        for split in ('all','dev','validation','heldout'):
            selected = [r for r in rows if r['extractor'] == version and (split == 'all' or r['split'] == split)]
            m = {key: sum(r['metrics'][key] for r in selected) for key in selected[0]['metrics']}
            m.update({'precision': m.get('matched',0)/m['actual'] if m.get('actual') else None,
                      'recall': m.get('matched',0)/m['expected'] if m.get('expected') else None,
                      'supported_recall': m.get('supported_matched',0)/m['supported_expected'] if m.get('supported_expected') else None})
            groups.append({'extractor':version,'split':split,'fixtures':len(selected),
                           'families':len({r['family'] for r in selected}), **m})
    summary = {'groups':groups,'fixture_source_sha256':sources,
        'scoring_revision':'v4.1: normalize None unknown; add independently reviewed env lookup; exclude disputed command resource ontology from exact binding',
        'graphs_replayed_from': str(graphs_from.relative_to(ROOT)) if graphs_from else None,
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                         ['scripts/evaluate_extraction_phase4.py','src/tsg/extraction_v4.py','src/tsg/shell_v4.py','src/tsg/evidence_v4.py']},
        'truth_origin':'separate literal author; no extractor output used to construct expectations',
        'matching':'maximum-cardinality span-overlap plus exact operation; target accuracy separate',
        'not_a_claim':'syntactic capability recall is not reachability/execution/authorization accuracy',
        'complete_fixture_denominator':50,'real_human_accuracy':None}
    immutable(out/'observations.jsonl', rows_bytes(rows))
    immutable(out/'summary.json', json_bytes(summary))
    print(json.dumps(summary['groups'], ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'results/phase4/extraction_primary')
    parser.add_argument('--graphs-from', type=Path)
    args=parser.parse_args()
    evaluate(args.out, args.graphs_from.resolve() if args.graphs_from else None)
