"""Prepare approved real sources offline; no API, execution or legacy writes."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tsg.real_v3 import LIMITS, TASK_ORIGIN, prepare_row


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/manifests/skills_manifest.jsonl')
    parser.add_argument('--expected-count', type=int, default=180)
    parser.add_argument('--data-out', type=Path, default=ROOT / 'data/phase3')
    parser.add_argument('--out', type=Path, default=ROOT / 'results/phase3/real_preparation')
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    rows = [json.loads(line) for line in manifest_bytes.decode('utf-8').splitlines() if line.strip()]
    if len(rows) != args.expected_count or len({r['skill_id'] for r in rows}) != len(rows):
        raise ValueError('FROZEN_MANIFEST_COUNT_OR_ID_MISMATCH')
    prepared = [prepare_row(row) for row in rows]
    if args.manifest.read_bytes() != manifest_bytes:
        raise ValueError('INPUT_MANIFEST_CHANGED')
    contexts, handoff = [], []
    for item in prepared:
        actions = {n['id']: n for n in item['graph']['nodes'] if n['id'] in item['action_ids']}
        source_hashes = {name.replace('\\', '/'): digest
                         for name, digest in item['provenance']['file_sha256'].items()}
        for name, context in item['contexts'].items():
            base = {k: item[k] for k in ('skill_id', 'source_native_id', 'family_id', 'split')}
            contexts.append({**base, 'context': name, **context, 'action_ids': item['action_ids'],
                             'coverage': item['coverage'], 'bounded_redacted_text_sha256': item['bounded_redacted_text_sha256'],
                             'prepared_evidence_ref': 'real_prepared.jsonl#' + item['skill_id']})
            for action in actions.values():
                handoff.append({**base, 'context': name, 'scope_status': context['scope_status'],
                                'task_origin': TASK_ORIGIN, 'trusted_task': context['trusted_task'],
                                'action_id': action['id'], 'provenance': action['provenance'],
                                'source_file_sha256': source_hashes[action['provenance']['file']],
                                'prepared_evidence_ref': 'real_prepared.jsonl#' + item['skill_id'],
                                'human_annotated': False, 'status': 'pending_independent_human_review',
                                'labels': {'rater_a': {}, 'rater_b': {}, 'adjudication': {}}})
    args.data_out.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    outputs = {'real_prepared.jsonl': prepared, 'real_contexts.jsonl': contexts,
               'real_annotation_handoff.jsonl': handoff}
    for filename, values in outputs.items():
        write_jsonl(args.data_out / filename, values)
    count = Counter(c['context'] for c in contexts)
    summary = {'skills': len(prepared), 'contexts': len(contexts), 'context_counts': dict(count),
               'explicit_effect_eligible_skills': count['explicit_effect'],
               'missing_scope_skills': count['missing_scope'],
               'action_candidates_selected': sum(len(p['action_ids']) for p in prepared),
               'action_candidates_before_cap': sum(p['coverage']['actions_total'] for p in prepared),
               'action_in_context_rows': len(handoff),
               'skills_with_zero_candidates': sum(not p['action_ids'] for p in prepared),
               'files_analyzed': sum(p['coverage']['files_analyzed'] for p in prepared),
               'source_files_hash_checked': sum(p['source_verification']['files_checked'] for p in prepared),
               'truncated_files': sum(len(p['coverage']['truncated_files']) for p in prepared),
               'omitted_files': sum(len(p['coverage']['omitted_files']) for p in prepared),
               'redacted_patterns': sum(p['coverage']['redacted_patterns'] for p in prepared),
               'max_detection_jobs_two_models_two_variants': len(contexts) * 4,
               'max_model_evaluated_jobs_two_models_two_variants': sum(len(p['contexts']) * 4 for p in prepared if p['action_ids']),
               'empty_candidate_rows_two_models_two_variants': sum(len(p['contexts']) * 4 for p in prepared if not p['action_ids']),
               'limits': LIMITS, 'source_changes': [], 'model_calls': 0, 'corpus_code_executed': False,
               'human_labels_received': 0, 'human_accuracy': None,
               'meaning': 'Coverage and availability of researcher hypothetical scope; no human ground truth or real-user authorization.',
               'selection_bias': 'Explicit-effect contexts exist only for literal eligible selected candidates; do not compare their subset as though it were all 180 skills.',
               'explicit_eligibility_rule': 'Eligible file/network operation and exact non-placeholder literal in its source span; Python AST grounding or directly associated lexical verb/explicit curl POST. Excludes credentials, command execution, unrelated keyword/URL pairs and reconstructed nonliteral values.',
               'denominators': 'All skills retain review_only and edge plus exactly one explicit_effect or missing_scope. Raw and graph_v2 use identical candidate IDs within every skill/context.',
               'existing_priority_annotation_pack': 'data/annotation_v2/priority (unchanged, blank human labels)',
               'new_annotation_handoff': 'real_annotation_handoff.jsonl (new context/spans; blank labels; not silently compatible with old graph IDs)'}
    (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    artifact_hashes = {filename: hashlib.sha256((args.data_out / filename).read_bytes()).hexdigest() for filename in outputs}
    manifest = {'input_manifest': str(args.manifest.resolve()),
                'input_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
                'prepared_artifact_sha256': artifact_hashes,
                'source_immutability_checked': 'all manifest files before and after each bounded read; input manifest before/after whole preparation',
                'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                                 ['src/tsg/real_v3.py', 'src/tsg/graph.py', 'src/tsg/graph_v2.py', 'src/tsg/models_v3.py',
                                  'scripts/prepare_real_phase3.py', 'tests/test_real_v3.py']},
                'reproduce': '.venv/Scripts/python.exe scripts/prepare_real_phase3.py'}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
