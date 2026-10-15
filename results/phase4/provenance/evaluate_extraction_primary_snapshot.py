"""Paired extraction benchmark against independently authored literal fixtures."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from tsg.extraction_v4 import extract_graph_v4
from tsg.graph_v2 import extract_graph_v2
from prepare_phase4 import immutable, json_bytes, rows_bytes


def compare(fixture, graph):
    actual = [n for n in graph['nodes'] if n.get('privilege_relevant')]
    expected = fixture['expected_effects']
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
            'resource_exact': e['resource'] == a['resource'],
            'false_resolved': a['resource'] != 'unknown' and a['resource'] != e['resource'],
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
        'exact_resources': sum(p['resource_exact'] for p in pairs),
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


def evaluate(out):
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
            graph = extractor(fixture['id'], fixture['files'])
            rows.append({**compare(fixture, graph), 'extractor': version})
            immutable(out/f'graphs/{version}/{fixture["id"]}.json', json_bytes(graph))
    groups = []
    for version in ('v2','v4'):
        for split in ('all','dev','validation','heldout'):
            selected = [r for r in rows if r['extractor'] == version and (split == 'all' or r['split'] == split)]
            m = dict(sum((Counter(r['metrics']) for r in selected), Counter()))
            m.update({'precision': m.get('matched',0)/m['actual'] if m.get('actual') else None,
                      'recall': m.get('matched',0)/m['expected'] if m.get('expected') else None,
                      'supported_recall': m.get('supported_matched',0)/m['supported_expected'] if m.get('supported_expected') else None})
            groups.append({'extractor':version,'split':split,'fixtures':len(selected),
                           'families':len({r['family'] for r in selected}), **m})
    summary = {'groups':groups,'fixture_source_sha256':sources,
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
    args=parser.parse_args()
    evaluate(args.out)
