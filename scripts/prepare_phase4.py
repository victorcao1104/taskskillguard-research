"""Offline phase-four preservation inventory and real-source descriptive census."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
BASELINE = 'a666de55206ece2dcdbb669d083aa175a50dea5a'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def immutable(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('PRESERVED_OUTPUT_MISMATCH: ' + str(path))
    else:
        path.write_bytes(data)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def rows_bytes(values):
    return ''.join(json.dumps(v, ensure_ascii=False, sort_keys=True) + '\n' for v in values).encode('utf-8')


def baseline():
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '-z', BASELINE], cwd=ROOT).decode('utf-8').strip('\0').split('\0')
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE], cwd=ROOT).decode('utf-8').splitlines()
    if set(changed) & set(names):
        raise ValueError('BASELINE_TRACKED_FILE_CHANGED')
    ledger_bytes = (ROOT / 'results/phase3_followup/api/budget.jsonl').read_bytes()
    latest = {r['reservation_id']: r for r in map(json.loads, ledger_bytes.decode('utf-8').splitlines())}
    exposure = sum(r.get('cost_usd', r['reserved_usd']) for r in latest.values())
    out = {'baseline_commit': BASELINE, 'file_sha256': {n: sha((ROOT / n).read_bytes()) for n in names},
           'inherited_budget_ref': 'results/phase3_followup/api/budget.jsonl',
           'inherited_budget_sha256': sha(ledger_bytes), 'inherited_budget_bytes': len(ledger_bytes),
           'inherited_exposure_usd': exposure, 'cumulative_cap_usd': 20,
           'unknown_billing_reservations_retained': sum(r['status'] != 'settled' for r in latest.values())}
    immutable(ROOT / 'results/phase4/provenance/baseline_manifest.json', json_bytes(out))
    return {'preserved_files': len(names), 'inherited_exposure_usd': exposure}


def census():
    from tsg.extraction_v4 import extract_graph_v4
    from tsg.evidence_v4 import select_graph
    from tsg.graph_v2 import extract_graph_v2
    prepared = [json.loads(line) for line in (ROOT / 'data/phase3/real_prepared.jsonl').read_text(encoding='utf-8').splitlines()]
    if len(prepared) != 180 or len({p['skill_id'] for p in prepared}) != 180:
        raise ValueError('REAL_CORPUS_SIZE_MISMATCH')
    census_rows, selections, transitions, annotation, failures = [], [], [], [], []
    for p in prepared:
        skill = p['skill_id']
        files = p['files']
        full = extract_graph_v4(skill, files)
        full['input_coverage'] = p['coverage']
        bounded, selected, coverage = select_graph(full)
        old = extract_graph_v2(skill, files)
        selected_ids = set(p['action_ids'])
        old_selected = [n for n in old['nodes'] if n['id'] in selected_ids]
        new_actions = [n for n in full['nodes'] if n.get('privilege_relevant')]
        for n in old_selected:
            span = n['provenance']
            overlaps = [a for a in new_actions if a['provenance']['file'] == span['file'] and
                        a['provenance']['line_start'] <= span['line_end'] and a['provenance']['line_end'] >= span['line_start']]
            regions = [r for r in full['regions'] if r['file'] == span['file'] and r['line_start'] <= span['line_start'] <= r['line_end']]
            transitions.append({'skill_id': skill, 'legacy_id': n['id'], 'legacy_operation': n['operation'],
                'legacy_resource': n['resource'], 'provenance': span,
                'new_overlapping_actions': [{'id': a['id'], 'operation': a['operation'], 'resource': a['resource']} for a in overlaps],
                'regions': regions, 'interpretation': 'span overlap only; not correctness or equivalent population'})
        row = {k: p[k] for k in ('skill_id', 'source_native_id', 'family_id', 'split')}
        row.update({'old_selected': len(old_selected), 'old_total': sum(n.get('privilege_relevant', False) for n in old['nodes']),
                    'new_total': len(new_actions), 'new_selected': len(selected), 'selection_coverage': coverage,
                    'source_coverage': p['coverage'], 'source_sha256': full['source_sha256'],
                    'new_roles': dict(Counter(a['execution_role'] for a in new_actions)),
                    'new_analysis': dict(Counter(a['analysis_kind'] for a in new_actions)),
                    'new_resolution': dict(Counter(a['resource_status'] for a in new_actions)),
                    'unresolved_reasons': dict(Counter(u['reason'] for u in full['unresolved'])),
                    'rejected_reasons': dict(Counter(u.get('reason', 'unspecified') for u in full['rejected']))})
        census_rows.append(row)
        selections.append({**{k: p[k] for k in ('skill_id', 'source_native_id', 'family_id', 'split')},
            'files': files, 'graph': bounded, 'actions': selected, 'coverage': coverage,
            'source_coverage': p['coverage'], 'original_provenance': p['provenance']})
        for n in selected:
            annotation.append({'skill_id': skill, 'action': n, 'source_sha256': full['source_sha256'],
                               'rater_a': {}, 'rater_b': {}, 'adjudication': {},
                               'status': 'pending_independent_human_review'})
        immutable(ROOT / f'results/phase4/real/graphs/{skill}.json', json_bytes(full))
    out = ROOT / 'results/phase4/real'
    immutable(out / 'census.jsonl', rows_bytes(census_rows))
    immutable(out / 'legacy_span_transitions.jsonl', rows_bytes(transitions))
    immutable(ROOT / 'data/phase4/real_prepared.jsonl', rows_bytes(selections))
    immutable(ROOT / 'data/phase4/annotation_handoff.jsonl', rows_bytes(annotation))
    summary = {'skills': len(census_rows), 'old_selected': sum(r['old_selected'] for r in census_rows),
        'old_total': sum(r['old_total'] for r in census_rows), 'new_total': sum(r['new_total'] for r in census_rows),
        'new_selected': sum(r['new_selected'] for r in census_rows), 'zero_new_actions': sum(r['new_total'] == 0 for r in census_rows),
        'closure_incomplete': sum(not r['selection_coverage']['dependency_closure_complete'] for r in census_rows),
        'roles': dict(sum((Counter(r['new_roles']) for r in census_rows), Counter())),
        'analysis': dict(sum((Counter(r['new_analysis']) for r in census_rows), Counter())),
        'resolution': dict(sum((Counter(r['new_resolution']) for r in census_rows), Counter())),
        'unresolved_reasons': dict(sum((Counter(r['unresolved_reasons']) for r in census_rows), Counter())),
        'legacy_selected_without_overlap': sum(not r['new_overlapping_actions'] for r in transitions),
        'failures': failures, 'human_accuracy': None, 'human_labels': 0,
        'claim_scope': 'descriptive extraction of same bounded redacted sources; unknown/accuracy rates not comparable across changed candidates',
        'input_sha256': sha((ROOT / 'data/phase3/real_prepared.jsonl').read_bytes())}
    immutable(out / 'summary.json', json_bytes(summary))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(baseline(), ensure_ascii=False))
    if not args.baseline_only:
        print(json.dumps(census(), ensure_ascii=False))
