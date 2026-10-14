"""Read-only phase-2 evidence/grid checks. No API, Docker, or source execution."""
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from tsg.evaluation import budget_summary
from tsg.pipeline_v2 import FEATURES
from run_pipeline_phase2 import validate_frozen_inputs


def rows(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]


def check_grid(records, fields, expected, name, errors):
    counts = Counter(tuple(row.get(k) for k in fields) for row in records)
    if any(n != 1 for n in counts.values()):
        errors.append(name + ': duplicate observation keys')
    if expected - counts.keys():
        errors.append(name + ': missing ' + str(len(expected - counts.keys())))
    if counts.keys() - expected:
        errors.append(name + ': unexpected ' + str(len(counts.keys() - expected)))


def check_raw(root, digest, errors):
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        errors.append('invalid request_hash: ' + str(digest))
        return
    path = root / 'results/api/raw' / (digest + '.json')
    if not path.exists():
        errors.append('missing raw: ' + digest)
        return
    raw = json.loads(path.read_text(encoding='utf-8'))
    actual = hashlib.sha256(json.dumps({'request': raw['request'], 'replicate': raw['replicate']}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if actual != digest:
        errors.append('raw fingerprint mismatch: ' + digest)


def main(root=ROOT):
    root = Path(root)
    errors, references, counts = [], set(), {}
    models = ('gpt-6-luna', 'gpt-4.1-mini')
    cases = rows(root / 'data/benchmark/synthetic_cases.jsonl')
    ids = [c['case_id'] for c in cases]
    samples = rows(root / 'data/manifests/skills_manifest.jsonl')
    try:
        validate_frozen_inputs(root)
    except (ValueError, OSError) as exc:
        errors.append('frozen input validation: ' + str(exc))

    def track(path, fields, expected):
        data = rows(root / path)
        check_grid(data, fields, set(expected), path, errors)
        for row in data:
            for key in ('request_hash', 'p_request_hash'):
                if row.get(key):
                    references.add(row[key])
        counts[path] = len(data)
        return data

    base = 'results/phase2/pipeline/'
    planner_keys = set(itertools.product(ids, models, ('v0', 'v5'), ('json',), (0, 1)))
    for case in cases:
        if '-0-' in case['case_id'] and case['scenario'] in {'low','high','claim_inflation','authority_spoofing','artificial_dependency','data_flow_misuse','optional_cache'}:
            for model in models:
                planner_keys.add((case['case_id'], model, 'v1', 'json', 0))
                planner_keys.update(itertools.product((case['case_id'],), (model,), ('v0','v1','v5'), ('fields','indented_json'), (0,)))
    planner = track(base + 'planner.jsonl', ('case_id','model','variant','form','replicate'), planner_keys)
    for row in planner:
        if row['variant'] == 'v5':
            raw = json.loads((root / 'results/api/raw' / (row['request_hash'] + '.json')).read_text(encoding='utf-8'))
            payload = json.loads(raw['request']['input'][1]['content'])
            if any(k.startswith('untrusted') for k in payload):
                errors.append('trusted P contains untrusted payload: ' + row['case_id'])
    track(base + 'e3_closed_loop.jsonl', ('case_id','model','policy_origin','mode'), itertools.product(ids, models, ('oracle_correct_policy','LLM_generated_separated','LLM_generated_mixed'), ('none','v3','v4','v5')))
    for variant in FEATURES:
        track(base + 'ablation_' + variant + '.jsonl', ('case_id','model','replicate'), itertools.product(ids, models, (0,1)))
    track(base + 'fixed_actions_mechanistic.jsonl', ('case_id','variant'), itertools.product(ids, FEATURES))
    for split in ('development','validation','held_out_test'):
        selected = [s['skill_id'] for s in samples if s['split'] == split]
        prefix = 'results/phase2/real/' + split + '/'
        track(prefix + 'extraction.jsonl', ('skill_id','model'), itertools.product(selected, models))
        real = track(prefix + 'predictions.jsonl', ('skill_id','model','context','variant'), itertools.product(selected, models, ('low','high','edge'), ('v0','v1')))
        if any(r.get('human_annotated') is not False for r in real):
            errors.append('unsupported human label claim: ' + split)
    os_ids = ['os-' + kind + '-' + context for kind in ('pdf','csv','git','http','smtp','sqlite') for context in ('low','high')]
    track('results/phase2/os_e2e/contracts.jsonl', ('case_id','model','mixed'), itertools.product(os_ids, models, (False,True)))
    os_keys = set(itertools.product(os_ids, ('oracle_correct_policy',), (None,), (False,True), (0,1)))
    os_keys.update(itertools.product(os_ids, ('LLM_generated_separated','LLM_generated_mixed'), models, (False,True), (0,1)))
    os_runs = track('results/phase2/os_e2e/runs.jsonl', ('case_id','origin','model','guard_enabled','replicate'), os_keys)
    for row in os_runs:
        evidence = root / row['evidence_path'].replace('\\','/')
        if not evidence.resolve().is_relative_to(root.resolve()):
            errors.append('OS evidence path escapes release')
            continue
        for name in ('host_result.json','scored.json','syscalls.log'):
            if not (evidence / name).is_file():
                errors.append('missing OS evidence: ' + str(evidence / name))
        saved = json.loads((evidence / 'scored.json').read_text(encoding='utf-8'))
        if saved != row:
            errors.append('OS aggregate differs from saved scored evidence: ' + row['case_id'])
        isolation = row['result'].get('isolation', {})
        if isolation.get('NetworkMode') != 'none' or isolation.get('ReadonlyRootfs') is not True or isolation.get('Binds'):
            errors.append('OS isolation mismatch: ' + row['case_id'])
        if 'task_oracle_goal_satisfied' not in row:
            errors.append('OS outer task oracle missing: ' + row['case_id'])
        if not row.get('observation_complete') and row.get('unauthorized_execution') is False:
            errors.append('incomplete OS observation credited as safe: ' + row['case_id'])
    replay = json.loads((root / 'results/phase2/os/replay_summary_final.json').read_text(encoding='utf-8'))
    if replay['valid_replay_pairs'] != 3 or len(replay['valid_action_classes']) != 3:
        errors.append('typed replay coverage incomplete')
    for path in replay['trace_paths']:
        if not (root / 'results/phase2/os' / path).is_file():
            errors.append('missing typed replay trace: ' + path)
    track('results/phase2/os_judge/predictions.jsonl', ('case_id','model'), itertools.product(('csv-write','csv-read','smtp-send'), models))
    judge = json.loads((root / 'results/phase2/os_judge/summary.json').read_text(encoding='utf-8'))
    if not judge['complete'] or judge['n_records'] != 6:
        errors.append('actual OS replay Judge incomplete')
    corpus = json.loads((root / 'results/phase2/corpus_immutability_final.json').read_text(encoding='utf-8'))
    if corpus != {'checked_bundles':180, 'checked_files':3414, 'changes':[]}:
        errors.append('full source immutability evidence mismatch')
    immutable = json.loads((root / 'results/phase2/os/source_immutability.json').read_text(encoding='utf-8'))
    if immutable['changed_files'] != 0:
        errors.append('source mutation recorded')
    annotation = json.loads((root / 'data/annotation_v2/verification.json').read_text(encoding='utf-8'))
    for entry in annotation['checks']:
        if not entry['all_human_labels_blank']:
            errors.append('unexpected completed human labels')
        html = root / 'data/annotation_v2' / entry['scope'] / entry['slot'] / 'review.html'
        if hashlib.sha256(html.read_bytes()).hexdigest() != entry['html_sha256']:
            errors.append('annotation HTML hash mismatch')
    analysis = json.loads((root / 'results/phase2/pipeline_analysis/summary.json').read_text(encoding='utf-8'))
    if analysis['analysis_status'] != 'complete_saved_counts' or not all(analysis['track_count_completion'].values()):
        errors.append('analysis incomplete')
    for digest in references:
        check_raw(root, digest, errors)
    budget = budget_summary(rows(root / 'results/api/budget.jsonl'))
    if budget['total_exposure_upper_usd'] > 20:
        errors.append('authorized budget exceeded')
    # The independent analyzer's ledger digest must match current budget evidence.
    if analysis['budget_ledger_sha256'] != hashlib.sha256((root / 'results/api/budget.jsonl').read_bytes()).hexdigest():
        errors.append('analysis budget is stale')
    result = {'track_records': counts, 'unique_raw_references': len(references), 'budget': budget, 'failures': errors}
    print(json.dumps(result, ensure_ascii=False))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
