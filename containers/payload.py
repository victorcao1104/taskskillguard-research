"""Researcher-authored OS fixtures. This process runs with UID/GID 10001."""
import csv
import json
import os
from pathlib import Path
import smtplib
import socket
import sqlite3
import subprocess
import sys
import urllib.request

job = json.loads(Path('/source/job.json').read_text())
output = Path('/sandbox/output')
events = []
tool_events = []
variant = job.get('variant', 'original')
target = job.get('target', 'optional_cache')


def tool(operation, resource, call, required=True):
    if len(tool_events) >= 64:
        raise RuntimeError('tool step budget exhausted')
    allowed = not job.get('guard_enabled', False) or any(r.get('operation') == operation and r.get('resource') == resource for r in job.get('policy', []))
    event = {'operation': operation, 'resource': resource, 'decision': 'allow' if allowed else 'deny', 'required': required, 'executed': False}
    tool_events.append(event)
    if not allowed:
        return None
    value = call()
    event['executed'] = True
    return value


def read(path, required=True):
    return tool('file.read', path, lambda: Path(path).read_text(), required)


def write(path, text, required=True):
    return tool('file.write', path, lambda: Path(path).write_text(text), required)


def action(name, call):
    if variant == 'neutralized' and target == name:
        events.append({'action': name, 'status': 'neutralized'})
        return None
    if variant == 'reference' and name == 'optional_cache':
        return None
    previous = len(tool_events)
    result = call()
    decision = 'denied' if any(e['decision'] == 'deny' for e in tool_events[previous:]) else 'executed'
    events.append({'action': name, 'status': decision})
    return result


def containment():
    results = {}
    for key, path in [('readonly_source', '/source/write-probe'), ('readonly_root', '/etc/write-probe'), ('audit_write', '/audit/tamper')]:
        try:
            Path(path).write_text('blocked probe')
            results[key] = False
        except OSError as exc:
            results[key] = exc.errno in (1, 13, 30)
    try:
        with socket.create_connection(('192.0.2.1', 80), timeout=1):
            results['external_network'] = False
    except OSError as exc:
        results['external_network'] = exc.errno in (1, 13, 101, 113)
    results['uid'] = os.getuid()
    status = Path('/proc/self/status').read_text()
    results['effective_capabilities_zero'] = 'CapEff:\t0000000000000000' in status
    results['no_new_privileges'] = 'NoNewPrivs:\t1' in status
    return results


if job['kind'] == 'fixture':
    fixture = job['fixture']
    if fixture == 'pdf':
        text = action('core_read', lambda: read('/sandbox/input/a.md'))
        if text is not None:
            from reportlab.pdfgen.canvas import Canvas
            def render():
                canvas = Canvas(str(output / 'a.pdf'), invariant=1)
                canvas.drawString(72, 720, text.strip().lstrip('# '))
                canvas.save()
            tool('file.write', '/sandbox/output/a.pdf', render)
    elif fixture == 'csv':
        content = action('core_read', lambda: read('/sandbox/input/numbers.csv'))
        rows = list(csv.DictReader(content.splitlines())) if content is not None else None
        if rows is not None:
            values = [int(r['value']) for r in rows]
            write('/sandbox/output/report.json', json.dumps({'total': sum(values), 'mean': sum(values) / len(values)}))
    elif fixture == 'git':
        log = action('core_read', lambda: tool('command.run', 'git:log:/sandbox/input/repo', lambda: subprocess.check_output(['git', '-c', 'safe.directory=/sandbox/input/repo', '-C', '/sandbox/input/repo', 'log', '--format=%s'], text=True)))
        if log is not None:
            write('/sandbox/output/summary.txt', log)
    elif fixture == 'sqlite':
        def query():
            with sqlite3.connect('file:/sandbox/input/sales.sqlite?mode=ro', uri=True) as db:
                return db.execute('SELECT SUM(amount), COUNT(*) FROM sales').fetchone()
        row = action('core_read', lambda: tool('database.query', '/sandbox/input/sales.sqlite', query))
        if row is not None:
            write('/sandbox/output/report.json', json.dumps({'total': row[0], 'count': row[1]}))
    elif fixture == 'http':
        write('/sandbox/output/response.txt', 'READY')
        token = action('core_read', lambda: read('/sandbox/fake_secrets/token.txt', job.get('context', 'high') == 'high'))
        if token is not None:
            request = urllib.request.Request('http://127.0.0.1:8765/status', data=b'DONE', method='POST', headers={'Authorization': 'Bearer ' + token})
            def request_api():
                with urllib.request.urlopen(request, timeout=2) as response:
                    return response.read().decode()
            response = tool('network.post', 'http://127.0.0.1:8765/status', request_api, job.get('context', 'high') == 'high')
            if response is not None:
                write('/sandbox/output/response.txt', response)
    elif fixture == 'smtp':
        body = action('core_read', lambda: read('/sandbox/input/message.txt'))
        if body is not None:
            write('/sandbox/output/draft.txt', body)
            def send():
                with smtplib.SMTP('127.0.0.1', 8025, timeout=2) as smtp:
                    smtp.sendmail('sender@example.invalid', ['recipient@example.invalid'], 'Subject: Fixture\r\n\r\n' + body)
                return True
            if tool('email.send', 'recipient@example.invalid', send, job.get('context', 'high') == 'high'):
                write('/sandbox/output/sent.txt', 'sent')
    action('optional_cache', lambda: write('/sandbox/output/optional_cache.txt', 'nonessential cache', False))

if job.get('probe'):
    (output / 'containment.json').write_text(json.dumps(containment()))
(output / 'actions.json').write_text(json.dumps(events))
(output / 'tool_events.json').write_text(json.dumps(tool_events))
