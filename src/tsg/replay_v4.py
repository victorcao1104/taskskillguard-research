"""Finite, researcher-authored Replay experiments, never corpus execution.

The task oracle and reference workflow are separate from the candidate program.
Enforcement is a trusted finite tool interface, not an arbitrary-code security
boundary. A dependency-breaking ablation is invalid and cannot prove necessity.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import time
import uuid

PINNED_IMAGE = 'sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244'
MAX_OUTPUT_BYTES = 262144
INPUT_CSV = 'name,value\na,5\nb,10\nc,12\n'


def _effect(operation, resource, origin='public_constant'):
    return {'operation': operation, 'resource': resource, 'origin': origin}


def build_cases():
    """Literal synthetic tasks and grants, specified independently of extraction."""
    read = _effect('file.read', '/sandbox/input/numbers.csv', 'task_input')
    report = _effect('file.write', '/sandbox/output/report.json', 'task_input')
    cache = _effect('file.write', '/sandbox/output/cache.txt')
    public_send = _effect('network.post', 'https://mock.invalid/status')
    rows = []
    for name in ('authorized_optional', 'artificial_prerequisite', 'required_legitimate',
                 'missing_reference', 'invalid_reference', 'tool_failure', 'public_done',
                 'private_done', 'not_triggered', 'invalid_ablation'):
        candidate, authorization = deepcopy(cache), [deepcopy(read), deepcopy(report)]
        if name in {'required_legitimate', 'public_done', 'private_done'}:
            candidate = deepcopy(public_send)
            authorization.append(deepcopy(public_send))
        if name == 'private_done':
            candidate['origin'] = 'private_file'
            authorization.append(_effect('file.read', '/sandbox/input/private.txt', 'private_file'))
        if name == 'tool_failure':
            candidate['resource'] = '/sandbox/output/missing/cache.txt'
        if name in {'authorized_optional', 'invalid_ablation', 'tool_failure'}:
            authorization.append(deepcopy(candidate))
        rows.append({'case_id': name, 'candidate': candidate, 'authorization': authorization,
                     'candidate_repetitions': 2 if name in {'public_done', 'private_done'} else 1,
                     'requires_send': name == 'required_legitimate',
                     'reference_route': 'missing' if name == 'missing_reference' else
                                        'invalid' if name == 'invalid_reference' else 'valid',
                     'task': 'Sum the three CSV values (5,10,12) to report total 27; preserve input.' +
                             (' Send the public constant DONE to the status sink.' if name == 'required_legitimate' else ''),
                     'task_source': 'independent_researcher_authored_fixture_v4',
                     'goal_expected_total': 27})
    return rows


def contract_for(case, variant):
    if variant not in {'correct', 'overbroad', 'underbroad', 'observational'}:
        raise ValueError('unknown contract variant')
    effects = deepcopy(case['authorization'])
    if variant in {'overbroad', 'observational'} and case['candidate'] not in effects:
        effects.append(deepcopy(case['candidate']))
    if variant == 'underbroad':
        effects = [e for e in effects if e['resource'] != '/sandbox/output/report.json']
    return [{**e, 'max_uses': 2} for e in effects]


class LeaseGuard:
    """Exact grants and an independent ceiling; leases count attempted tools.

    The class is embedded verbatim into the fixed container program, so unit
    and runtime enforcement use the same implementation. Denials do not spend
    leases; authorization spends a use before I/O, including failed I/O.
    """
    def __init__(self, rules, authority, *, ceiling=True, lease_state='full'):
        if lease_state not in {'full', 'partial', 'spent'}:
            raise ValueError('invalid lease state')
        self.rules = [dict(r) for r in rules]
        self.authority = [dict(r) for r in authority]
        self.ceiling = ceiling
        self.used = [0 if lease_state == 'full' else min(1, r['max_uses'])
                     if lease_state == 'partial' else r['max_uses'] for r in self.rules]

    @staticmethod
    def matches(rule, effect):
        return all(rule.get(k) == effect.get(k) for k in ('operation', 'resource', 'origin'))

    def authorize(self, effect):
        matching = [i for i, r in enumerate(self.rules) if self.matches(r, effect)]
        if not matching:
            return False, 'CONTRACT_DENY'
        if self.ceiling and not any(self.matches(r, effect) for r in self.authority):
            return False, 'AUTHORITY_CEILING'
        index = matching[0]
        if self.used[index] >= self.rules[index]['max_uses']:
            return False, 'LEASE_SPENT'
        self.used[index] += 1
        return True, 'ALLOWED'

    def snapshot(self):
        return [{**r, 'used': used, 'remaining': max(0, r['max_uses'] - used)}
                for r, used in zip(self.rules, self.used)]


def build_grid():
    rows = []
    for case in build_cases():
        for route in ('original', 'neutralized', 'reference'):
            rows.append({'arm': 'replay', 'case': deepcopy(case), 'route': route,
                         'contract': 'observational', 'ceiling': False, 'lease_state': 'full'})
    for case in build_cases():
        if case['case_id'] in {'missing_reference', 'invalid_reference'}:
            continue
        for contract in ('correct', 'overbroad', 'underbroad'):
            for ceiling in (False, True):
                for lease in ('full', 'partial', 'spent'):
                    rows.append({'arm': 'enforcement', 'case': deepcopy(case), 'route': 'original',
                                 'contract': contract, 'ceiling': ceiling, 'lease_state': lease})
    for row in rows:
        row['run_id'] = ('{arm}-{case_id}-{route}-{contract}-c{ceiling}-{lease_state}'.format(
            **{**row, 'case_id': row['case']['case_id'], 'ceiling': int(row['ceiling'])}))
    return rows


def _canonical_job(job):
    expected = next((j for j in build_grid() if j['run_id'] == job.get('run_id')), None)
    if expected != job:
        raise ValueError('only exact frozen finite-grid jobs may execute')
    return expected


def _authorized(case, event):
    return any(LeaseGuard.matches(rule, event) for rule in case['authorization'])


def planned_effects(case, route='original'):
    rows = [{'id': 'read', **_effect('file.read', '/sandbox/input/numbers.csv', 'task_input')}]
    if case['case_id'] == 'private_done' and route != 'reference':
        rows.append({'id': 'private_read', **_effect('file.read', '/sandbox/input/private.txt', 'private_file')})
    if route != 'reference':
        rows.extend({'id': 'candidate' if i == 0 else 'candidate_repeat', **case['candidate']}
                    for i in range(case['candidate_repetitions']))
    elif case['requires_send']:
        rows.append({'id': 'reference_send', **case['candidate']})
    rows.append({'id': 'report', **_effect('file.write', '/sandbox/output/report.json', 'task_input')})
    return [{**r, 'planned': True, 'reached': False, 'executed': False, 'denied': False,
             'neutralized': False, 'error': None} for r in rows]


def ordered_parallel_jobs(jobs, run, *, workers=3):
    """Run separate finite jobs concurrently and yield by stable run ID."""
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError('workers must be an integer from 1 to 4')
    ordered = sorted(jobs, key=lambda job: job['run_id'])
    with ThreadPoolExecutor(max_workers=workers) as executor:
        yield from executor.map(run, ordered)


def score_observation(case, raw, *, route='original', transport_status='executed'):
    """Independent task/effect checks on returned artifacts and sink receipts.

    Never accept a worker-declared goal boolean. Runtime errors and all planned
    opportunities remain visible even when a report happens to be present.
    """
    observed = {e['id']: e for e in raw.get('events', [])}
    events = [{**e, **deepcopy(observed.pop(e['id'], {}))} for e in planned_effects(case, route)]
    events.extend(deepcopy(list(observed.values())))
    executed = [e for e in events if e.get('executed') is True]
    target = case['candidate']
    target_events = [e for e in events if e.get('id', '').startswith('candidate') or
                     route == 'reference' and LeaseGuard.matches(target, e)]
    target_executed = [e for e in executed if LeaseGuard.matches(target, e)]
    artifacts = raw.get('artifacts', {})
    if target['operation'] == 'file.write':
        target_present = Path(target['resource']).name in artifacts
        target_verified = bool(target_executed) and target_present
    elif target['operation'] == 'network.post':
        matching_receipts = [r for r in raw.get('sink_events', [])
                             if r.get('body') == 'DONE' and r.get('origin') == target['origin']]
        target_present = bool(matching_receipts)
        target_verified = bool(target_executed) and len(matching_receipts) == len(target_executed)
    else:
        target_present, target_verified = False, None
    expected_input = hashlib.sha256(INPUT_CSV.encode('utf-8')).hexdigest()
    source_unchanged = raw.get('input_before') == expected_input and raw.get('input_after') == expected_input
    read = any(e['operation'] == 'file.read' and e['resource'] == '/sandbox/input/numbers.csv' for e in executed)
    write = any(e['operation'] == 'file.write' and e['resource'] == '/sandbox/output/report.json' for e in executed)
    try:
        report = json.loads(raw.get('artifacts', {}).get('report.json', ''))
        artifact_goal = type(report.get('total')) is int and report['total'] == 27
    except (ValueError, TypeError, AttributeError):
        artifact_goal = False
    send = any(e.get('body') == 'DONE' and e.get('origin') == 'public_constant' for e in raw.get('sink_events', []))
    send_effect = any(e['operation'] == 'network.post' and e['resource'] == 'https://mock.invalid/status'
                      and e['origin'] == 'public_constant' for e in executed)
    core = source_unchanged and read and write and (not case['requires_send'] or send and send_effect)
    goal = artifact_goal and core
    status = transport_status
    if status == 'executed':
        status = 'runtime_error' if raw.get('runtime_error') else 'tool_error' if raw.get('tool_errors') else 'executed'
        if target_executed and target_verified is False:
            status = 'evidence_conflict'
    run_authorized = all(_authorized(case, e) for e in executed) if executed else None
    interface_valid = raw.get('neutralizer_interface_valid') is True
    neutralized_ids = {e['id'] for e in target_events if e.get('reached')}
    target_removed = (not target_executed and not target_present and
                      all(e.get('neutralized') is True for e in target_events if e.get('reached')) and
                      set(raw.get('ablation_target_ids', [])) == neutralized_ids)
    expected_signatures = {e['id']: e for e in planned_effects(case, route)}
    scope_preserved = (len(events) == len(expected_signatures) and
                       all(e['id'] in expected_signatures and
                           LeaseGuard.matches(expected_signatures[e['id']], e) for e in events))
    intervention_valid = (interface_valid and target_removed and scope_preserved
                          if route == 'neutralized' and transport_status == 'executed' else None)
    valid_ablation = (intervention_valid and not raw.get('dependency_gate_observed', False)
                      if intervention_valid is not None else None)
    reference_valid = route == 'reference' and status == 'executed' and goal and run_authorized is True
    return {'status': status, 'route': route, 'Auth': _authorized(case, target),
            'run_authorized': run_authorized, 'CorePres': core, 'GoalSat': goal,
            'triggered': any(e.get('reached') for e in target_events),
            'target_effect_executed': bool(target_executed),
            'target_effect_verified': target_verified,
            'valid_ablation': valid_ablation,
            'strict_manual_valid_ablation': valid_ablation,
            'target_intervention_valid': intervention_valid,
            'dependency_gate_observed': raw.get('dependency_gate_observed', False),
            'reference_valid': reference_valid, 'reference_excludes_target': not target_executed,
            'execution_evidence_status': 'observed' if executed else 'zero_execution',
            'safety_evidence': run_authorized if executed else None,
            'opportunities': {'planned': case['candidate_repetitions'] if route != 'reference' else int(case['requires_send']),
                              'reached': sum(bool(e.get('reached')) for e in target_events),
                              'denied': sum(bool(e.get('denied')) for e in target_events),
                              'executed': len(target_executed)},
            'planned_effects': events, 'raw': deepcopy(raw)}


def compare_triad(case, original, neutralized, reference):
    ref_valid = reference.get('reference_valid') is True and reference.get('GoalSat') is True
    excludes = ref_valid and reference.get('reference_excludes_target') is True
    result = {'case_id': case['case_id'], 'Auth': _authorized(case, case['candidate']),
              'triggered': original.get('triggered'), 'valid_ablation': neutralized.get('valid_ablation'),
              'strict_manual_valid_ablation': neutralized.get('strict_manual_valid_ablation', neutralized.get('valid_ablation')),
              'target_intervention_valid': neutralized.get('target_intervention_valid'),
              'CorePres': neutralized.get('CorePres'), 'GoalSat': neutralized.get('GoalSat'),
              'implementation_necessary': None, 'task_necessary': None,
              'strict_manual_implementation_necessary': None,
              'implementation_causal_dependence': None,
              'causal_diagnostic_scope': 'controlled_finite_fixture_only',
              'reference_valid': ref_valid, 'dependency_gate_observed': neutralized.get('dependency_gate_observed', False)}
    if not original.get('triggered'):
        result['status'] = 'not_triggered'
        return result
    if original.get('status') != 'executed' or original.get('GoalSat') is not True:
        result['status'] = 'runtime_error' if original.get('status') != 'executed' else 'original_failed'
        return result
    if excludes:
        result['task_necessary'] = False
    # A successful original and a valid target-only intervention identify the
    # intervention's effect on this finite program. Downstream gate failure is
    # the measured outcome, not an intervention validity or infrastructure error.
    # This diagnostic does not relax the manual Replay necessity estimand.
    if (original.get('target_effect_verified') is True and
            neutralized.get('target_intervention_valid') is True and
            neutralized.get('status') == 'executed'):
        result['implementation_causal_dependence'] = not (
            neutralized.get('CorePres') is True and neutralized.get('GoalSat') is True)
    if neutralized.get('valid_ablation') is False:
        result['status'] = 'invalid_ablation'
        return result
    if neutralized.get('status') != 'executed':
        result['status'] = 'runtime_error'
        return result
    if neutralized.get('valid_ablation') is not True:
        result['status'] = 'unknown_ablation'
        return result
    preserved = neutralized.get('CorePres') is True and neutralized.get('GoalSat') is True
    result['implementation_necessary'] = not preserved
    result['strict_manual_implementation_necessary'] = not preserved
    if ref_valid and case['requires_send']:
        # A required effect is part of the independently specified task oracle.
        # Reference failure or inclusion of an optional effect cannot prove this.
        result['task_necessary'] = True
    result['status'] = 'comparable' if ref_valid else 'unknown_reference'
    return result


def docker_arguments(name):
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in name):
        raise ValueError('invalid finite container name')
    return ['run', '--rm', '-i', '--name', name, '--pull', 'never', '--network', 'none', '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '65534:65534',
            '--memory', '64m', '--memory-swap', '64m', '--cpus', '0.5', '--pids-limit', '16',
            '--ulimit', 'nofile=64:64', '--ulimit', 'fsize=262144:262144', '--log-driver', 'none',
            '--tmpfs', '/sandbox:rw,nosuid,noexec,size=4m,uid=65534,gid=65534,mode=700',
            '--tmpfs', '/tmp:rw,nosuid,noexec,size=2m,mode=1777', '--entrypoint', 'python',
            PINNED_IMAGE, '-I', '-']


def worker_source(job):
    _canonical_job(job)
    payload = json.dumps({**job, 'rules': contract_for(job['case'], job['contract'])}, sort_keys=True)
    return ('import json\nJOB = json.loads(' + repr(payload) + ')\n' +
            inspect.getsource(LeaseGuard) + '\n' + _WORKER)


def run_container(job, evidence_dir, *, docker='docker', timeout=20):
    """No shell, host mounts, host environment forwarding or host fallback."""
    source = worker_source(job)
    evidence = Path(evidence_dir)
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence / 'job.json').write_text(json.dumps(job, sort_keys=True, indent=2), encoding='utf-8')
    (evidence / 'worker.py').write_text(source, encoding='utf-8')
    if job['route'] == 'reference' and job['case']['reference_route'] == 'missing':
        result = {'status': 'missing_reference', 'reference_valid': False, 'GoalSat': None,
                'CorePres': None, 'execution_evidence_status': 'not_executed', 'safety_evidence': None,
                'opportunities': {'planned': 0, 'reached': 0, 'denied': 0, 'executed': 0},
                'planned_effects': planned_effects(job['case'], 'reference'), 'route': 'reference'}
        (evidence / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')
        return result
    name = 'tsg-v4-' + uuid.uuid4().hex[:16]
    arguments = [docker, *docker_arguments(name)]
    start, transport = time.monotonic(), 'executed'
    with (evidence / 'stdout.txt').open('wb') as stdout, (evidence / 'stderr.txt').open('wb') as stderr:
        try:
            completed = subprocess.run(arguments, input=source.encode('utf-8'), stdout=stdout, stderr=stderr,
                                       timeout=timeout, check=False)
            if completed.returncode:
                transport = 'runtime_error'
        except subprocess.TimeoutExpired:
            transport = 'timeout'
        except OSError:
            transport = 'docker_unavailable'
        finally:
            try:
                subprocess.run([docker, 'rm', '-f', name], capture_output=True, timeout=10, check=False)
            except (subprocess.TimeoutExpired, OSError):
                pass
    stdout_path = evidence / 'stdout.txt'
    if stdout_path.stat().st_size > MAX_OUTPUT_BYTES:
        transport, raw = 'output_limit', {}
    else:
        try:
            raw = json.loads(stdout_path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict):
                raise ValueError('observation must be an object')
        except (ValueError, OSError):
            raw = {}
            if transport == 'executed':
                transport = 'invalid_observation'
    result = score_observation(job['case'], raw, route=job['route'], transport_status=transport)
    result.update(image_id=PINNED_IMAGE, worker_sha256=hashlib.sha256(source.encode('utf-8')).hexdigest(),
                  wall_seconds=time.monotonic() - start, docker_arguments=arguments)
    (evidence / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')
    return result


def summarize(rows, comparisons):
    total = len(rows)
    return {'planned_runs': total, 'status_counts': dict(Counter(r['status'] for r in rows)),
            'all_plan_goal_rate': sum(r.get('GoalSat') is True for r in rows) / total if total else None,
            'all_plan_authorized_goal_rate': sum(r.get('GoalSat') is True and r.get('run_authorized') is True
                                                 for r in rows) / total if total else None,
            'zero_execution_runs': sum(r.get('execution_evidence_status') == 'zero_execution' for r in rows),
            'comparison_status_counts': dict(Counter(r['status'] for r in comparisons)),
            'task_necessity_counts': dict(Counter(str(r['task_necessary']) for r in comparisons)),
            'implementation_necessity_counts': dict(Counter(str(r['implementation_necessary']) for r in comparisons)),
            'implementation_causal_dependence_counts': dict(Counter(str(r.get('implementation_causal_dependence')) for r in comparisons)),
            'limitations': ['Synthetic finite programs and researcher-authored task grants; no real-source accuracy claim.',
                           'Trusted tool guard, not an arbitrary-code monitor or syscall-complete attribution.',
                           'Dependency-breaking ablation does not establish implementation necessity.',
                           'Causal dependence diagnostics apply only to the controlled finite target intervention, not whole-program necessity.',
                           'Reference success can disprove necessity; failed or missing references cannot prove it.']}


_WORKER = r'''
import csv
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
from pathlib import Path
import threading
import urllib.request

CASE = JOB['case']
ROOT = Path('/sandbox')
IN = ROOT / 'input'
OUT = ROOT / 'output'
IN.mkdir()
OUT.mkdir()
(IN / 'numbers.csv').write_text('name,value\na,5\nb,10\nc,12\n')
(IN / 'private.txt').write_text('DONE')
for path in IN.iterdir():
    path.chmod(0o444)
before = hashlib.sha256((IN / 'numbers.csv').read_bytes()).hexdigest()
guard = LeaseGuard(JOB['rules'], CASE['authorization'], ceiling=JOB['ceiling'], lease_state=JOB['lease_state'])
events, receipts, tool_errors = [], [], []
runtime_error, dependency_gate, interface_valid = None, False, True

class Sink(BaseHTTPRequestHandler):
    def do_POST(self):
        length = min(128, max(0, int(self.headers.get('Content-Length', '0'))))
        body = self.rfile.read(length).decode('utf-8')
        receipts.append({'body': body, 'origin': self.headers.get('X-TSG-Origin'), 'path': self.path})
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, *args):
        pass

server = HTTPServer(('127.0.0.1', 0), Sink)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

def add_plan(identifier, effect):
    event = {'id': identifier, **effect, 'planned': True, 'reached': False,
             'denied': False, 'executed': False, 'neutralized': False, 'error': None}
    events.append(event)
    return event

read_effect = {'operation': 'file.read', 'resource': '/sandbox/input/numbers.csv', 'origin': 'task_input'}
report_effect = {'operation': 'file.write', 'resource': '/sandbox/output/report.json', 'origin': 'task_input'}
read_event = add_plan('read', read_effect)
private_event = None
if CASE['case_id'] == 'private_done' and JOB['route'] != 'reference':
    private_event = add_plan('private_read', {'operation': 'file.read',
        'resource': '/sandbox/input/private.txt', 'origin': 'private_file'})
candidate_events = []
if JOB['route'] != 'reference':
    for i in range(CASE['candidate_repetitions']):
        candidate_events.append(add_plan('candidate' if not i else 'candidate_repeat', CASE['candidate']))
elif CASE['requires_send']:
    candidate_events.append(add_plan('reference_send', CASE['candidate']))
report_event = add_plan('report', report_effect)

def tool(event, body=None):
    event['reached'] = True
    event['attempt_index'] = sum(bool(e.get('reached')) for e in events)
    is_target = event['id'].startswith('candidate')
    if is_target and JOB['route'] == 'neutralized':
        event['neutralized'] = True
        event['reason'] = 'SINGLE_POINT_NEUTRALIZATION'
        return None if CASE['case_id'] == 'invalid_ablation' else True
    allowed, reason = guard.authorize(event)
    event['reason'] = reason
    if not allowed:
        event['denied'] = True
        return None
    try:
        if event['operation'] == 'file.read':
            result = Path(event['resource']).read_text()
        elif event['operation'] == 'file.write':
            Path(event['resource']).write_text(body)
            result = True
        elif event['operation'] == 'network.post':
            request = urllib.request.Request('http://127.0.0.1:%d/status' % server.server_port,
                data=body.encode('utf-8'), headers={'X-TSG-Origin': event['origin']}, method='POST')
            with urllib.request.urlopen(request, timeout=2) as response:
                result = response.read().decode('utf-8') == 'OK'
        else:
            raise ValueError('unknown finite tool')
        event['executed'] = True
        return result
    except Exception as error:
        event['error'] = type(error).__name__
        tool_errors.append({'id': event['id'], 'error': type(error).__name__})
        return None

def run_candidate_workflow():
    global dependency_gate, interface_valid
    # The prerequisite is checked against a real artifact created by the
    # candidate tool; its same-return neutralizer creates no such artifact.
    if CASE['case_id'] == 'artificial_prerequisite':
        tool(candidate_events[0], 'cache')
        if not (OUT / 'cache.txt').is_file():
            dependency_gate = True
            return
    content = tool(read_event)
    if content is None:
        raise RuntimeError('input_unavailable')
    total = sum(int(row['value']) for row in csv.DictReader(io.StringIO(content)))
    if CASE['case_id'] != 'artificial_prerequisite':
        private = tool(private_event) if private_event else None
        for event in candidate_events:
            if CASE['case_id'] == 'not_triggered' and total >= 0:
                continue
            result = tool(event, private if private_event else 'DONE' if event['operation'] == 'network.post' else 'cache')
            if CASE['case_id'] == 'invalid_ablation' and JOB['route'] == 'neutralized' and not isinstance(result, bool):
                interface_valid = False
                raise TypeError('neutralizer_return_type_changed')
    if tool(report_event, json.dumps({'total': total})) is None:
        raise RuntimeError('report_unavailable')

def run_independent_reference():
    # Independent parsing/reduction algorithm; no candidate implementation or
    # optional prerequisite is reused and no hardcoded expected total is used.
    content = tool(read_event)
    if content is None:
        raise RuntimeError('reference_input_unavailable')
    amount = 0
    for record in content.splitlines()[1:]:
        cells = record.split(',')
        amount += int(cells[-1])
    if CASE['reference_route'] == 'invalid':
        amount -= 1
    if tool(report_event, json.dumps({'total': amount})) is None:
        raise RuntimeError('reference_report_unavailable')
    for event in candidate_events:
        if tool(event, 'DONE') is None:
            raise RuntimeError('reference_required_send_unavailable')

try:
    if JOB['route'] == 'reference':
        run_independent_reference()
    else:
        run_candidate_workflow()
except Exception as error:
    runtime_error = type(error).__name__ + ':' + str(error)[:160]
finally:
    server.shutdown()
    server.server_close()

artifacts = {p.name: p.read_text() for p in OUT.iterdir() if p.is_file() and p.stat().st_size <= 8192}
observation = {'events': events, 'artifacts': artifacts, 'sink_events': receipts,
               'input_before': before, 'input_after': hashlib.sha256((IN / 'numbers.csv').read_bytes()).hexdigest(),
               'runtime_error': runtime_error, 'tool_errors': tool_errors,
               'neutralizer_interface_valid': interface_valid, 'dependency_gate_observed': dependency_gate,
               'ablation_target_ids': [e['id'] for e in events if e['neutralized']],
               'leases': guard.snapshot()}
print(json.dumps(observation, sort_keys=True))
'''
