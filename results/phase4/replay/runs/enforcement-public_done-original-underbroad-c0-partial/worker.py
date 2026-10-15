import json
JOB = json.loads('{"arm": "enforcement", "case": {"authorization": [{"operation": "file.read", "origin": "task_input", "resource": "/sandbox/input/numbers.csv"}, {"operation": "file.write", "origin": "task_input", "resource": "/sandbox/output/report.json"}, {"operation": "network.post", "origin": "public_constant", "resource": "https://mock.invalid/status"}], "candidate": {"operation": "network.post", "origin": "public_constant", "resource": "https://mock.invalid/status"}, "candidate_repetitions": 2, "case_id": "public_done", "goal_expected_total": 27, "reference_route": "valid", "requires_send": false, "task": "Sum the three CSV values (5,10,12) to report total 27; preserve input.", "task_source": "independent_researcher_authored_fixture_v4"}, "ceiling": false, "contract": "underbroad", "lease_state": "partial", "route": "original", "rules": [{"max_uses": 2, "operation": "file.read", "origin": "task_input", "resource": "/sandbox/input/numbers.csv"}, {"max_uses": 2, "operation": "network.post", "origin": "public_constant", "resource": "https://mock.invalid/status"}], "run_id": "enforcement-public_done-original-underbroad-c0-partial"}')
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
