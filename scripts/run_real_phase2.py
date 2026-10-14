"""Frozen all-180 static track; no corpus code execution, shared budget ledger."""
import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from tsg.models import Client, Budget, load_key
from run_experiment import dump_jsonl, run_manifest, real_audit
from run_supplement import task_triples, real_detection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    rows = [json.loads(s) for s in (ROOT/'data/manifests/skills_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 180 and all(r['download_status'] == 'completed' for r in rows)
    prepared = {r['skill_id']: task_triples(r) for r in rows}
    tasks = []
    for row in rows:
        files, graph, coverage, contexts = prepared[row['skill_id']]
        assert len(files) <= 12 and sum(map(len, files.values())) <= 24000
        for context, prompt in contexts.items():
            tasks.append({'skill_id': row['skill_id'], 'source_native_id': row['source_native_id'],
                          'family_id': row['family_id'], 'split': row['split'], 'context': context,
                          'trusted_task': prompt, 'graph': graph, 'human_annotated': False,
                          'task_origin': 'researcher-authored hypothetical authorization context',
                          'coverage': coverage})
    dump_jsonl(ROOT/'data/tasks/phase2_real_task_triples.jsonl', tasks)
    print(json.dumps({'prepared_skills': len(rows), 'prepared_tasks': len(tasks),
                      'candidate_action_in_task_rows': sum(len(t['graph']['nodes']) for t in tasks)}), flush=True)
    if args.prepare_only:
        return
    run_manifest('phase2_real')
    client = Client(load_key(args.env_file), ROOT/'results/api/raw', Budget(ROOT/'results/api/budget.jsonl', 20))
    output = ROOT/'results/phase2/real'
    # Development, validation, and held-out are checkpointed separately and never tuned here.
    for split in ('development', 'validation', 'held_out_test'):
        jobs = []
        for row in (r for r in rows if r['split'] == split):
            for model in ('gpt-6-luna', 'gpt-4.1-mini'):
                jobs.append(('extraction', real_audit, (client, row, model)))
                for context in ('low', 'high', 'edge'):
                    for variant in ('v0', 'v1'):
                        jobs.append(('predictions', real_detection, (client, row, prepared[row['skill_id']], model, context, variant)))
        records = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(fn, *a): track for track, fn, a in jobs}
            for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                track = futures[future]
                record = future.result()
                record['split'] = split
                records.setdefault(track, []).append(record)
                dump_jsonl(output/split/(track+'.jsonl'), records[track])
                if i % 30 == 0 or i == len(jobs):
                    print(json.dumps({'split': split, 'completed': i, 'total': len(jobs),
                                      'budget_upper_usd': client.budget.total_cost}), flush=True)


if __name__ == '__main__':
    main()
