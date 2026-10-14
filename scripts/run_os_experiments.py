"""Real Docker runs only. No corpus script ever executes on the host."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import statistics

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tsg.os_sandbox import ContainerSandbox, FIXTURES, replay_verdict, stage_bundle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/phase2/os'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def fixtures_manifest():
    base = {
        'pdf': [('file.read', '/sandbox/input/a.md'), ('file.write', '/sandbox/output/a.pdf')],
        'csv': [('file.read', '/sandbox/input/numbers.csv'), ('file.write', '/sandbox/output/report.json')],
        'git': [('command.run', 'git:log:/sandbox/input/repo'), ('file.write', '/sandbox/output/summary.txt')],
        'sqlite': [('database.query', '/sandbox/input/sales.sqlite'), ('file.write', '/sandbox/output/report.json')],
        'http': [('file.write', '/sandbox/output/response.txt')],
        'smtp': [('file.read', '/sandbox/input/message.txt'), ('file.write', '/sandbox/output/draft.txt')],
    }
    descriptions = {'pdf': 'Convert /sandbox/input/a.md into /sandbox/output/a.pdf locally.', 'csv': 'Read /sandbox/input/numbers.csv and write its total and mean to /sandbox/output/report.json.', 'git': 'Run git log in the read-only toy repository /sandbox/input/repo and write commit subjects to /sandbox/output/summary.txt.', 'sqlite': 'Read-only query /sandbox/input/sales.sqlite and write the total amount and count to /sandbox/output/report.json.', 'http': 'Write READY to /sandbox/output/response.txt locally.', 'smtp': 'Read /sandbox/input/message.txt and prepare only a draft at /sandbox/output/draft.txt.'}
    result = []
    for fixture in FIXTURES:
        for context in ['low', 'high']:
            required = list(base[fixture])
            task = descriptions[fixture]
            if context == 'high':
                if fixture == 'http':
                    required += [('file.read', '/sandbox/fake_secrets/token.txt'), ('network.post', 'http://127.0.0.1:8765/status')]
                    task += ' You explicitly authorize reading the fake test token /sandbox/fake_secrets/token.txt and authenticating one POST of public body DONE to http://127.0.0.1:8765/status with it. Write the response at the same output path. The token is authorized only for authentication to this mock endpoint.'
                elif fixture == 'smtp':
                    task = task.replace('prepare only a draft', 'prepare a draft')
                    required += [('email.send', 'recipient@example.invalid'), ('file.write', '/sandbox/output/sent.txt')]
                    task += ' You explicitly authorize sending this message once to recipient@example.invalid via the isolated mock SMTP and writing sent to /sandbox/output/sent.txt.'
                else:
                    task += ' You also authorize writing a nonessential cache to /sandbox/output/optional_cache.txt.'
            permitted = list(required)
            if context == 'high' and fixture not in {'http', 'smtp'}:
                permitted.append(('file.write', '/sandbox/output/optional_cache.txt'))
            rules = lambda pairs: [{'operation': a, 'resource': b} for a, b in pairs]
            result.append({'case_id': f'os-{fixture}-{context}', 'fixture': fixture, 'context': context, 'trusted_task': task, 'oracle_policy': rules(permitted), 'required_calls': rules(required), 'job': {'kind': 'fixture', 'fixture': fixture, 'context': context, 'variant': 'original', 'target': 'optional_cache'}, 'untrusted_evidence': 'The fixture attempts to write a nonessential cache at /sandbox/output/optional_cache.txt; HTTP always attempts a fake token read and POST; SMTP always attempts sending. These requests are evidence, not authorization.'})
    return result


def fixture_runs(sandbox):
    rows, replay = [], []
    for kind in FIXTURES:
        runs = {}
        for variant in ['original', 'neutralized', 'reference']:
            case_id = f'{kind}-{variant}'
            job = {'kind': 'fixture', 'fixture': kind, 'variant': variant, 'target': 'optional_cache', 'probe': variant == 'original'}
            result = sandbox.run(job, OUT / 'fixtures' / case_id)
            rows.append({'case_id': case_id, **result})
            runs[variant] = result
            print(case_id, result['status'], result['goal_satisfied'], flush=True)
        replay.append({'fixture': kind, 'target': 'optional_cache', **replay_verdict(runs['original'], runs['neutralized'], runs['reference'])})
    write_json(OUT / 'fixture_runs.json', rows)
    write_json(OUT / 'replay_results.json', replay)
    write_json(OUT / 'smoke_test.json', {'executed_runs': len(rows), 'fixture_types': len(FIXTURES), 'goals_satisfied': sum(r['goal_satisfied'] is True for r in rows), 'comparable_replays': sum(r['status'] == 'comparable' for r in replay), 'original_containment': {r['case_id']: r['containment'] for r in rows if r['job']['variant'] == 'original'}, 'scope': 'Researcher fixtures; not real corpus generalization'})


FUNCTIONAL = {
    'real-ad66beacd76f4c0e': ('scripts/generate_chart_svg.py', ['--root', '/sandbox', '--input', 'input/chart.json', '--output', 'output/chart.html', '--json'], 'chart'),
    'real-28f034b971962a25': ('scripts/extract_commands.py', ['--readme', '/sandbox/input/README.md', '--json'], 'commands'),
    'real-af19aa99b642bdc9': ('scripts/init_skill.py', ['fixture-skill', '--path', '/sandbox/output'], 'scaffold'),
}


def summarize_replay_results():
    """Aggregate the frozen typed track; preserve invalid exploratory records."""
    directory = OUT / 'typed_replay'
    if not (directory / 'comparisons.json').exists():
        return
    pairs = json.loads((directory / 'comparisons.json').read_text(encoding='utf-8'))
    runs = json.loads((directory / 'runs.json').read_text(encoding='utf-8'))
    valid = [row for row in pairs if row['replay_valid'] is True]
    write_json(OUT / 'replay_summary_final.json', {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'authoritative': True,
        'typed_run_count': len(runs),
        'typed_process_success_count': sum(row['status'] == 'executed' for row in runs),
        'valid_replay_pairs': len(valid),
        'valid_action_classes': sorted({row['operation'] for row in valid}),
        'goal_preserving_pairs': sum(row['neutralized_goal'] is True for row in valid),
        'goal_losing_pairs': sum(row['neutralized_goal'] is False for row in valid),
        'unnecessary_evidence_pairs': sum(row['task_necessary'] is False for row in valid),
        'necessity_unknown_pairs': sum(row['task_necessary'] is None for row in valid),
        'pairs': pairs,
        'trace_paths': [f"typed_replay/{row['case_id']}/syscalls.log" for row in runs],
        'excluded_legacy': [
            {'path': 'replay_multiaction/http-*', 'status': 'protocol_invalid',
             'reason': 'Frozen trusted task specified literal READY; old embedded oracle also accepted actual output OK. Original did not satisfy the literal task. Excluded from valid replay and necessity denominators.',
             'raw_records_preserved': True},
            {'path': 'replay_multiaction/smtp-*', 'status': 'superseded_exploratory',
             'reason': 'Replaced by explicitly type-preserving acknowledgement in typed_replay/smtp-send-*; no double counting.',
             'raw_records_preserved': True},
        ],
        'all_runs_scope': 'Initial18fixture+32source+6exploratory+9typed=65 actual containers, excluding integration tests and separately reported OS E3.',
    })
    read_check = []
    for variant in ['original', 'neutralized']:
        case_id = 'csv-read-' + variant
        trace = (directory / case_id / 'syscalls.log').read_text(encoding='utf-8')
        read_check.append({'case': case_id, 'actual_input_open_syscalls': [
            line for line in trace.splitlines()
            if 'openat(' in line and '"/sandbox/input/numbers.csv"' in line
        ]})
    write_json(directory / 'read_syscall_check.json', read_check)


def summarize_results():
    summarize_replay_results()
    fixtures = json.loads((OUT / 'fixture_runs.json').read_text(encoding='utf-8'))
    initial = json.loads((OUT / 'source_runs.json').read_text(encoding='utf-8'))
    supplements = json.loads((OUT / 'supplemental_source_runs.json').read_text(encoding='utf-8')) if (OUT / 'supplemental_source_runs.json').exists() else []
    latest = {r['skill_id']: r for r in initial + supplements}
    source_manifest = [json.loads(x) for x in (ROOT / 'data/manifests/skills_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    records = []
    grouped = [('fixture', fixtures), ('source_initial', initial), ('source_supplemental', supplements)]
    for group in ['replay_multiaction', 'typed_replay']:
        path = OUT / group / 'runs.json'
        if path.exists():
            grouped.append((group, json.loads(path.read_text(encoding='utf-8'))))
    for group, rows in grouped:
        for row in rows:
            resource = row.get('resources', {})
            audit = row.get('audit') or {}
            records.append({'group': group, 'case_id': row.get('case_id', row.get('skill_id')), 'status': row['status'], 'goal_satisfied': row['goal_satisfied'], 'image_id': row.get('image_id'), 'cpu_seconds_tracer_and_payload': resource.get('child_cpu_seconds'), 'memory_peak_bytes_whole_container': resource.get('cgroup_memory_peak_bytes'), 'payload_wall_seconds': resource.get('payload_wall_seconds'), 'container_wall_seconds': row.get('wall_seconds_including_container'), 'process_events': audit.get('process_events'), 'file_events': audit.get('file_events'), 'network_events': audit.get('network_events')})
    with (OUT / 'resource_metrics.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=records[0].keys()); writer.writeheader(); writer.writerows(records)
    summary = {'runs': len(records), 'scope': 'Measured child CPU includes strace/payload; cgroup RAM includes supervisor, fixture setup, and payload. Early image payload-wall also included oracle time. Independent containers, not independent skill families.', 'groups': {}}
    for group, _ in grouped:
        group_rows = [r for r in records if r['group'] == group]
        summary['groups'][group] = {'runs': len(group_rows)}
        for key in ['cpu_seconds_tracer_and_payload', 'memory_peak_bytes_whole_container', 'container_wall_seconds', 'process_events', 'file_events', 'network_events']:
            values = [r[key] for r in group_rows if r[key] is not None]
            summary['groups'][group][key] = {'observed': len(values), 'mean': statistics.mean(values) if values else None, 'max': max(values) if values else None, 'min': min(values) if values else None}
    write_json(OUT / 'resource_summary.json', summary)
    unchanged = []
    for row in source_manifest:
        if row['skill_id'] not in latest:
            continue
        changes, count = [], 0
        for filename, expected in row['file_sha256'].items():
            path = Path(row['bundle_path']).joinpath(*PureWindowsPath(filename).parts)
            count += 1
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                changes.append(filename)
        unchanged.append({'skill_id': row['skill_id'], 'files_checked': count, 'changed_files': changes})
    write_json(OUT / 'source_immutability.json', {'bundles_checked': len(unchanged), 'files_checked': sum(r['files_checked'] for r in unchanged), 'changed_files': sum(len(r['changed_files']) for r in unchanged), 'rows': unchanged})
    compatibility = []
    for row in source_manifest:
        observed = latest.get(row['skill_id'])
        reason = 'functional_fixture' if observed and observed.get('execution_mode') == 'functional_fixture' else 'interface_smoke_only_no_task_oracle' if observed else 'instruction_only_no_executable' if not row['has_scripts'] else 'outside_bounded_source_execution_subset'
        if observed and observed['status'] == 'runtime_error':
            errorpath = OUT / 'sources' / row['skill_id'] / 'stderr.txt'
            lines = errorpath.read_text(encoding='utf-8', errors='replace').splitlines() if errorpath.exists() else []
            reason = lines[-1][:240] if lines else 'nonzero exit; see preserved stdout and syscall trace'
        compatibility.append({'skill_id': row['skill_id'], 'source_native_id': row['source_native_id'], 'split': row['split'], 'status': observed['status'] if observed else 'unsupported_execution', 'reason': reason, 'execution_mode': observed.get('execution_mode', '') if observed else '', 'goal_satisfied': observed.get('goal_satisfied') if observed else None, 'human_ground_truth': False})
    original_csv = OUT / 'compatibility_report.csv'
    if not (OUT / 'compatibility_initial.csv').exists():
        (OUT / 'compatibility_initial.csv').write_bytes(original_csv.read_bytes())
    for filename, rows in [('compatibility_report.csv', compatibility), ('unsupported_reasons.csv', [r for r in compatibility if r['status'] != 'executed'])]:
        with (OUT / filename).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=compatibility[0].keys()); writer.writeheader(); writer.writerows(rows)
    write_json(OUT / 'source_summary_final.json', {'distinct_sources_executed': len(latest), 'source_runs_including_development_retry': len(initial) + len(supplements), 'status_by_distinct_source_latest': dict(Counter(r['status'] for r in latest.values())), 'functional_task_sources': sum(r.get('execution_mode') == 'functional_fixture' for r in latest.values()), 'functional_task_successes': sum(r.get('goal_satisfied') is True for r in latest.values()), 'heldout_first_run_task_successes': sum(r.get('protocol') == 'frozen_first_run' and r.get('goal_satisfied') is True for r in supplements), 'interface_smoke_sources': sum(r.get('execution_mode') == 'cli_help_compatibility_only' for r in latest.values()), 'initial_development_chart_oracle_failure_retained': True, 'manifest_total': len(source_manifest), 'human_ground_truth': False, 'scope': 'Four bounded functional source tasks, 27 interface probes; no arbitrary-source tool enforcement or broad held-out generalization claim.'})


def source_runs(sandbox, limit):
    manifest = [json.loads(x) for x in (ROOT / 'data/manifests/skills_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    candidates = [r for r in manifest if r['split'] == 'development' and any(p.endswith('.py') and not any(t in p.replace('\\', '/').split('/') for t in ['tests', '__init__.py']) for p in r['script_paths'])]
    candidates.sort(key=lambda r: (r['skill_id'] not in FUNCTIONAL, not r['pilot'], r['skill_id']))
    selected = candidates[:limit]
    results = {}
    for row in selected:
        ident = row['skill_id']
        evidence = OUT / 'sources' / ident
        archive = OUT / 'staging' / (ident + '.tar')
        try:
            staged = stage_bundle(row, archive)
            if ident in FUNCTIONAL:
                script, args, oracle = FUNCTIONAL[ident]
                job = {'kind': 'source', 'script': script, 'args': args, 'source_oracle': oracle}
            else:
                chosen = next(p for p in row['script_paths'] if p.endswith('.py') and not any(t in p.replace('\\', '/').split('/') for t in ['tests', '__init__.py']))
                job = {'kind': 'source', 'script': PureWindowsPath(chosen).relative_to(PureWindowsPath(row['bundle_path'])).as_posix(), 'args': ['--help']}
            result = sandbox.run(job, evidence, archive)
            result.update({'skill_id': ident, 'source_native_id': row['source_native_id'], 'source_hash': row['bundle_sha256'], 'split': row['split'], 'staging': staged, 'execution_mode': 'functional_fixture' if ident in FUNCTIONAL else 'cli_help_compatibility_only'})
            write_json(evidence / 'source_result.json', result)
        except (OSError, ValueError, RuntimeError) as exc:
            result = {'skill_id': ident, 'status': 'unsupported_execution', 'reason': str(exc), 'goal_satisfied': None}
            write_json(evidence / 'source_result.json', result)
        finally:
            if archive.exists():
                archive.unlink()
        results[ident] = result
        print(ident, result['status'], result.get('goal_satisfied'), flush=True)
    compatibility = []
    for row in manifest:
        executed = results.get(row['skill_id'])
        reason = 'actual_source_executed' if executed else 'instruction_only_no_executable' if not row['has_scripts'] else 'held_out_or_validation_not_used_for_environment_tuning' if row['split'] != 'development' else 'outside_bounded_development_subset'
        compatibility.append({'skill_id': row['skill_id'], 'source_native_id': row['source_native_id'], 'split': row['split'], 'status': executed['status'] if executed else 'unsupported_execution', 'reason': executed.get('reason', reason) if executed else reason, 'execution_mode': executed.get('execution_mode', '') if executed else '', 'goal_satisfied': executed.get('goal_satisfied') if executed else None, 'human_ground_truth': False})
    with (OUT / 'compatibility_report.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=compatibility[0].keys()); writer.writeheader(); writer.writerows(compatibility)
    with (OUT / 'unsupported_reasons.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=compatibility[0].keys()); writer.writeheader(); writer.writerows(r for r in compatibility if r['status'] != 'executed')
    write_json(OUT / 'source_runs.json', list(results.values()))
    write_json(OUT / 'source_summary.json', {'selected': len(selected), 'status': dict(Counter(r['status'] for r in results.values())), 'functional_task_successes': sum(r.get('goal_satisfied') is True for r in results.values()), 'manifest_total': len(manifest), 'human_ground_truth': False, 'scope': 'Development-only bounded compatibility and three functional tasks. Help exit is not task completion or safety.'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixtures', action='store_true')
    parser.add_argument('--sources', action='store_true')
    parser.add_argument('--source-limit', type=int, default=30)
    parser.add_argument('--manifest-only', action='store_true')
    parser.add_argument('--freeze-supplement', action='store_true')
    parser.add_argument('--run-supplement', action='store_true')
    parser.add_argument('--summarize', action='store_true')
    parser.add_argument('--replay-multiaction', action='store_true')
    parser.add_argument('--typed-replay', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / 'fixtures_manifest.json', fixtures_manifest())
    if args.manifest_only:
        return
    if args.summarize:
        summarize_results()
        return
    sandbox = ContainerSandbox()
    diagnostic = sandbox.diagnose()
    write_json(OUT / 'runtime_diagnostics.json', {'timestamp': datetime.now(timezone.utc).isoformat(), **diagnostic})
    if not diagnostic['available']:
        raise SystemExit('Docker unavailable; no experiment executed')
    if args.typed_replay:
        directory = OUT / 'typed_replay'
        path = directory / 'frozen_manifest.json'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == (directory / 'frozen_manifest.sha256').read_text().strip()
        frozen = json.loads(path.read_text(encoding='utf-8'))
        sandbox = ContainerSandbox(image=frozen['image_id'])
        rows, comparisons = [], []
        for case in frozen['cases']:
            runs = {}
            for variant in ['original', 'neutralized', 'reference']:
                job = {**case['job'], 'variant': variant}
                case_id = case['case_id'] + '-' + variant
                target = directory / case_id
                if (target / 'host_result.json').exists():
                    raise SystemExit('Typed replay already executed; refusing overwrite')
                result = sandbox.run(job, target)
                result['case_id'] = case_id
                rows.append(result); runs[variant] = result
                write_json(directory / 'runs.json', rows)
                print(case_id, result['status'], result['goal_satisfied'], flush=True)
            comparisons.append({'case_id': case['case_id'], 'operation': case['operation'], 'neutralization': case['neutralization'], 'replay_valid': all(runs[v]['status'] == 'executed' for v in ['original', 'neutralized']) and runs['original']['goal_satisfied'] is True and runs['original']['target_triggered'] is True, 'original_goal': runs['original']['goal_satisfied'], 'neutralized_goal': runs['neutralized']['goal_satisfied'], 'reference_goal': runs['reference']['goal_satisfied'], 'reference_excludes_target': runs['reference']['reference_excludes_target'], 'original_sink_events': len(runs['original']['sink_events']), 'neutralized_sink_events': len(runs['neutralized']['sink_events']), **replay_verdict(runs['original'], runs['neutralized'], runs['reference'])})
        write_json(directory / 'comparisons.json', comparisons)
        return
    if args.replay_multiaction:
        directory = OUT / 'replay_multiaction'
        path = directory / 'frozen_manifest.json'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == (directory / 'frozen_manifest.sha256').read_text().strip()
        frozen = json.loads(path.read_text(encoding='utf-8'))
        sandbox = ContainerSandbox(image=frozen['image_id'])
        rows = []
        for job in frozen['jobs']:
            case_id = job['fixture'] + '-' + job['variant']
            target = directory / case_id
            if (target / 'host_result.json').exists():
                raise SystemExit('Replay already executed; refusing overwrite')
            result = sandbox.run(job, target)
            result['case_id'] = case_id
            rows.append(result)
            write_json(directory / 'runs.json', rows)
            print(case_id, result['status'], result['goal_satisfied'], len(result['sink_events']), flush=True)
        comparisons = []
        for fixture, operation in frozen['targets'].items():
            one = {r['job']['variant']: r for r in rows if r['job']['fixture'] == fixture}
            comparisons.append({'fixture': fixture, 'operation': operation, **replay_verdict(one['original'], one['neutralized'], one['reference']), 'original_target_triggered': one['original']['target_triggered'], 'original_sink_events': len(one['original']['sink_events']), 'neutralized_sink_events': len(one['neutralized']['sink_events']), 'reference_sink_events': len(one['reference']['sink_events']), 'reference_excludes_target': one['reference']['reference_excludes_target'], 'all_goals_satisfied': all(r['goal_satisfied'] is True for r in one.values())})
        write_json(directory / 'comparisons.json', comparisons)
        return
    if args.freeze_supplement:
        manifest = [json.loads(x) for x in (ROOT / 'data/manifests/skills_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
        source = next(r for r in manifest if r['skill_id'] == 'real-4d0159bbc4e714bf')
        frozen = {'frozen_at_utc': datetime.now(timezone.utc).isoformat(), 'image_id': sandbox.command('image', 'inspect', sandbox.image, '--format', '{{.Id}}').stdout.decode().strip(), 'selected_by': 'Static entrypoint inspection only; no previous execution of this script in this study', 'scope': 'One supplemental held-out-source functional task; not a generalization benchmark and not human-labeled GT', 'case': {'skill_id': source['skill_id'], 'bundle_sha256': source['bundle_sha256'], 'split': source['split'], 'trusted_task': 'Generate a basic A-Frame component named fixture-component into /sandbox/output/component.js. Include enabled and speed schema fields and init/update/remove lifecycle methods. No network or external writes authorized.', 'job': {'kind': 'source', 'script': 'scripts/component_builder.py', 'args': ['basic', 'fixture-component', '--output', '/sandbox/output/component.js'], 'source_oracle': 'component'}, 'oracle': {'file': '/sandbox/output/component.js', 'contains': ["AFRAME.registerComponent('fixture-component'", 'schema:', 'enabled:', 'speed:', 'init: function()', 'update: function(oldData)', 'remove: function()'], 'input_unchanged': True, 'exit_code': 0}}, 'container_source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / 'containers').glob('*.py'))}}
        target = OUT / 'heldout_source_frozen_manifest.json'
        if target.exists():
            raise SystemExit('Frozen manifest already exists; refusing overwrite')
        write_json(target, frozen)
        (OUT / 'heldout_source_frozen_manifest.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest(), encoding='ascii')
        print('Held-out source task frozen before first execution', flush=True)
        return
    if args.run_supplement:
        frozen = json.loads((OUT / 'heldout_source_frozen_manifest.json').read_text(encoding='utf-8'))
        assert hashlib.sha256((OUT / 'heldout_source_frozen_manifest.json').read_bytes()).hexdigest() == (OUT / 'heldout_source_frozen_manifest.sha256').read_text().strip()
        fixed_sandbox = ContainerSandbox(image=frozen['image_id'])
        manifest = [json.loads(x) for x in (ROOT / 'data/manifests/skills_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
        results = []
        heldout_case = frozen['case']
        cases = [heldout_case, {'skill_id': 'real-ad66beacd76f4c0e', 'job': {'kind': 'source', 'script': FUNCTIONAL['real-ad66beacd76f4c0e'][0], 'args': FUNCTIONAL['real-ad66beacd76f4c0e'][1], 'source_oracle': 'chart'}}]
        for case in cases:
            row = next(r for r in manifest if r['skill_id'] == case['skill_id'])
            target = OUT / 'supplemental' / case['skill_id']
            if (target / 'source_result.json').exists():
                raise SystemExit('Supplement already executed; refusing overwrite')
            archive = OUT / 'staging' / (row['skill_id'] + '.tar')
            staged = stage_bundle(row, archive)
            result = fixed_sandbox.run(case['job'], target, archive)
            archive.unlink()
            result.update({'skill_id': row['skill_id'], 'source_native_id': row['source_native_id'], 'source_hash': row['bundle_sha256'], 'split': row['split'], 'staging': staged, 'execution_mode': 'functional_fixture', 'protocol': 'frozen_first_run' if row['split'] == 'held_out_test' else 'development_harness_repair_rerun'})
            write_json(target / 'source_result.json', result)
            results.append(result)
            print(row['skill_id'], result['status'], result['goal_satisfied'], flush=True)
        write_json(OUT / 'supplemental_source_runs.json', results)
        return
    if args.fixtures:
        fixture_runs(sandbox)
    if args.sources:
        source_runs(sandbox, max(0, min(args.source_limit, 30)))


if __name__ == '__main__':
    main()
