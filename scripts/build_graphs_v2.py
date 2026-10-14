"""Read the frozen selection, compare bounded extractors, and write new artifacts."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tsg.graph import extract_graph, read_bundle
from tsg.graph_v2 import extract_graph_v2


def measures(graph):
    actions = [n for n in graph['nodes'] if n['kind'] in {'CODE_ACTION', 'INSTR_ACTION'}]
    known = sum(n['resource'] != 'unknown' for n in actions)
    code = [n for n in actions if n['kind'] == 'CODE_ACTION']
    sinks = {n['id'] for n in code if n['operation'] in {'file.write', 'network.post', 'email.send', 'db.write'}}
    pairs = 0
    for source in code:
        if source['operation'] not in {'file.read', 'secret.read', 'network.get', 'db.read'}:
            continue
        pending, seen = [source['id']], set()
        while pending:
            current = pending.pop()
            if current not in seen:
                seen.add(current)
                pending.extend(e['target'] for e in graph['edges'] if e['source'] == current and e['type'] == 'DATA')
        pairs += len(seen & sinks)
    return {'nodes': len(graph['nodes']), 'candidate_actions': len(actions), 'known_resource_actions': known,
            'unknown_resource_actions': len(actions) - known,
            'candidate_source_sink_data_pairs': pairs,
            'resource_status_counts': dict(Counter(n.get('resource_status', 'unclassified_v1') for n in code)),
            'code_known_resource_actions': sum(n['resource'] != 'unknown' for n in code),
            'code_candidate_actions': len(code),
            'edge_counts': dict(Counter(e['type'] for e in graph['edges'])),
            'node_kinds': dict(Counter(n['kind'] for n in graph['nodes'])),
            'unresolved_records': len(graph['unresolved']),
            'unresolved_reasons': dict(Counter(u['reason'] for u in graph['unresolved']))}


def aggregate(rows, key):
    totals = {k: sum(row[key][k] for row in rows) for k in ('nodes', 'candidate_actions', 'known_resource_actions', 'unknown_resource_actions', 'unresolved_records', 'candidate_source_sink_data_pairs', 'code_known_resource_actions', 'code_candidate_actions')}
    for field in ('edge_counts', 'node_kinds', 'unresolved_reasons', 'resource_status_counts'):
        counter = Counter()
        for row in rows:
            counter.update(row[key][field])
        totals[field] = dict(counter)
    totals['known_resource_fraction'] = totals['known_resource_actions'] / totals['candidate_actions'] if totals['candidate_actions'] else None
    totals['skills_with_data_edges'] = sum(row[key]['edge_counts'].get('DATA', 0) > 0 for row in rows)
    totals['skills_with_unresolved_records'] = sum(row[key]['unresolved_records'] > 0 for row in rows)
    return totals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/manifests/skills_manifest.jsonl')
    parser.add_argument('--out', type=Path, default=ROOT / 'results/phase2/graphs_v2')
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.manifest.read_text(encoding='utf-8').splitlines()]
    args.out.mkdir(parents=True, exist_ok=True)
    started, measurements, changes = time.perf_counter(), [], []
    for row in rows:
        bundle = Path(row['bundle_path']).resolve()
        before = {}
        for rel, expected in row['file_sha256'].items():
            path = (bundle / rel).resolve()
            if not path.is_relative_to(bundle):
                raise ValueError('MANIFEST_PATH_OUTSIDE_BUNDLE')
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
            before[rel] = observed
            if observed != expected:
                changes.append({'skill_id': row['skill_id'], 'file': rel, 'when': 'before'})
        files, coverage = read_bundle(row, max_chars=24000, max_files=12)
        baseline = extract_graph(row['skill_id'], files)
        graph = extract_graph_v2(row['skill_id'], files)
        graph.update(family_id=row.get('family_id'), split=row.get('split'), coverage=coverage,
                     source_text_sha256={file: hashlib.sha256(text.encode()).hexdigest() for file, text in files.items()})
        (args.out / (row['skill_id'] + '.json')).write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
        measurements.append({'skill_id': row['skill_id'], 'family_id': row.get('family_id'), 'split': row.get('split'),
                             'files_analyzed': len(files), 'chars_analyzed': sum(map(len, files.values())),
                             'coverage': coverage, 'v1_same_input': measures(baseline), 'v2': measures(graph)})
        for rel, expected in before.items():
            if hashlib.sha256((bundle / rel).read_bytes()).hexdigest() != expected:
                changes.append({'skill_id': row['skill_id'], 'file': rel, 'when': 'after'})
    summary = {'skills': len(rows), 'v1_same_input': aggregate(measurements, 'v1_same_input'), 'v2': aggregate(measurements, 'v2'),
               'source_changes': changes, 'elapsed_seconds': time.perf_counter() - started,
               'files_analyzed': sum(r['files_analyzed'] for r in measurements),
               'truncated_files': sum(len(r['coverage']['truncated_files']) for r in measurements),
               'omitted_files': sum(len(r['coverage']['omitted_files']) for r in measurements),
               'meaning': 'candidate/resource/edge coverage, not semantic accuracy or authorization accuracy',
               'limits': {'max_chars_per_bundle': 24000, 'max_files_per_bundle': 12},
               'model_calls': 0, 'corpus_code_executed': False}
    (args.out / 'coverage.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in measurements), encoding='utf-8')
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    manifest = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                'input_manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
                                  ['src/tsg/graph.py', 'src/tsg/graph_v2.py', 'scripts/build_graphs_v2.py', 'tests/test_graph_v2.py']},
                'source_immutability_checked': True, 'baseline': 'original_v1_extractor_on_identical_bounded_text',
                'reproduce': '.venv/Scripts/python.exe scripts/build_graphs_v2.py'}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('skills', 'files_analyzed', 'truncated_files', 'omitted_files', 'source_changes', 'elapsed_seconds')}))
    return 0 if not changes else 1


if __name__ == '__main__':
    raise SystemExit(main())
