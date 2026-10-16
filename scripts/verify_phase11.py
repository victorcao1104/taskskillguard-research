"""Offline Phase 11 release audit; replay existing evidence, never acquire data.

Dependency and tokenizer-cache installation happens before this command. Socket
connections are blocked during verification. Docker capsules are checked against
fresh local VM replay; this command does not launch fresh Docker containers.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch

from phase11_common import ROOT, BASE, CAP, CAMPAIGN_CAP, sha, jb, rb, read_rows, read_chunks
from phase6_common import immutable as release_write

sys.path.insert(0, str(ROOT / 'src'))
TOKENIZER_CACHE_NAME = 'fb374d419588a4632f3f557e76b4b70aebbca790'
TOKENIZER_CACHE_SHA256 = '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def existing_identical(path, data):
    """Replace append-only writers during replay so missing evidence cannot pass."""
    path = Path(path)
    require(path.is_file(), 'MISSING_RECORDED_EVIDENCE:' + str(path))
    require(path.read_bytes() == data, 'REPLAY_BYTES_DIFFER:' + str(path))


def progress(**value):
    print(json.dumps(value, sort_keys=True), flush=True)


def release_files():
    paths = set()
    for directory in ('data/phase11', 'results/phase11', 'paper/phase11'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file())
    for directory in ('src/tsg', 'scripts', 'tests', 'docs', '.github/workflows'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file()
                     and ('phase11' in p.name or '_v11' in p.name)
                     and '__pycache__' not in p.parts)
    paths.update(ROOT / n for n in ('PHASE11.md', 'tests/conftest.py'))
    excluded = {'results/phase11/provenance/release_hashes.json',
                'results/phase11/provenance/release_verification.json'}
    require(all(p.is_file() for p in paths), 'RELEASE_ENTRY_MISSING')
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
            for p in sorted(paths) if p.relative_to(ROOT).as_posix() not in excluded}


def baseline_and_freezes():
    from phase11_common import verify_freeze
    baseline = read_json(ROOT / 'results/phase11/provenance/baseline.json')
    require(baseline['commit'] == BASE and baseline['count'] == len(baseline['files']) == 37907,
            'BASELINE_IDENTITY_OR_COUNT')
    for i, (name, digest) in enumerate(baseline['files'].items(), 1):
        require(sha((ROOT / name).read_bytes()) == digest, 'OLD_FILE_CHANGED:' + name)
        if i % 4000 == 0:
            progress(old_files_verified=i)
    archive = read_json(ROOT / 'results/phase11/provenance/archive.json')
    require(archive['commit'] == BASE and archive['tag'] == 'archive-phase10-20261017', 'ARCHIVE_IDENTITY')
    production, data = verify_freeze('production'), verify_freeze()
    require(len(production['files']) == 78 and len(data['files']) == 86, 'FREEZE_COUNT')
    return baseline, production, data


def independent_reference():
    from hydrate_phase11 import hydrate
    import build_phase11_heldout as main
    import build_phase11_challenge as challenge
    hydrate()  # Only ignored work/ is restored, by checked copies of archived bytes.
    pretty = lambda value: (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    cases = main.build_cases()
    refs = [main.reference_record(c) for c in cases]
    scaling = main.scaling_cases()
    scaled_refs = [main.reference_record(c) for c in scaling]
    challenge_cases = challenge.build_cases()
    challenge_refs = [challenge.ref.reference_record(c) for c in challenge_cases]
    require((len(cases), len({c['family'] for c in cases}), len(challenge_cases),
             len({c['family'] for c in challenge_cases}), len(scaling)) == (48, 24, 24, 12, 12),
            'REFERENCE_COHORT_GRID')
    # Frozen generator used str(Path), so exactly one descriptive path is
    # platform-specific. Validate its canonical form, then retain the original
    # Windows spelling for exact-byte archived metadata reconstruction.
    challenge_coverage = challenge.coverage(challenge_cases, challenge_refs)
    prior_path = challenge_coverage['novelty']['prior_sources'][-1]
    require(prior_path['path'].replace('\\', '/') == 'work/phase11-reference-firstpass/heldout.jsonl',
            'CHALLENGE_PRIOR_PATH')
    prior_path['path'] = 'work\\phase11-reference-firstpass\\heldout.jsonl'
    validation = challenge.checker_validation(challenge_cases, challenge_refs)
    outputs = {
        'main': {'heldout.jsonl': main.jsonl_bytes(cases), 'reference.jsonl': main.jsonl_bytes(refs),
                 'scaling.jsonl': main.jsonl_bytes(scaling), 'reference_scaling.jsonl': main.jsonl_bytes(scaled_refs),
                 'coverage.json': pretty(main.audit(cases, refs))},
        'challenge': {'challenge.jsonl': main.jsonl_bytes(challenge_cases),
                      'reference_challenge.jsonl': main.jsonl_bytes(challenge_refs),
                      'coverage.json': pretty(challenge_coverage), 'checker_validation.json': pretty(validation)}}
    provenance = {}
    for cohort, artifacts in outputs.items():
        directory = ROOT / 'results/phase11/reference' / cohort
        archived = directory / 'first-pass'
        prov = read_json(archived / 'provenance.json')
        provenance[cohort] = prov
        require(prov['production_modules_consulted'] is False and prov['model_outcomes_consulted'] is False,
                'REFERENCE_ATTESTATION_CHANGED')
        existing_identical(directory / 'provenance.json', (archived / 'provenance.json').read_bytes())
        for name, digest in prov['source_sha256'].items():
            require(sha((ROOT / name).read_bytes()) == digest, 'REFERENCE_SOURCE_CHANGED:' + name)
        require(set(artifacts) == set(prov['artifact_sha256']), 'REFERENCE_ARTIFACT_INVENTORY')
        for name, content in artifacts.items():
            existing_identical(archived / name, content)
            require(sha(content) == prov['artifact_sha256'][name], 'FIRSTPASS_HASH:' + name)
            existing_identical(ROOT / 'data/phase11' / name if name.endswith('.jsonl') else directory / name, content)
        material = read_json(ROOT / f'results/phase11/provenance/materialization_{cohort}.json')
        require(material['firstpass_provenance_sha256'] == sha((archived / 'provenance.json').read_bytes()), 'MATERIALIZATION_REFERENCE')
        require(material['production_freeze_sha256'] == sha((ROOT / 'results/phase11/provenance/production_freeze.json').read_bytes()), 'MATERIALIZATION_FREEZE')
        require(datetime.fromisoformat(prov['authored_at_utc']) < datetime.fromisoformat(material['materialized_at_utc']), 'REFERENCE_CHRONOLOGY')
    require(provenance['challenge']['original_firstpass_artifact_sha256'] == provenance['main']['artifact_sha256'], 'CHALLENGE_REPLACED_MAIN')
    require(provenance['challenge']['original_firstpass_provenance_sha256'] == sha((ROOT / 'results/phase11/reference/main/provenance.json').read_bytes()), 'CHALLENGE_MAIN_PROVENANCE')
    attestation = read_json(ROOT / 'results/phase11/provenance/initial_reference_attestation.json')
    require(attestation['generator_sha256'] == provenance['main']['source_sha256']['scripts/build_phase11_heldout.py']
            and attestation['heldout_sha256'] == provenance['main']['artifact_sha256']['heldout.jsonl'], 'INITIAL_REFERENCE_ATTESTATION')
    from validate_phase11_reference import validate
    raw_summary = read_json(ROOT / 'results/phase11/reference/agreement_summary.json')
    try:
        validate(False)
    except AssertionError as exc:
        require(json.loads(str(exc)) == raw_summary and raw_summary['mismatches'] == 2,
                'UNEXPECTED_RAW_SEMANTIC_MISMATCH')
    else:
        raise ValueError('EXPECTED_PRESERVED_RAW_ERROR_NAME_DIFFERENCES_MISSING')
    normalized = validate(True)
    require(normalized['comparisons'] == normalized['matching'] == 1006 and normalized['normalized_error_records'] == 2,
            'NORMALIZED_REFERENCE_AGREEMENT')
    from check_reference_phase11 import validate_main
    main_validation = validate_main(cases, refs)
    for directory in ('results/phase11/reference/main', 'results/phase11/reference/main/first-pass'):
        require(read_json(ROOT / directory / 'exhaustive_checker_validation.json') == main_validation,
                'MAIN_EXHAUSTIVE_CHECKER_REPLAY')
    progress(reference_reproduced=True, semantic_comparisons=1006)
    return {'cases': 72, 'families': 36, 'scaling_siblings': 12,
            'semantic_comparisons': 1006, 'raw_error_name_differences_retained': 2,
            'challenge_checker_validation': validation,
            'main_exhaustive_check': main_validation,
            'provenance_scope': 'local timestamps and author attestations; not an externally preregistered audit',
            'portable_metadata_normalization': 'one archived challenge provenance path separator; no dataset changes'}


def tokenizer_preflight():
    cache = Path(os.environ.get('TIKTOKEN_CACHE_DIR', ROOT / 'work/tiktoken')).resolve()
    path = cache / TOKENIZER_CACHE_NAME
    require(path.is_file(), 'TOKENIZER_CACHE_MISSING: install dependency cache before offline verification')
    require(sha(path.read_bytes()) == TOKENIZER_CACHE_SHA256, 'TOKENIZER_CACHE_HASH_MISMATCH')
    os.environ['TIKTOKEN_CACHE_DIR'] = str(cache)
    import tiktoken
    require(tiktoken.__version__ == '0.12.0', 'TOKENIZER_VERSION_MISMATCH')
    return {'encoding': 'o200k_base', 'package_version': '0.12.0',
            'cache_sha256': TOKENIZER_CACHE_SHA256,
            'scope': 'surrogate prompt length control, not a verified Luna tokenizer'}


def acquisition():
    from run_phase11 import prepare, acquire_stream, finalize, request_cost
    old = (ROOT / 'results/phase10/api/budget.jsonl').read_bytes()
    ledger = (ROOT / 'results/phase11/api/budget.jsonl').read_bytes()
    require(ledger.startswith(old) and old.endswith(b'\n') and ledger.endswith(b'\n'), 'BUDGET_PREFIX_CHANGED')
    cs, specs, budget, audit = prepare()
    lookup = {c['case_id']: c for c in cs}
    api = ROOT / 'results/phase11/api'
    observations = read_rows(api / 'observations.jsonl')
    saved = {r['stream_id']: r for r in observations}
    require(len(saved) == len(observations) == len(specs) == 288, 'STREAM_GRID')
    request_ids, job_ids, reservations = [], [], []
    for i, spec in enumerate(specs, 1):
        replay = acquire_stream(spec, lookup[spec['case_id']], api, invoke=None)
        require(replay == saved[spec['stream_id']], 'STREAM_REPLAY_DIFFERS:' + spec['stream_id'])
        for decision in replay['decisions']:
            job = read_json(api / 'requests' / (decision['job_id'] + '.json'))
            raw = read_json(ROOT / decision['raw_ref'])
            fingerprint = sha(json.dumps({'request': raw['request'], 'replicate': raw['replicate']},
                                        sort_keys=True, ensure_ascii=False).encode())
            require(fingerprint == raw['request_hash'] == job['expected_request_hash'] == decision['request_hash'], 'REQUEST_FINGERPRINT')
            require(raw['tag'] == job['job_id'] and raw['replicate'] == spec['replicate'], 'REQUEST_STREAM_BINDING')
            require(job['local_tokens']['graph'] == job['local_tokens']['padding'], 'SURROGATE_TOKEN_CONTROL')
            require(read_json(api / 'dispatch' / (job['job_id'] + '.json')) ==
                    {'job_id': job['job_id'], 'request_hash': fingerprint}, 'DISPATCH_BINDING')
            require(request_cost(raw, job) == (decision['cost_upper_usd'], decision['cost_basis']), 'REQUEST_COST')
            rid = raw['reservation_id']
            entry = budget.entries[rid]
            require(entry['model'] == job['model'] and entry['reserved_usd'] == job['reservation_upper_usd'], 'RESERVATION_BINDING')
            if entry['status'] == 'settled':
                require(entry['usage'] == raw['usage'] and entry['cost_usd'] == decision['cost_upper_usd'], 'SETTLED_USAGE')
            else:
                require(raw['status'] == 'api_error' and entry['status'] == 'reserved'
                        and decision['cost_upper_usd'] == entry['reserved_usd'], 'UNKNOWN_USAGE_EXPOSURE')
            request_ids.append(fingerprint)
            job_ids.append(job['job_id'])
            reservations.append(rid)
        if i % 48 == 0:
            progress(streams_reproduced=i)
    for sequence, label in ((request_ids, 'REQUEST'), (job_ids, 'JOB'), (reservations, 'RESERVATION')):
        require(len(sequence) == len(set(sequence)) == 1605, 'REUSED_OR_MISSING_' + label)
    for directory, expected in (('requests', job_ids), ('dispatch', job_ids), ('decisions', job_ids),
                                ('raw', request_ids), ('streams', saved)):
        require({p.stem for p in (api / directory).glob('*.json')} == set(expected), 'API_FILE_INVENTORY:' + directory)
    previous = {r['reservation_id']: r for r in map(json.loads, old.splitlines())}
    suffix = [json.loads(line) for line in ledger[len(old):].splitlines()]
    by_id = defaultdict(list)
    exposure = dict(previous)
    max_exposure = sum(r.get('cost_usd', r['reserved_usd']) for r in exposure.values())
    materialized = max(datetime.fromisoformat(read_json(ROOT / f'results/phase11/provenance/materialization_{c}.json')['materialized_at_utc']) for c in ('main', 'challenge'))
    for row in suffix:
        rid = row['reservation_id']
        require(rid not in previous, 'INHERITED_RESERVATION_REWRITTEN')
        by_id[rid].append(row)
        require(datetime.fromisoformat(row['timestamp']) >= materialized, 'ACQUISITION_PRECEDES_DATA_MATERIALIZATION')
        exposure[rid] = row
        current = sum(r.get('cost_usd', r['reserved_usd']) for r in exposure.values())
        max_exposure = max(max_exposure, current)
        require(current <= budget.limit <= CAP, 'LEDGER_HISTORICAL_CAP_EXCEEDED')
    require(set(by_id) == set(budget.entries) - set(previous) == set(reservations), 'UNATTRIBUTED_RESERVATIONS')
    require(all([r['status'] for r in rows] in (['reserved'], ['reserved', 'settled']) for rows in by_id.values()), 'RETRY_OR_LEDGER_LIFECYCLE')
    require(Counter(r['status'] for r in suffix) == {'reserved': 1605, 'settled': 1603}, 'LEDGER_COUNTS')
    require(budget.total_cost - audit['inherited_upper_usd'] <= CAMPAIGN_CAP, 'CAMPAIGN_CAP_EXCEEDED')
    summary = finalize(specs, budget, audit)
    return {'streams': len(specs), 'unique_requests': len(request_ids), 'new_reservations': len(reservations),
            'maximum_recorded_reserved_exposure_usd': max_exposure, 'summary': summary}


def experiment_replay():
    from experiment_phase11 import deterministic, integrated
    deterministic_summary = deterministic()
    integrated_summary = integrated()
    require(deterministic_summary['semantic_pairs'] == 1006 and deterministic_summary['policy_conditions'] == 12320
            and deterministic_summary['recovery_conditions'] == 15696
            and deterministic_summary['previous_contract_comparisons'] == 218, 'DETERMINISTIC_GRID')
    require(integrated_summary['integrated_rows'] == 13824, 'INTEGRATED_GRID')
    return {'deterministic': deterministic_summary, 'integrated': integrated_summary}


def isolation_capsules():
    from container_phase11 import build, cases, command, payload, IMAGE
    cs = cases()
    result = {}
    for track in ('deterministic', 'integrated'):
        jobs, expected = build(track)
        directory = ROOT / 'results/phase11/isolation' / track
        require(read_chunks(directory / 'jobs') == jobs, 'ISOLATION_JOB_REBUILD:' + track)
        require(read_chunks(directory / 'results') == expected, 'ISOLATION_RECORDED_RESULTS:' + track)
        combined = []
        expected_batches = {f'{i:03}' for i in range(1, (len(jobs) + 249) // 250 + 1)}
        require({p.name for p in (directory / 'batches').iterdir() if p.is_dir()} == expected_batches, 'ISOLATION_BATCH_INVENTORY')
        for i, start in enumerate(range(0, len(jobs), 250), 1):
            subset = jobs[start:start + 250]
            out = directory / 'batches' / f'{i:03}'
            digest = sha(payload(subset, cs))
            require(read_json(out / 'plan.json') == {'conditions': len(subset), 'image': IMAGE, 'command': command(),
                'payload_sha256': digest, 'jobs_sha256': sha(rb(subset)),
                'scope': 'fresh memory per condition; shared batch container; no network or host mounts'}, 'ISOLATION_PLAN')
            require(read_json(out / 'intent.json') == {'payload_sha256': digest}, 'ISOLATION_INTENT')
            require(read_json(out / 'exit.json') == {'exit_code': 0}, 'ISOLATION_EXIT')
            require((out / 'stderr.txt').read_bytes() == b'', 'ISOLATION_STDERR')
            stdout = read_json(out / 'stdout.json')
            require(stdout['uid'] == 65534 and stdout['rows'] == expected[start:start + 250], 'ISOLATION_STDOUT')
            combined.extend(stdout['rows'])
        require(combined == expected, 'ISOLATION_CONCATENATION')
        audit = {'conditions': len(expected), 'containers': len(expected_batches), 'exact_agreement': True,
                 'null_abstention_results': sum(r['result'] is None for r in expected), 'uid': 65534, 'image': IMAGE}
        require(read_json(directory / 'audit.json') == audit, 'ISOLATION_AUDIT')
        result[track] = audit
        progress(isolation_capsules_verified=track, conditions=len(expected))
    result['verification_scope'] = 'recorded Docker command/input/output/exit checked against fresh local semantic replay; no fresh Docker launch'
    return result


def analysis_and_figures(render_figures=False):
    from analyze_phase11 import build_analysis, csv_bytes
    result = build_analysis()
    import plot_phase11 as plot
    source = ROOT / 'results/phase11/analysis'
    directory = ROOT / 'results/phase11/figures'
    manifest = read_json(directory / 'manifest.json')
    require(manifest['analysis_manifest_sha256'] == sha((source / 'manifest.json').read_bytes()), 'FIGURE_ANALYSIS_BINDING')
    for name, digest in manifest['files'].items():
        require(sha((directory / name).read_bytes()) == digest, 'FIGURE_HASH:' + name)
    definitions = [('deterministic_acquisition', plot.deterministic), ('matched_model_comparison', plot.model_comparison),
                   ('bounded_recovery', plot.recovery), ('actual_api_costs', plot.actual_costs),
                   ('paired_family_effects', plot.family_effects), ('dependent_scaling', plot.scaling)]
    require(set(manifest['files']) == {name + '.' + ext for name, _ in definitions for ext in ('png', 'svg', 'pdf', 'csv')}, 'FIGURE_INVENTORY')
    for name, function in definitions:
        fig, rows = function(result['tables'])
        try:
            existing_identical(directory / (name + '.csv'), csv_bytes(rows))
            if render_figures:
                for ext, data in plot.figure_bytes(fig).items():
                    existing_identical(directory / (name + '.' + ext), data)
        finally:
            plot.plt.close(fig)
    return {'analysis_tables': len(result['tables']), 'figures': len(definitions),
            'scope': 'exact numeric table and plotted-data replay; all archived image hashes checked',
            'render_byte_replay': 'optional --render-figures is environment-sensitive and reported separately'}


def recorded_trace_audit():
    from audit_phase11_traces import audit
    result = audit()
    directory = ROOT / 'results/phase11/trace_audit'
    existing_identical(directory / 'summary.json', jb(result['summary']))
    require(read_chunks(directory / 'detail') == result['details'], 'INDEPENDENT_TRACE_AUDIT_DETAILS')
    counts = result['summary']['all_rows']
    require((counts['rows'], counts['non_null_executions'], counts['null_executions']) == (42846, 28482, 14364),
            'TRACE_AUDIT_DENOMINATORS')
    return {'classification': result['summary']['classification'],
            'summary_sha256': sha((directory / 'summary.json').read_bytes()),
            'all_rows': counts,
            'scope': 'independent measurement reconstruction from recorded traces; no new executions'}


def physical_goal_audit():
    from analyze_phase11_physical_goal import analyze, csv_bytes
    result = analyze()
    directory = ROOT / 'results/phase11/physical_goal'
    existing_identical(directory / 'summary.json', jb(result['summary']))
    for name in ('conditions', 'contrasts'):
        existing_identical(directory / (name + '.jsonl'), rb(result[name]))
        existing_identical(directory / (name + '.csv'), csv_bytes(result[name]))
    summary = result['summary']
    require((summary['rows'], summary['null_execution_rows'], summary['condition_rows'], summary['contrast_rows'],
             summary['saved_goal_disagreement_rows']) == (15696, 2880, 1512, 24, 0), 'PHYSICAL_GOAL_AUDIT_GRID')
    return {k: summary[k] for k in ('classification', 'rows', 'null_execution_rows', 'physical_goal_rows',
                                  'authorized_goal_rows', 'saved_goal_disagreement_rows', 'condition_rows',
                                  'contrast_rows', 'detail_sha256', 'source_sha256')}


def verify(render_figures=False):
    tokenizer = tokenizer_preflight()
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex'):
            stack.enter_context(patch(target, side_effect=RuntimeError('NETWORK_DISABLED_IN_OFFLINE_VERIFIER')))
        # Every later module import receives a check-only immutable writer.
        for name in ('phase6_common', 'phase10_common', 'phase11_common'):
            module = __import__(name)
            stack.enter_context(patch.object(module, 'immutable', existing_identical))
        baseline, production, data = baseline_and_freezes()
        reference = independent_reference()
        api = acquisition()
        experiments = experiment_replay()
        isolation = isolation_capsules()
        analysis = analysis_and_figures(render_figures)
        trace_audit = recorded_trace_audit()
        physical_goal = physical_goal_audit()
        from counterexamples_phase11 import examples
        existing_identical(ROOT / 'results/phase11/counterexamples/results.json', jb(examples()))
        from reaudit_phase11_protocol import reaudit
        parser = reaudit()
    return {'status': 'pass', 'baseline_commit': BASE, 'baseline_files_unchanged': len(baseline['files']),
            'production_frozen_files': len(production['files']), 'data_frozen_files': len(data['files']),
            'tokenizer': tokenizer, 'reference': reference, 'acquisition': api, 'experiments': experiments,
            'isolation': isolation, 'analysis': analysis, 'counterexamples_reproduced': 4,
            'recorded_trace_audit': trace_audit,
            'physical_goal_audit': physical_goal,
            'historical_parser_reaudit': parser, 'network_calls': 0, 'new_provider_calls': 0,
            'cumulative_upper_usd': api['summary']['cumulative_upper_usd'],
            'remaining_usd': CAP - api['summary']['cumulative_upper_usd']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', action='store_true', help='Write the two final release manifests once, after all evidence exists.')
    parser.add_argument('--render-figures', action='store_true', help='Additionally demand exact PNG/SVG/PDF rerender bytes in this rendering environment.')
    args = parser.parse_args()
    value = verify(args.render_figures)
    hashes = release_files()
    value['release_files'] = len(hashes)
    if args.release:
        release_write(ROOT / 'results/phase11/provenance/release_hashes.json', jb(hashes))
        release_write(ROOT / 'results/phase11/provenance/release_verification.json', jb(value))
    else:
        existing_identical(ROOT / 'results/phase11/provenance/release_hashes.json', jb(hashes))
        existing_identical(ROOT / 'results/phase11/provenance/release_verification.json', jb(value))
    progress(**value)
    if args.render_figures:
        progress(optional_exact_render_replay='pass')


if __name__ == '__main__':
    main()
