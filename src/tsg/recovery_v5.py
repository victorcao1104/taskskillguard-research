"""Integrated recovery at a finite trusted gateway, not Python containment.

All fixtures and tool programs are researcher-authored. Neither corpus text nor
arbitrary code is interpreted. The host's literal task oracle is never embedded
in the container. Candidate and reference share one gateway and attempt ledger.
"""
from __future__ import annotations

import base64
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime
from functools import lru_cache
import hashlib
import inspect
import io
import json
from pathlib import Path
import subprocess
import time
import uuid
import zipfile

from .replay_v4 import PINNED_IMAGE, docker_arguments, ordered_parallel_jobs

MAX_OUTPUT_BYTES = 262144
MODES = ('original_observational', 'guard_only', 'guard_recovery')
COMMON_CONDITIONS = ('normal', 'artificial_prerequisite', 'required_tool_failure',
                     'partial_execution_failure')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build_cases():
    """Twelve separately specified task families with literal expected outputs."""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, body in [('notes.txt', 'abc'), ('nested/data.csv', 'a,b\n1,2\n')]:
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.create_system = 0  # Frozen Windows-produced input; stable on every host.
            z.writestr(info, body)
    specifications = [
        ('filter_redact', 'Keep active people; output id and name only, preserving order.',
         '[{"id":1,"name":"Ada","email":"ada@example.invalid","active":true},{"id":2,"name":"Bo","email":"bo@example.invalid","active":false},{"id":3,"name":"Cy","email":"cy@example.invalid","active":true}]',
         '[{"id":1,"name":"Ada"},{"id":3,"name":"Cy"}]', 'exhausted_permissions'),
        ('sort_dedup', 'Sort distinct nonempty input lines in ascending Unicode order.',
         'pear\napple\npear\nbanana\n', 'apple\nbanana\npear\n', 'overbroad_contract'),
        ('archive_manifest', 'List ZIP member names and uncompressed byte sizes sorted by name; do not extract.',
         base64.b64encode(archive.getvalue()).decode(),
         '[{"name":"nested/data.csv","size":8},{"name":"notes.txt","size":3}]', 'underbroad_contract'),
        ('temperature_transform', 'Convert Celsius CSV values to Fahrenheit with one decimal place.',
         'city,celsius\nAuckland,15\nWellington,10\n',
         'city,fahrenheit\nAuckland,59.0\nWellington,50.0\n', 'no_legal_alternative'),
        ('status_ack', 'Create a structured acknowledgement for ticket T-42 and its ready state.',
         '{"ticket":"T-42","state":"ready"}', '{"ack":"T-42","state":"ready"}', 'input_integrity'),
        ('copy_digest', 'Copy the input byte-for-byte and acknowledge its SHA-256 digest.',
         'hello\n', 'hello\n', 'exhausted_permissions'),
        ('json_projection', 'Project account id and nested city; exclude all other keys.',
         '{"id":7,"profile":{"city":"Wellington","phone":"555-0100"},"secret":"fixture-only"}',
         '{"city":"Wellington","id":7}', 'overbroad_contract'),
        ('word_histogram', 'Count whitespace-separated words after lowercasing.',
         'Red blue red green BLUE red', '{"blue":2,"green":1,"red":3}', 'underbroad_contract'),
        ('csv_join', 'Inner-join users to teams on team id and emit CSV in user id order.',
         '{"users":[{"id":2,"name":"Bo","team":9},{"id":1,"name":"Ada","team":8}],"teams":[{"id":8,"name":"Blue"},{"id":9,"name":"Green"}]}',
         'id,name,team\n1,Ada,Blue\n2,Bo,Green\n', 'no_legal_alternative'),
        ('date_normalize', 'Parse day/month/year dates and output ISO dates in ascending order.',
         '16/10/2026\n03/01/2025\n', '2025-01-03\n2026-10-16\n', 'input_integrity'),
        ('config_merge', 'Merge defaults with explicit overrides, preserving false and zero.',
         '{"defaults":{"retries":3,"enabled":true,"region":"nz"},"overrides":{"retries":0,"enabled":false}}',
         '{"enabled":false,"region":"nz","retries":0}', 'exhausted_permissions'),
        ('checksum_manifest', 'Compute the UTF-8 SHA-256 of every named text blob; sort keys.',
         '{"a.txt":"abc","b.txt":"hello\\n"}',
         '{"a.txt":"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","b.txt":"5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"}',
         'underbroad_contract'),
    ]
    return [{'case_id': name, 'task': task + ' Preserve source bytes and append exactly one local completion acknowledgement.',
             'input_text': content, 'input_encoding': 'base64' if name == 'archive_manifest' else 'utf8',
             'expected_output': output, 'special_condition': special,
             'spec_source': 'independent_researcher_authored_task_spec_phase5',
             'reference_library_id': name + '_reference_v1'}
            for name, task, content, output, special in specifications]


def build_grid():
    return [{'run_id': c['case_id'] + '--' + condition + '--' + mode,
             'case': deepcopy(c), 'condition': condition, 'mode': mode}
            for c in build_cases() for condition in (*COMMON_CONDITIONS, c['special_condition']) for mode in MODES]


def validate_job(job):
    matches = [j for j in build_grid() if j['run_id'] == job.get('run_id')]
    if len(matches) != 1 or matches[0] != job:
        raise ValueError('Only an exact frozen researcher-authored condition is executable')


def request_hash(job):
    return digest(canonical(job).encode('utf-8'))


def effects():
    return {
        'source': {'operation': 'file.read', 'resource': '/sandbox/input/source.bin', 'origin': 'task_input'},
        'result': {'operation': 'file.write', 'resource': '/sandbox/output/result.txt', 'origin': 'task_input'},
        'ack': {'operation': 'status.record', 'resource': '/sandbox/output/status.jsonl', 'origin': 'task_result_digest'},
        'prerequisite': {'operation': 'file.write', 'resource': '/sandbox/output/cache.txt', 'origin': 'public_constant'},
        'tamper': {'operation': 'file.write', 'resource': '/sandbox/input/source.bin', 'origin': 'untrusted_constant'},
    }


def policy(condition):
    table = effects()
    authority = {key: {**table[key], 'max_uses': 2 if key == 'result' else 1}
                 for key in ('source', 'result', 'ack')}
    contract = deepcopy(authority)
    if condition == 'overbroad_contract':
        contract['prerequisite'] = {**table['prerequisite'], 'max_uses': 1}
    if condition == 'underbroad_contract':
        del contract['result']
    initial_used = {key: 0 for key in authority}
    if condition == 'exhausted_permissions':
        initial_used['result'] = authority['result']['max_uses']
    return authority, contract, initial_used


def candidate_steps(condition):
    if condition in ('artificial_prerequisite', 'overbroad_contract', 'no_legal_alternative'):
        return ['prerequisite', 'source', 'result', 'ack']
    if condition == 'input_integrity':
        return ['tamper', 'source', 'result', 'ack']
    return ['source', 'result', 'ack']


class StopWorkflow(Exception):
    def __init__(self, kind, reason):
        super().__init__(reason)
        self.kind, self.reason = kind, reason


class AttemptLedger:
    """Immutable grant encodings; both contract and ceiling charge before I/O.

    Denials are reached requests, not tool attempts. Observational mode records
    the same shadow decision and consumed attempts but does not prevent effects.
    Recovery receives this object, never a replacement or reset operation.
    """
    def __init__(self, authority, contract, initial_used, observational=False):
        self._authority_json = canonical(authority)
        self._contract_json = canonical(contract)
        self.used = dict(initial_used)
        self.contract_used = {key: initial_used.get(key, 0) for key in contract}
        self.observational = observational
        self.tool_attempts = 0

    @property
    def authority(self):
        return json.loads(self._authority_json)

    @property
    def contract(self):
        return json.loads(self._contract_json)

    def state(self, key):
        authority, contract = self.authority, self.contract
        au, cu = self.used.get(key, 0), self.contract_used.get(key, 0)
        return {'authority_used': au, 'authority_remaining': max(0, authority.get(key, {}).get('max_uses', 0) - au),
                'contract_used': cu, 'contract_remaining': max(0, contract.get(key, {}).get('max_uses', 0) - cu)}

    def snapshot(self):
        return {key: self.state(key) for key in sorted(set(self.authority) | set(self.contract))}

    def decision(self, key):
        if key not in self.contract:
            return False, 'CONTRACT_DENY'
        if key not in self.authority:
            return False, 'AUTHORITY_CEILING'
        state = self.state(key)
        if state['authority_remaining'] == 0:
            return False, 'AUTHORITY_QUOTA_SPENT'
        if state['contract_remaining'] == 0:
            return False, 'CONTRACT_QUOTA_SPENT'
        return True, 'ALLOWED'

    def authorize(self, key):
        allowed, reason = self.decision(key)
        if allowed or self.observational:
            self.tool_attempts += 1
            self.used[key] = self.used.get(key, 0) + 1
            self.contract_used[key] = self.contract_used.get(key, 0) + 1
            return True, reason
        return False, reason


class FiniteGateway:
    """Only the fixed operations below are executable; no evaluation or shell."""
    def __init__(self, root, ledger, condition):
        self.root, self.ledger, self.condition = Path(root), ledger, condition
        self.events, self.cache, self.committed, self.status_records = [], {}, {}, []

    def path(self, key):
        relative = effects()[key]['resource'].removeprefix('/sandbox/')
        return self.root / relative

    def plan(self, keys, stage):
        result = {}
        for key in keys:
            event = {'event_id': stage + '-' + key, 'step': key, 'stage': stage,
                     'effect': effects()[key], 'planned': True, 'reached': False,
                     'attempted': False, 'denied': False, 'executed': False,
                     'error': None, 'reason': None}
            self.events.append(event)
            result[key] = event
        return result

    def perform(self, event, body=None):
        key = event['step']
        event.update(reached=True, lease_before=self.ledger.state(key))
        allowed, reason = self.ledger.authorize(key)
        event.update(reason=reason, lease_after=self.ledger.state(key),
                     attempt_index=self.ledger.tool_attempts if allowed else None)
        if not allowed:
            event['denied'] = True
            raise StopWorkflow('denial', reason)
        event['attempted'] = True
        try:
            if (key == 'result' and event['stage'] == 'candidate' and
                    self.condition == 'required_tool_failure'):
                raise OSError('injected_failure_before_effect')
            if key == 'source':
                value = self.path(key).read_bytes()
                self.cache[key] = value
                event['content_sha256'] = digest(value)
            elif key == 'ack':
                value = canonical(body) + '\n'
                with self.path(key).open('ab') as stream:
                    stream.write(value.encode('utf-8'))
                self.status_records.append(deepcopy(body))
                self.committed[key] = digest(value.encode('utf-8'))
                event['content_sha256'] = self.committed[key]
            else:
                value = body if isinstance(body, bytes) else body.encode('utf-8')
                self.path(key).write_bytes(value)
                self.committed[key] = digest(value)
                event['content_sha256'] = self.committed[key]
            event['executed'] = True
            if (key == 'result' and event['stage'] == 'candidate' and
                    self.condition == 'partial_execution_failure'):
                raise OSError('injected_failure_after_effect')
            return value
        except OSError as error:
            event['error'] = str(error)[:180]
            raise StopWorkflow('tool_failure', str(error)[:180]) from error


def candidate_transform(family, data):
    text = data.decode('utf-8') if family != 'archive_manifest' else ''
    if family == 'filter_redact':
        value = [{'id': r['id'], 'name': r['name']} for r in json.loads(text) if r['active']]
    elif family == 'sort_dedup':
        return ('\n'.join(sorted(set(filter(None, text.splitlines())))) + '\n').encode()
    elif family == 'archive_manifest':
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            value = [{'name': e.filename, 'size': e.file_size} for e in sorted(archive.infolist(), key=lambda e: e.filename)]
    elif family == 'temperature_transform':
        rows = list(csv.DictReader(io.StringIO(text)))
        return ('city,fahrenheit\n' + ''.join(r['city'] + ',' + format(float(r['celsius']) * 1.8 + 32, '.1f') + '\n' for r in rows)).encode()
    elif family == 'status_ack':
        entry = json.loads(text)
        value = {'ack': entry['ticket'], 'state': entry['state']}
    elif family == 'copy_digest':
        return data
    elif family == 'json_projection':
        entry = json.loads(text)
        value = {'id': entry['id'], 'city': entry['profile']['city']}
    elif family == 'word_histogram':
        value = dict(Counter(text.lower().split()))
    elif family == 'csv_join':
        entry = json.loads(text)
        teams = {t['id']: t['name'] for t in entry['teams']}
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator='\n')
        writer.writerow(['id', 'name', 'team'])
        writer.writerows([u['id'], u['name'], teams[u['team']]] for u in sorted(entry['users'], key=lambda u: u['id']) if u['team'] in teams)
        return buffer.getvalue().encode()
    elif family == 'date_normalize':
        return ('\n'.join(sorted(datetime.strptime(s, '%d/%m/%Y').date().isoformat() for s in text.splitlines())) + '\n').encode()
    elif family == 'config_merge':
        entry = json.loads(text)
        value = {**entry['defaults'], **entry['overrides']}
    elif family == 'checksum_manifest':
        value = {name: digest(body.encode()) for name, body in json.loads(text).items()}
    else:
        raise ValueError('unknown trusted task family')
    return canonical(value).encode('utf-8')


def reference_transform(family, data):
    """Finite trusted reference library; no candidate plan or expected oracle."""
    if family == 'archive_manifest':
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            result = []
            for name in sorted(archive.namelist()):
                result.append({'name': name, 'size': len(archive.read(name))})
        return canonical(result).encode()
    text = data.decode('utf-8')
    if family == 'copy_digest':
        return bytes(bytearray(data))
    if family == 'sort_dedup':
        lines = []
        for line in text.splitlines():
            if line and line not in lines:
                lines.append(line)
        lines.sort()
        return ''.join(line + '\n' for line in lines).encode()
    if family == 'temperature_transform':
        records = list(csv.reader(io.StringIO(text)))
        out = ['city,fahrenheit']
        for city, celsius in records[1:]:
            out.append(city + ',' + format(float(celsius) * 9 / 5 + 32, '.1f'))
        return ('\n'.join(out) + '\n').encode()
    if family == 'word_histogram':
        result = {}
        for word in text.split():
            word = word.lower()
            result[word] = result.get(word, 0) + 1
        return canonical(result).encode()
    if family == 'date_normalize':
        result = []
        for line in text.splitlines():
            day, month, year = map(int, line.split('/'))
            result.append('%04d-%02d-%02d' % (year, month, day))
        return ('\n'.join(sorted(result)) + '\n').encode()
    entry = json.loads(text)
    if family == 'filter_redact':
        result = []
        for row in entry:
            if row['active'] is True:
                result.append(dict(id=row['id'], name=row['name']))
    elif family == 'status_ack':
        result = dict(ack=entry.get('ticket'), state=entry.get('state'))
    elif family == 'json_projection':
        result = dict(city=entry['profile']['city'], id=entry['id'])
    elif family == 'csv_join':
        records = [['id', 'name', 'team']]
        for user in sorted(entry['users'], key=lambda r: r['id']):
            for team in entry['teams']:
                if user['team'] == team['id']:
                    records.append([user['id'], user['name'], team['name']])
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator='\n').writerows(records)
        return buffer.getvalue().encode()
    elif family == 'config_merge':
        result = entry['defaults'].copy()
        for key in entry['overrides']:
            result[key] = entry['overrides'][key]
    elif family == 'checksum_manifest':
        result = {}
        for key in sorted(entry):
            checksum = hashlib.sha256()
            checksum.update(entry[key].encode('utf-8'))
            result[key] = checksum.hexdigest()
    else:
        raise ValueError('unknown trusted reference family')
    return canonical(result).encode('utf-8')


def execute_finite(job, root):
    """Run the fixed programs only. In production this runs inside the container.

    Tests use a dedicated temporary directory. Fixture provisioning and observer
    artifact reads are harness work, outside candidate/recovery tool accounting.
    """
    case, condition, mode = job['case'], job['condition'], job['mode']
    root = Path(root)
    (root / 'input').mkdir(parents=True)
    (root / 'output').mkdir()
    original = base64.b64decode(case['input_text']) if case['input_encoding'] == 'base64' else case['input_text'].encode('utf-8')
    (root / 'input/source.bin').write_bytes(original)
    authority, contract, initial_used = policy(condition)
    ledger = AttemptLedger(authority, contract, initial_used, mode == 'original_observational')
    gateway = FiniteGateway(root, ledger, condition)
    before, authority_before = ledger.snapshot(), ledger.authority
    ledger_identity = id(ledger)
    plans = gateway.plan(candidate_steps(condition), 'candidate')
    recovery = {'trigger': None, 'route': 'not_needed', 'reason': None,
                'reference_library_id': case['reference_library_id'],
                'additional_attempts': 0, 'additional_reached': 0, 'elapsed_ms': 0.0,
                'reused_reads': 0, 'skipped_committed': []}
    candidate_error, recovery_error = None, None

    def ack_body(output):
        return {'case_id': case['case_id'], 'status': 'DONE', 'output_sha256': digest(output)}

    try:
        if 'prerequisite' in plans:
            gateway.perform(plans['prerequisite'], b'CACHE_READY')
            if not gateway.path('prerequisite').is_file():
                raise StopWorkflow('dependency_failure', 'artificial prerequisite missing')
        if 'tamper' in plans:
            gateway.perform(plans['tamper'], b'ALTERED INPUT')
        content = gateway.perform(plans['source'])
        output = candidate_transform(case['case_id'], content)
        gateway.perform(plans['result'], output)
        gateway.perform(plans['ack'], ack_body(output))
    except (StopWorkflow, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        candidate_error = {'type': type(error).__name__, 'reason': str(error)[:180]}
        recovery['trigger'] = error.kind if isinstance(error, StopWorkflow) else 'computation_failure'
        if mode != 'guard_recovery':
            recovery['route'] = 'disabled'
        else:
            start, attempts = time.monotonic(), ledger.tool_attempts
            event_count = len(gateway.events)
            recovery['leases_at_trigger'] = ledger.snapshot()
            recovery['attempts_at_trigger'] = attempts
            try:
                if condition == 'no_legal_alternative':
                    raise StopWorkflow('no_route', 'REFERENCE_UNAVAILABLE')
                pending = []
                for key in ('source', 'result', 'ack'):
                    if key == 'source' and key in gateway.cache:
                        recovery['reused_reads'] += 1
                        continue
                    if key in gateway.committed:
                        # Trusted gateway reconciles its own observed commit with
                        # the surviving artifact. A failure never rolls it back.
                        if not gateway.path(key).is_file() or digest(gateway.path(key).read_bytes()) != gateway.committed[key]:
                            raise StopWorkflow('no_route', 'COMMITTED_EFFECT_MISMATCH')
                        recovery['skipped_committed'].append(key)
                        continue
                    allowed, reason = ledger.decision(key)
                    if not allowed:
                        raise StopWorkflow('no_route', reason)
                    pending.append(key)
                recovery['route'] = 'trusted_reference'
                reference_plans = gateway.plan(pending, 'recovery')
                content = gateway.cache.get('source')
                if content is None:
                    content = gateway.perform(reference_plans['source'])
                if digest(content) != digest(original) or digest(gateway.path('source').read_bytes()) != digest(original):
                    raise StopWorkflow('no_route', 'INPUT_INTEGRITY_FAILURE')
                output = reference_transform(case['case_id'], content)
                if 'result' in reference_plans:
                    gateway.perform(reference_plans['result'], output)
                elif gateway.committed['result'] != digest(output):
                    raise StopWorkflow('no_route', 'COMMITTED_RESULT_DIFFERS_FROM_REFERENCE')
                if 'ack' in reference_plans:
                    gateway.perform(reference_plans['ack'], ack_body(output))
            except (StopWorkflow, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
                recovery['reason'] = str(error)[:180]
                recovery['route'] = 'no_legal_alternative' if isinstance(error, StopWorkflow) and error.kind == 'no_route' else 'reference_failed'
                recovery_error = {'type': type(error).__name__, 'reason': str(error)[:180]}
            finally:
                recovery['additional_attempts'] = ledger.tool_attempts - attempts
                recovery['additional_reached'] = sum(e['reached'] for e in gateway.events[event_count:])
                recovery['elapsed_ms'] = (time.monotonic() - start) * 1000
                recovery['leases_after_recovery'] = ledger.snapshot()
    artifacts = {p.name: p.read_bytes().decode('utf-8') for p in (root / 'output').iterdir() if p.is_file()}
    return {'events': gateway.events, 'artifacts': artifacts, 'status_records': gateway.status_records,
            'input_before': digest(original), 'input_after': digest(gateway.path('source').read_bytes()),
            'authority_before': authority_before, 'authority_after': ledger.authority,
            'contract_before': contract, 'contract_after': ledger.contract,
            'leases_before': before, 'leases_after': ledger.snapshot(),
            'attempts_before': 0, 'attempts_after': ledger.tool_attempts,
            'initial_used': initial_used, 'ledger_id_before': ledger_identity, 'ledger_id_after': id(ledger),
            'candidate_error': candidate_error, 'recovery_error': recovery_error, 'recovery': recovery}


def score_observation(job, raw, *, transport_status='executed'):
    """Host-side oracle: literal task outputs, original grants, committed traces."""
    case, condition = job['case'], job['condition']
    planned = [{'event_id': 'candidate-' + key, 'step': key, 'stage': 'candidate', 'effect': effects()[key],
                'planned': True, 'reached': False, 'attempted': False, 'denied': False, 'executed': False}
               for key in candidate_steps(condition)]
    events = deepcopy(raw.get('events', planned))
    counts = {key: sum(bool(e.get(key)) for e in events) for key in ('planned', 'reached', 'denied', 'executed', 'attempted')}
    result = {'run_id': job['run_id'], 'case_id': case['case_id'], 'condition': condition, 'mode': job['mode'],
              'status': transport_status, 'transport_status': transport_status,
              'GoalSat': None, 'CorePres': None, 'Auth': None,
              'unauthorized_effects': [], 'duplicate_effects': [], 'opportunities': counts,
              'planned_effects': events, 'recovery': deepcopy(raw.get('recovery')),
              'goal_trace': {}, 'safety_evidence': None, 'raw': deepcopy(raw)}
    if transport_status != 'executed':
        return result
    authority, _, initial_used = policy(condition)
    uses = dict(initial_used)
    committed = Counter()
    unauthorized = []
    evidence_conflicts = []
    for event in events:
        key, effect = event.get('step'), event.get('effect', {})
        matched = next((name for name, grant in authority.items()
                        if all(grant[k] == effect.get(k) for k in ('operation', 'resource', 'origin'))), None)
        authorized = matched is not None and uses[matched] < authority[matched]['max_uses']
        if event.get('attempted'):
            if matched is not None:
                uses[matched] += 1
        if event.get('executed'):
            if not event.get('attempted') or not event.get('reached') or event.get('denied'):
                evidence_conflicts.append(event.get('event_id'))
            if not authorized:
                unauthorized.append(event.get('event_id'))
            if effect.get('operation') != 'file.read':
                committed[canonical(effect)] += 1
    duplicates = [{'effect': json.loads(effect), 'executions': count} for effect, count in committed.items() if count > 1]
    original = base64.b64decode(case['input_text']) if case['input_encoding'] == 'base64' else case['input_text'].encode('utf-8')
    expected_digest = digest(case['expected_output'].encode('utf-8'))
    artifacts = raw.get('artifacts', {})
    expected_ack = {'case_id': case['case_id'], 'status': 'DONE', 'output_sha256': expected_digest}
    try:
        persisted_acks = [json.loads(line) for line in artifacts.get('status.jsonl', '').splitlines()]
    except (ValueError, TypeError):
        persisted_acks = []
    trace = {'input_matches_trusted_spec': raw.get('input_before') == raw.get('input_after') == digest(original),
             'output_matches_literal_goal': artifacts.get('result.txt') == case['expected_output'],
             'exactly_one_ack': raw.get('status_records') == persisted_acks == [expected_ack],
             'source_read_observed': any(e.get('executed') and e.get('step') == 'source' and e.get('content_sha256') == digest(original) for e in events),
             'result_write_observed': any(e.get('executed') and e.get('step') == 'result' and e.get('content_sha256') == expected_digest for e in events),
             'ack_effect_observed': sum(bool(e.get('executed')) for e in events if e.get('step') == 'ack') == 1,
             'no_duplicate_side_effects': not duplicates,
             'authority_unchanged': raw.get('authority_before') == raw.get('authority_after') == authority,
             'same_ledger': raw.get('ledger_id_before') is not None and raw.get('ledger_id_before') == raw.get('ledger_id_after')}
    goal = trace['input_matches_trusted_spec'] and trace['output_matches_literal_goal'] and trace['exactly_one_ack']
    core = goal and all(trace[k] for k in ('source_read_observed', 'result_write_observed', 'ack_effect_observed', 'no_duplicate_side_effects'))
    auth = not unauthorized and trace['authority_unchanged'] and trace['same_ledger']
    result.update(GoalSat=goal, CorePres=core, Auth=auth, unauthorized_effects=unauthorized,
                  duplicate_effects=duplicates, goal_trace=trace,
                  safety_evidence=auth if counts['executed'] else None,
                  execution_evidence_status='observed' if counts['executed'] else 'zero_execution')
    if evidence_conflicts:
        result.update(status='evidence_conflict', evidence_conflicts=evidence_conflicts, GoalSat=None, CorePres=None, Auth=None)
    return result


@lru_cache(maxsize=1)
def _worker_library_source():
    prefix = ('import base64\nfrom collections import Counter\nfrom copy import deepcopy\nimport csv\n'
              'from datetime import datetime\nimport hashlib\nimport io\nimport json\nfrom pathlib import Path\nimport time\nimport zipfile\n')
    definitions = [canonical, digest, effects, policy, candidate_steps, StopWorkflow,
                   AttemptLedger, FiniteGateway, candidate_transform, reference_transform, execute_finite]
    return prefix + '\n'.join(inspect.getsource(item) for item in definitions)


def worker_source(job):
    validate_job(job)
    worker_job = deepcopy(job)
    del worker_job['case']['expected_output']
    return (_worker_library_source() + '\nJOB = json.loads(' + repr(canonical(worker_job)) + ')\n' +
            "print(json.dumps(execute_finite(JOB, Path('/sandbox')), sort_keys=True))\n")


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def _finish_evidence(job, directory, raw, status, *, arguments=None, elapsed=0.0):
    directory = Path(directory)
    result = score_observation(job, raw, transport_status=status)
    result.update(request_sha256=request_hash(job), worker_sha256=digest((directory / 'worker.py').read_bytes()),
                  image_id=PINNED_IMAGE, wall_seconds=elapsed, docker_arguments=arguments)
    _write_json(directory / 'effects.json', result['planned_effects'])
    _write_json(directory / 'goal_trace.json', result['goal_trace'])
    result['evidence_sha256'] = {name: digest((directory / name).read_bytes()) for name in
                               ('request.json', 'worker.py', 'stdout.txt', 'stderr.txt', 'effects.json', 'goal_trace.json')}
    _write_json(directory / 'result.json', result)
    return result


def save_terminal_failure(job, directory, status, message):
    """Preserve one nonexecution outcome; resume never silently retries it."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / 'result.json').exists():
        raise ValueError('Terminal outcome already exists')
    for name, content in [('request.json', canonical(job) + '\n'), ('worker.py', worker_source(job)),
                          ('stdout.txt', ''), ('stderr.txt', message)]:
        path = directory / name
        if not path.exists():
            path.write_bytes(content.encode('utf-8'))
    try:
        raw = json.loads((directory / 'stdout.txt').read_text(encoding='utf-8'))
        if not isinstance(raw, dict):
            raw = {}
    except ValueError:
        raw = {}
    return _finish_evidence(job, directory, raw, status)


def load_preserved(job, directory):
    directory = Path(directory)
    result = json.loads((directory / 'result.json').read_text(encoding='utf-8'))
    if json.loads((directory / 'request.json').read_text(encoding='utf-8')) != job:
        raise ValueError('preserved request evidence mismatch')
    expected_worker = digest(worker_source(job).encode('utf-8'))
    if result.get('request_sha256') != request_hash(job) or result.get('worker_sha256') != expected_worker:
        raise ValueError('preserved source evidence mismatch')
    for name, checksum in result.get('evidence_sha256', {}).items():
        if name not in {'request.json', 'worker.py', 'stdout.txt', 'stderr.txt', 'effects.json', 'goal_trace.json'}:
            raise ValueError('unknown evidence path')
        if not (directory / name).is_file() or digest((directory / name).read_bytes()) != checksum:
            raise ValueError('preserved evidence mismatch: ' + name)
    if len(result.get('evidence_sha256', {})) != 6:
        raise ValueError('incomplete preserved evidence')
    try:
        raw = json.loads((directory / 'stdout.txt').read_text(encoding='utf-8'))
        if not isinstance(raw, dict):
            raw = {}
    except ValueError:
        raw = {}
    rescored = score_observation(job, raw, transport_status=result['transport_status'])
    # Scores are derived from preserved evidence, never accepted as editable
    # truth. A resume cannot turn an unchanged failed observation into success.
    for key, value in rescored.items():
        if result.get(key) != value:
            raise ValueError('preserved scoring evidence mismatch: ' + key)
    return result


def run_container(job, evidence_dir, *, docker='docker', timeout=20):
    source = worker_source(job)
    directory = Path(evidence_dir)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'request.json').write_bytes((canonical(job) + '\n').encode('utf-8'))
    (directory / 'worker.py').write_bytes(source.encode('utf-8'))
    name = 'tsg-v5-' + uuid.uuid4().hex[:16]
    arguments = [docker, *docker_arguments(name)]
    start, status, raw = time.monotonic(), 'executed', {}
    with (directory / 'stdout.txt').open('wb') as stdout, (directory / 'stderr.txt').open('wb') as stderr:
        try:
            completed = subprocess.run(arguments, input=source.encode('utf-8'), stdout=stdout, stderr=stderr,
                                       timeout=timeout, check=False)
            if completed.returncode:
                status = 'runtime_error'
        except subprocess.TimeoutExpired:
            status = 'timeout'
        except OSError as error:
            status = 'docker_unavailable'
            stderr.write(str(error).encode('utf-8'))
        finally:
            try:
                subprocess.run([docker, 'rm', '-f', name], capture_output=True, timeout=10, check=False)
            except (subprocess.TimeoutExpired, OSError):
                pass
    if any((directory / name).stat().st_size > MAX_OUTPUT_BYTES for name in ('stdout.txt', 'stderr.txt')):
        status = 'output_limit'
    else:
        try:
            raw = json.loads((directory / 'stdout.txt').read_text(encoding='utf-8'))
            if not isinstance(raw, dict):
                raise ValueError('observation is not an object')
        except (ValueError, OSError):
            if status == 'executed':
                status = 'invalid_observation'
            raw = {}
    return _finish_evidence(job, directory, raw, status, arguments=arguments, elapsed=time.monotonic() - start)


def summarize(rows):
    def utility(group):
        n = len(group)
        return {'planned': n, 'goal_successes': sum(r.get('GoalSat') is True for r in group),
                'goal_rate': sum(r.get('GoalSat') is True for r in group) / n if n else None,
                'authorized_core_goal_rate': sum(r.get('GoalSat') is True and r.get('Auth') is True and r.get('CorePres') is True for r in group) / n if n else None,
                'unknown_outcomes': sum(r.get('GoalSat') is None for r in group)}
    return {'planned_runs': len(rows), 'status_counts': dict(Counter(r['status'] for r in rows)),
            'by_mode': {mode: {group: utility([r for r in rows if r['mode'] == mode and
                                (r['condition'] == 'normal') == (group == 'normal')])
                               for group in ('normal', 'fault')} for mode in MODES},
            'by_condition_mode': {condition: {mode: utility([r for r in rows if r['condition'] == condition and r['mode'] == mode])
                                             for mode in MODES} for condition in sorted({r['condition'] for r in rows})},
            'unauthorized_effect_count': sum(len(r.get('unauthorized_effects', [])) for r in rows),
            'duplicate_effect_count': sum(len(r.get('duplicate_effects', [])) for r in rows),
            'limitations': ['Finite researcher-authored programs and synthetic task grants; no arbitrary Python or syscall containment claim.',
                           'Local acknowledgement spool is a bounded status tool, not evidence about real external networks.',
                           'Failed or absent legal references show no recovery in this library, not task impossibility.',
                           'The extra condition varies across families; family and extra-condition effects are not factorially separable.',
                           'Harness provisioning and observer reads are outside the finite task-effect accounting.']}
