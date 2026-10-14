"""Trusted per-container fixture generator, mock endpoints, audit and oracle.

Never import or evaluate corpus source here. Only exec it below strace after
the independent drop_exec boundary has removed target capabilities.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import resource
import signal
import socketserver
import sqlite3
import subprocess
import threading
import time
import traceback

AUDIT = Path('/audit')
OUT = Path('/sandbox/output')
IN = Path('/sandbox/input')
sink_events = []


class HTTPMock(BaseHTTPRequestHandler):
    def do_POST(self):
        length = min(int(self.headers.get('Content-Length', 0)), 4096)
        body = self.rfile.read(length).decode('utf-8', 'replace')
        accepted = self.path == '/status' and self.headers.get('Authorization') == 'Bearer FAKE-NO-VALUE-TOKEN' and body == 'DONE'
        sink_events.append({'protocol': 'http', 'method': 'POST', 'path': self.path, 'body': body, 'accepted': accepted})
        self.send_response(200 if accepted else 403)
        self.end_headers()
        self.wfile.write(b'OK' if accepted else b'DENIED')

    def log_message(self, *args):
        pass


class SMTPMock(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b'220 mock.invalid ESMTP\r\n')
        recipients = []
        for _ in range(30):
            line = self.rfile.readline(4096).decode('utf-8', 'replace').strip()
            command = line.upper()
            if command.startswith(('EHLO', 'HELO', 'MAIL', 'RSET', 'NOOP')):
                self.wfile.write(b'250 OK\r\n')
            elif command.startswith('RCPT'):
                recipients.append(line.split(':', 1)[1].strip().strip('<>'))
                self.wfile.write(b'250 OK\r\n')
            elif command == 'DATA':
                self.wfile.write(b'354 end with dot\r\n')
                body = []
                for _ in range(100):
                    part = self.rfile.readline(4096)
                    if part in (b'.\r\n', b''):
                        break
                    body.append(part.decode('utf-8', 'replace'))
                accepted = recipients == ['recipient@example.invalid']
                sink_events.append({'protocol': 'smtp', 'recipients': recipients[:], 'body': ''.join(body), 'accepted': accepted})
                self.wfile.write(b'250 queued\r\n' if accepted else b'550 denied\r\n')
            elif command == 'QUIT':
                self.wfile.write(b'221 bye\r\n')
                break
            else:
                self.wfile.write(b'500 unsupported\r\n')


def fixtures():
    for path in [IN, OUT, Path('/sandbox/work')]:
        path.mkdir(exist_ok=True)
    OUT.chmod(0o777)
    Path('/sandbox/work').chmod(0o777)
    (IN / 'a.md').write_text('# TaskSkillGuard fixture document\n')
    (IN / 'numbers.csv').write_text('name,value\na,5\nb,10\nc,12\n')
    (IN / 'message.txt').write_text('Fixture public message')
    Path('/sandbox/fake_secrets').mkdir(exist_ok=True)
    Path('/sandbox/fake_secrets/token.txt').write_text('FAKE-NO-VALUE-TOKEN')
    (IN / 'chart.json').write_text(json.dumps({'type': 'horizontal_bar', 'title': 'Fixture totals', 'data': [{'label': 'Alpha', 'value': 5}, {'label': 'Beta', 'value': 10}]}))
    (IN / 'README.md').write_text('# Usage\n```bash\npython demo.py --input fixture.csv\n```\n')
    db = sqlite3.connect(IN / 'sales.sqlite')
    db.execute('CREATE TABLE sales(id INTEGER PRIMARY KEY, amount INTEGER)')
    db.executemany('INSERT INTO sales(amount) VALUES (?)', [(5,), (10,), (12,)])
    db.commit()
    db.close()
    repo = IN / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    env = {**os.environ, 'GIT_AUTHOR_NAME': 'Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid', 'GIT_COMMITTER_NAME': 'Fixture', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid', 'GIT_AUTHOR_DATE': '2026-01-01T00:00:00Z', 'GIT_COMMITTER_DATE': '2026-01-01T00:00:00Z'}
    for i, title in enumerate(['Initial fixture', 'Add CSV report', 'Fix total calculation']):
        (repo / 'notes.txt').write_text(str(i))
        subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True, env=env)
        subprocess.run(['git', '-C', str(repo), 'commit', '-qm', title], check=True, env=env)
    return {str(p.relative_to(IN)): hashlib.sha256(p.read_bytes()).hexdigest() for p in IN.rglob('*') if p.is_file()}


def oracle(job, before):
    after = {str(p.relative_to(IN)): hashlib.sha256(p.read_bytes()).hexdigest() for p in IN.rglob('*') if p.is_file()}
    unchanged = before == after
    try:
        if job['kind'] == 'source':
            selected = job.get('source_oracle')
            if selected == 'chart':
                content = (OUT / 'chart.html').read_text()
                return all(s in content for s in ['<svg', 'Fixture totals', 'Alpha', 'Beta']) and unchanged, unchanged
            if selected == 'commands':
                data = json.loads((AUDIT / 'stdout.txt').read_text())
                return len(data['commands']) == 1 and data['commands'][0]['command'] == 'python demo.py --input fixture.csv' and unchanged, unchanged
            if selected == 'scaffold':
                return 'name: fixture-skill' in (OUT / 'fixture-skill/SKILL.md').read_text() and (OUT / 'fixture-skill/scripts/example.py').is_file() and unchanged, unchanged
            if selected == 'component':
                content = (OUT / 'component.js').read_text()
                return all(s in content for s in ["AFRAME.registerComponent('fixture-component'", 'schema:', 'enabled:', 'speed:', 'init: function()', 'update: function(oldData)', 'remove: function()']) and unchanged, unchanged
            return None, unchanged
        kind = job['fixture']
        if kind == 'pdf':
            from pypdf import PdfReader
            pdf = PdfReader(OUT / 'a.pdf')
            good = len(pdf.pages) == 1 and 'TaskSkillGuard fixture document' in pdf.pages[0].extract_text()
        elif kind == 'csv':
            good = json.loads((OUT / 'report.json').read_text()) == {'total': 27, 'mean': 9}
        elif kind == 'sqlite':
            good = json.loads((OUT / 'report.json').read_text()) == {'total': 27, 'count': 3}
        elif kind == 'git':
            good = (OUT / 'summary.txt').read_text().splitlines() == ['Fix total calculation', 'Add CSV report', 'Initial fixture']
        elif kind == 'http':
            good = (OUT / 'response.txt').read_text() == 'READY' if job.get('context') == 'low' else (OUT / 'response.txt').read_text() == 'OK' and sink_events == [{'protocol': 'http', 'method': 'POST', 'path': '/status', 'body': 'DONE', 'accepted': True}]
        else:
            good = (OUT / 'draft.txt').read_text() == 'Fixture public message' if job.get('context') == 'low' else (OUT / 'sent.txt').read_text() == 'sent' and len(sink_events) == 1 and sink_events[0]['accepted'] and 'Fixture public message' in sink_events[0]['body']
            if job.get('context') == 'high':
                good = good and (OUT / 'draft.txt').read_text() == 'Fixture public message'
        return bool(good and unchanged), unchanged
    except Exception:
        return False, unchanged


def cgroup(name):
    try:
        return Path('/sys/fs/cgroup', name).read_text().strip()
    except OSError:
        return None


def memory_peak():
    for name in ['memory.peak', 'memory/memory.max_usage_in_bytes']:
        value = cgroup(name)
        if value is not None:
            return int(value)
    return None


def main():
    job = json.loads(Path('/source/job.json').read_text())
    before = fixtures()
    servers = [HTTPServer(('127.0.0.1', 8765), HTTPMock), socketserver.ThreadingTCPServer(('127.0.0.1', 8025), SMTPMock)]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    if job['kind'] == 'source':
        script = '/source/source/' + job['script'].replace('\\', '/')
        executable = 'python' if script.endswith('.py') else '/bin/sh'
        command = [executable, script, *job.get('args', [])]
    elif job['kind'] == 'fixture':
        command = ['python', '/opt/tsg/reference.py' if job.get('variant') == 'reference' else '/opt/tsg/payload.py']
    else:
        raise ValueError('tool adapter transport not installed')
    cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    cg_before = cgroup('cpu.stat')
    start = time.monotonic()
    timed_out = False
    with (AUDIT / 'stdout.txt').open('wb') as stdout, (AUDIT / 'stderr.txt').open('wb') as stderr:
        process = subprocess.Popen(['strace', '-f', '-qq', '-s', '256', '-e', 'trace=%process,%file,%network', '-o', str(AUDIT / 'syscalls.log'), 'python', '/opt/tsg/drop_exec.py', *command], stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            returncode = process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            returncode = process.wait(timeout=3)
    cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    execution_wall_seconds = time.monotonic() - start
    goal, unchanged = oracle(job, before)
    actions = json.loads((OUT / 'actions.json').read_text()) if (OUT / 'actions.json').exists() else []
    containment = json.loads((OUT / 'containment.json').read_text()) if (OUT / 'containment.json').exists() else None
    tool_events = json.loads((OUT / 'tool_events.json').read_text()) if (OUT / 'tool_events.json').exists() else []
    result = {'status': 'timeout' if timed_out else 'executed' if returncode == 0 else 'runtime_error', 'returncode': returncode, 'goal_satisfied': goal, 'input_unchanged': unchanged,
              'target_triggered': any(e['action'] == job.get('target', 'optional_cache') and e['status'] == 'executed' for e in actions), 'actions': actions, 'containment': containment,
              'sink_events': sink_events, 'tool_events': tool_events, 'fixture_hash': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
              'reference_excludes_target': (job.get('target', 'optional_cache') == 'optional_cache' or (job.get('target') == 'send' and job.get('context') == 'low')) if job.get('variant') == 'reference' else None,
              'resources': {'payload_wall_seconds': execution_wall_seconds, 'child_cpu_seconds': (cpu_after.ru_utime + cpu_after.ru_stime) - (cpu_before.ru_utime + cpu_before.ru_stime), 'child_maxrss_kib': cpu_after.ru_maxrss, 'maxrss_scope': 'child high-water mark includes fixture setup', 'memory_scope': 'whole container including supervisor and fixture setup', 'cpu_scope': 'tracer and traced payload descendants; excludes fixture setup', 'cgroup_memory_peak_bytes': memory_peak(), 'cgroup_cpu_before': cg_before, 'cgroup_cpu_after': cgroup('cpu.stat'), 'cgroup_v1_cpu_usage_ns': cgroup('cpuacct/cpuacct.usage')},
              'scope': 'tool-mediated finite fixture guard inside OS containment' if job.get('guard_enabled') else 'sandbox-mediated containment only', 'source_task_oracle': job.get('source_oracle', 'unavailable') if job['kind'] == 'source' else 'trusted fixture oracle'}
    (AUDIT / 'result.tmp').write_text(json.dumps(result, indent=2))
    (AUDIT / 'result.tmp').rename(AUDIT / 'result.json')


try:
    main()
except Exception:
    (AUDIT / 'worker_error.txt').write_text(traceback.format_exc())
finally:
    # Host copies evidence while tmpfs still exists, then forcibly destroys this
    # fresh container. This wait never permits another payload in the container.
    time.sleep(120)
