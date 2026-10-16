"""Offline reproduction: immutable baseline, truth, requests, budget and execution."""
import argparse
import json
import sys
from phase9_common import ROOT, sha, jb, rb, immutable, read_rows, cases, verify_freeze, CAP
sys.path.insert(0, str(ROOT / 'src'))


def release_files():
    paths = set()
    for directory in ('data/phase9', 'results/phase9'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file())
    for directory in ('src/tsg', 'scripts', 'tests', 'docs', '.github/workflows'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file()
                     and ('phase9' in p.name or '_v9' in p.name) and '__pycache__' not in p.parts)
    paths.add(ROOT / 'PHASE9.md')
    excluded = {'results/phase9/provenance/release_hashes.json', 'results/phase9/provenance/release_verification.json'}
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(paths)
            if p.relative_to(ROOT).as_posix() not in excluded}


def verify():
    baseline = json.loads((ROOT / 'results/phase9/provenance/baseline.json').read_text())
    for i, (p, h) in enumerate(baseline['files'].items(), 1):
        assert sha((ROOT / p).read_bytes()) == h, 'OLD_FILE_CHANGED:' + p
        if i % 4000 == 0:
            print(json.dumps({'old_files_verified': i}), flush=True)
    production, data = verify_freeze('production'), verify_freeze()
    from build_phase9_heldout import build_cases, reference_record, coverage_audit, novelty_audit, jsonl_bytes
    new = build_cases()
    refs = [reference_record(c) for c in new]
    assert len(new) == 24 and len({c['family'] for c in new}) == 12
    assert jsonl_bytes(new) == (ROOT / 'data/phase9/heldout.jsonl').read_bytes()
    assert jsonl_bytes(refs) == (ROOT / 'results/phase9/reference/truth.jsonl').read_bytes()
    normalize = lambda v: json.loads(json.dumps(v))
    for name, value in [('coverage', coverage_audit(new, refs)), ('novelty', novelty_audit(new))]:
        assert normalize(value) == json.loads((ROOT / f'results/phase9/reference/{name}.json').read_text())
    provenance = json.loads((ROOT / 'results/phase9/reference/provenance.json').read_text())
    for p, h in provenance['source_sha256'].items():
        assert sha((ROOT / p).read_bytes()) == h
    for name, h in provenance['artifact_sha256'].items():
        path = ROOT / 'data/phase9/heldout.jsonl' if name == 'heldout.jsonl' else ROOT / f'results/phase9/reference/{name}'
        assert sha(path.read_bytes()) == h
    first = json.loads((ROOT / 'results/phase9/reference/first-pass/candidate-hashes.json').read_text())
    assert first['generator_sha256'] == sha((ROOT / 'scripts/build_phase9_heldout.py').read_bytes())
    assert first['heldout_sha256'] == sha(jsonl_bytes(new)) and first['truth_sha256'] == sha(jsonl_bytes(refs))
    for name in ('coverage.json', 'novelty.json'):
        assert (ROOT / f'results/phase9/reference/{name}').read_bytes() == (ROOT / f'results/phase9/reference/first-pass/{name}').read_bytes()
    print(json.dumps({'reference_reproduced': True}), flush=True)
    from run_phase9 import prepare, observation
    jobs, manifest, budget = prepare()
    observations = read_rows(ROOT / 'results/phase9/api/observations.jsonl')
    index = {r['job_id']: r for r in observations}
    assert len(observations) == len(index) == len(jobs) == 336
    assert set(index) == {j['job_id'] for j in jobs}
    cs = {c['case_id']: c for c in cases()}
    reservations = []
    for j in jobs:
        raw = json.loads((ROOT / index[j['job_id']]['raw_ref']).read_text(encoding='utf-8'))
        expected = j['expected_request_hash']
        assert raw['request_hash'] == expected
        if 'request' in raw:
            assert sha(json.dumps({'request': raw['request'], 'replicate': raw['replicate']}, sort_keys=True, ensure_ascii=False).encode()) == expected
        dispatch = json.loads((ROOT / f'results/phase9/api/dispatch/{j["job_id"]}.json').read_text())
        assert dispatch == {'job_id': j['job_id'], 'request_hash': expected}
        assert observation(j, raw, cs[j['case_id']]) == index[j['job_id']]
        assert json.loads((ROOT / f'results/phase9/api/jobs/{j["job_id"]}.json').read_text(encoding='utf-8')) == index[j['job_id']]
        if raw.get('reservation_id'):
            rid = raw['reservation_id']
            reservations.append(rid)
            entry = budget.entries[rid]
            assert entry['model'] == j['model'] and entry['reserved_usd'] == j['reservation_upper_usd']
            if entry['status'] == 'settled':
                from tsg.budget_v4 import UPPER_PRICES
                ip, op = UPPER_PRICES[j['model']]
                assert entry['usage'] == raw['usage']
                assert entry['cost_usd'] == (raw['usage']['input_tokens'] * ip + raw['usage']['output_tokens'] * op) / 1e6
    oldids = {r['reservation_id'] for r in read_rows(ROOT / 'results/phase8/api/budget.jsonl')}
    assert len(reservations) == len(set(reservations)) and set(budget.entries) - oldids == set(reservations)
    assert budget.total_cost <= CAP and manifest['reservation_upper_usd'] <= 4
    print(json.dumps({'api_records_reproduced': len(observations)}), flush=True)
    from experiment_phase9 import semantics, queries, batch
    semantic, query = semantics(), queries()
    from container_phase9 import command, IMAGE
    totals = {}
    for track in ('interface', 'recovery', 'integrated'):
        totals[track] = batch(track)['conditions']
        directory = ROOT / f'results/phase9/{track}'
        vm = read_rows(directory / 'vm_results.jsonl')
        saved = read_rows(directory / 'container_results.jsonl')
        assert vm == saved
        grid = read_rows(directory / 'jobs.jsonl')
        modules = {'tsg.' + n: (ROOT / f'src/tsg/{n}.py').read_text(encoding='utf-8')
                   for n in ('runtime_v6', 'recovery_v7', 'recovery_v8', 'observation_v9', 'recovery_v9')}
        combined = []
        for i, start in enumerate(range(0, len(grid), 400), 1):
            out = directory / f'container_batches/{i:03}'
            subset = grid[start:start + 400]
            plan = json.loads((out / 'plan.json').read_text())
            intent = json.loads((out / 'intent.json').read_text())
            assert plan['image'] == IMAGE and plan['command'] == command()
            assert plan['jobs_sha256'] == sha(rb(subset))
            assert plan['payload_sha256'] == sha(jb({'modules': modules, 'jobs': subset})) == intent['payload_sha256']
            assert json.loads((out / 'exit.json').read_text())['exit_code'] == 0
            result = json.loads((out / 'stdout.json').read_text())
            assert result['uid'] == 65534
            combined.extend(result['rows'])
        assert combined == vm
        audit = json.loads((directory / 'container_audit.json').read_text())
        assert audit == {'conditions': len(vm), 'containers': (len(grid) + 399) // 400,
                         'exact_vm_agreement': True, 'uid': 65534, 'image': IMAGE}
        for r in vm:
            v = r['result']
            assert v['unauthorized_effects'] == v['duplicate_effects'] == 0
            assert v['charged_calls'] <= r['quota'] and v['attempts'] <= 4
            if r['policy'] != 'v8_cost':
                assert v['planning_units'] <= r['planning_budget']
                assert v['observation_count'] <= r['observation_budget']
                if track == 'integrated':
                    assert v['audit_interpreter_calls'] == 0
        print(json.dumps({'reproduced_track': track, 'conditions': len(vm)}), flush=True)
    from analyze_phase9 import main as analyze
    analyze([])
    value = {'status': 'pass', 'baseline_files_unchanged': len(baseline['files']),
             'production_frozen_files': len(production['files']), 'data_frozen_files': len(data['files']),
             'model_conditions': len(jobs), 'unique_requests': len({j['expected_request_hash'] for j in jobs}),
             'new_reservations': len(reservations), 'semantic_comparisons': semantic['comparisons'],
             'query_conditions': query['conditions'], 'executions': totals,
             'cumulative_upper_usd': budget.total_cost, 'remaining_usd': CAP - budget.total_cost}
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--release', action='store_true')
    a = p.parse_args()
    value = verify()
    hashes = release_files()
    if a.release:
        immutable(ROOT / 'results/phase9/provenance/release_hashes.json', jb(hashes))
        immutable(ROOT / 'results/phase9/provenance/release_verification.json', jb({**value, 'release_files': len(hashes)}))
    else:
        assert hashes == json.loads((ROOT / 'results/phase9/provenance/release_hashes.json').read_text())
        assert {**value, 'release_files': len(hashes)} == json.loads((ROOT / 'results/phase9/provenance/release_verification.json').read_text())
    print(json.dumps({**value, 'release_files': len(hashes)}), flush=True)
