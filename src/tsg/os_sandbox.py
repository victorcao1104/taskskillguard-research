"""Docker OS containment, distinct from the in-memory tool-policy experiments.

Only bounded, hash-verified source copies enter containers. There are no host
mounts, inherited environment variables, real credentials, or host execution
fallbacks. Trusted root supervision traces a separate unprivileged payload.
"""
from __future__ import annotations

import hashlib
import base64
import io
import json
import re
import subprocess
import tarfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


IMAGE = 'taskskillguard-os:phase2'
FIXTURES = ('pdf', 'csv', 'git', 'http', 'smtp', 'sqlite')


def _relative(name):
    normalized = name.replace('\\', '/')
    p = PurePosixPath(normalized)
    if not normalized or p.is_absolute() or '..' in p.parts or ':' in normalized or '\x00' in normalized:
        raise ValueError('unsafe source path')
    return p


def stage_bundle(row, destination, *, max_bytes=8_000_000, max_files=256):
    """Read only manifest-listed files; never traverse links or execute source."""
    unresolved_root = Path(row['bundle_path'])
    if unresolved_root.is_symlink() or (hasattr(unresolved_root, 'is_junction') and unresolved_root.is_junction()):
        raise ValueError('linked source root path rejected')
    root = unresolved_root.resolve()
    files = row['file_sha256']
    if len(files) > max_files:
        raise ValueError('file count limit exceeded')
    content = []
    total = 0
    for name, expected in sorted(files.items()):
        rel = _relative(name)
        path = root.joinpath(*rel.parts)
        if not path.resolve().is_relative_to(root):
            raise ValueError('source path escaped bundle')
        for parent in [path, *path.parents]:
            if parent == root:
                break
            if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
                raise ValueError('linked source path rejected')
        if not path.is_file() or path.stat().st_size > max_bytes - total:
            raise ValueError('source byte limit exceeded or non-regular source')
        data = path.read_bytes()
        total += len(data)
        if total > max_bytes:
            raise ValueError('source byte limit exceeded')
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('source hash mismatch')
        content.append((rel, data))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, 'w') as archive:
        for rel, data in content:
            item = tarfile.TarInfo('source/' + rel.as_posix())
            item.size, item.mode, item.uid, item.gid, item.mtime = len(data), 0o444, 0, 0, 0
            archive.addfile(item, io.BytesIO(data))
    return {'files': len(content), 'bytes': total, 'archive_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'skill_id': row['skill_id']}


def validate_job(job):
    if not isinstance(job, dict) or job.get('kind') not in {'fixture', 'source'}:
        raise ValueError('unsupported execution kind')
    if job['kind'] == 'fixture':
        if job.get('guard_enabled') and job.get('variant') == 'reference':
            raise ValueError('independent trusted reference is not a guarded fixture')
        if job.get('guard_enabled') and (not isinstance(job.get('policy'), list) or len(job['policy']) > 128 or any(not isinstance(r, dict) or set(r) != {'operation', 'resource'} or any(not isinstance(v, str) or len(v) > 1024 for v in r.values()) for r in job['policy'])):
            raise ValueError('invalid exact resource policy')
        if job.get('fixture') not in FIXTURES or job.get('variant', 'original') not in {'original', 'neutralized', 'reference'}:
            raise ValueError('unsupported fixture or variant')
        if job.get('target', 'optional_cache') not in {'optional_cache', 'core_read', 'send'}:
            raise ValueError('unsupported single-point ablation')
    elif job['kind'] == 'source':
        p = _relative(job.get('script', ''))
        if p.suffix not in {'.py', '.sh'}:
            raise ValueError('unsupported source interpreter')
        args = job.get('args', [])
        if not isinstance(args, list) or len(args) > 32 or any(not isinstance(a, str) or len(a) > 1024 or '\x00' in a for a in args):
            raise ValueError('source argument limit')
    return job


def parse_trace(text):
    counts = {'process_events': 0, 'file_events': 0, 'network_events': 0, 'denied_errno': {}}
    process = {'execve', 'execveat', 'clone', 'clone3', 'fork', 'vfork', 'wait4', 'waitid', 'exit', 'exit_group'}
    network = {'socket', 'socketpair', 'connect', 'bind', 'listen', 'accept', 'accept4', 'sendto', 'recvfrom', 'sendmsg', 'recvmsg', 'shutdown', 'getsockopt', 'setsockopt', 'getsockname', 'getpeername'}
    for line in text.splitlines():
        match = re.search(r'(?:^|\s)([a-zA-Z_][a-zA-Z_0-9]*)\(', line)
        if not match:
            continue
        syscall = match.group(1)
        key = 'process_events' if syscall in process else 'network_events' if syscall in network else 'file_events'
        counts[key] += 1
        failure = re.search(r'= -1 (E[A-Z0-9]+)', line)
        if failure:
            code = failure.group(1)
            counts['denied_errno'][code] = counts['denied_errno'].get(code, 0) + 1
    counts['trace_lines'] = len(text.splitlines())
    return counts


def replay_verdict(original, neutralized, reference):
    if neutralized.get('ablation_valid') is False:
        return {'status': 'invalid_ablation', 'task_necessary': None}
    if any(r.get('status') != 'executed' for r in (original, neutralized, reference)):
        return {'status': 'runtime_error', 'task_necessary': None}
    if not original.get('target_triggered'):
        return {'status': 'not_triggered', 'task_necessary': None}
    if not original.get('goal_satisfied'):
        return {'status': 'original_failed', 'task_necessary': None}
    if neutralized.get('goal_satisfied'):
        return {'status': 'comparable', 'task_necessary': False}
    if reference.get('goal_satisfied') and reference.get('reference_excludes_target') is True:
        return {'status': 'dependency_blocked', 'task_necessary': False}
    return {'status': 'unknown', 'task_necessary': None}


class ContainerSandbox:
    def __init__(self, image=IMAGE, timeout=45, docker='docker'):
        self.image, self.timeout, self.docker = image, timeout, docker

    def command(self, *args, timeout=20, check=True, input=None):
        result = subprocess.run([self.docker, *args], input=input, capture_output=True, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', 'replace')[:4000])
        return result

    def diagnose(self):
        r = self.command('version', '--format', '{{json .}}', check=False)
        return {'available': r.returncode == 0, 'stdout': r.stdout.decode('utf-8', 'replace'), 'stderr': r.stderr.decode('utf-8', 'replace')}

    def run(self, job, evidence_dir, source_archive=None):
        validate_job(job)
        if job['kind'] == 'source' and source_archive is None:
            raise ValueError('source execution requires staged archive')
        evidence = Path(evidence_dir).resolve()
        evidence.mkdir(parents=True, exist_ok=True)
        name = 'tsg-' + uuid.uuid4().hex[:16]
        volume = name + '-input'
        staging = name + '-stage'
        jobfile = evidence / 'job.json'
        jobfile.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
        start = time.monotonic()
        # Only the trusted supervisor gets these capabilities. The target
        # drops UID/GID and has zero effective capabilities plus no_new_privs.
        args = ['create', '--name', name, '--network', 'none', '--read-only',
                '--cap-drop', 'ALL', '--cap-add', 'SETUID', '--cap-add', 'SETGID', '--cap-add', 'SYS_PTRACE', '--cap-add', 'KILL', '--cap-add', 'DAC_READ_SEARCH',
                '--security-opt', 'no-new-privileges', '--pids-limit', '64', '--memory', '256m', '--memory-swap', '256m',
                '--cpus', '0.5', '--ulimit', 'nofile=128:128', '--ulimit', 'fsize=16777216:16777216',
                '--tmpfs', '/sandbox:rw,nosuid,noexec,size=64m,mode=755',
                '--tmpfs', '/audit:rw,nosuid,noexec,size=32m,mode=700',
                '--tmpfs', '/tmp:rw,nosuid,noexec,size=16m,mode=1777',
                '--mount', 'type=volume,src=' + volume + ',dst=/source,readonly',
                '--user', '0:0', '--workdir', '/sandbox', '--env', 'PYTHONDONTWRITEBYTECODE=1',
                '--env', 'PYTHONUNBUFFERED=1', '--env', 'HOME=/sandbox/work', self.image]
        result = None
        try:
            # Docker refuses cp into a read-only rootfs. A short trusted helper
            # populates a fresh engine-managed volume, then is destroyed before
            # that volume is attached read-only to the experimental container.
            self.command('volume', 'create', volume)
            self.command('run', '-d', '--name', staging, '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '64m', '--cpus', '0.5', '--pids-limit', '16', '--mount', 'type=volume,src=' + volume + ',dst=/stage', '--entrypoint', 'python', self.image, '-c', 'import time; time.sleep(120)')
            self.command('cp', str(jobfile), staging + ':/stage/job.json')
            if source_archive:
                self.command('cp', '-', staging + ':/stage/', input=Path(source_archive).read_bytes())
            self.command('rm', '-f', staging)
            self.command(*args)
            self.command('start', name)
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                probe = self.command('exec', name, 'cat', '/audit/result.json', check=False)
                if probe.returncode == 0:
                    result = json.loads(probe.stdout)
                    break
                state = self.command('inspect', name, '--format', '{{.State.Running}}', check=False)
                if state.stdout.strip() != b'true':
                    break
                time.sleep(0.25)
            # Docker Desktop's archive endpoint does not reliably expose tmpfs
            # mounts. Read bounded regular audit files through trusted exec.
            for filename in ['syscalls.log', 'stdout.txt', 'stderr.txt', 'result.json', 'worker_error.txt']:
                fetched = self.command('exec', name, 'cat', '/audit/' + filename, check=False)
                if fetched.returncode == 0:
                    (evidence / filename).write_bytes(fetched.stdout)
            output = evidence / 'output'
            output.mkdir(exist_ok=True)
            collector = "import pathlib,json,base64; root=pathlib.Path('/sandbox/output'); files=[p for p in root.iterdir() if p.is_file() and not p.is_symlink() and p.stat().st_size<=2000000][:16]; print(json.dumps({p.name:base64.b64encode(p.read_bytes()).decode() for p in files}))"
            collected = self.command('exec', name, 'python', '-c', collector, check=False)
            if collected.returncode == 0:
                for filename, data in json.loads(collected.stdout).items():
                    rel = _relative(filename)
                    if len(rel.parts) == 1:
                        (output / filename).write_bytes(base64.b64decode(data))
            logs = self.command('logs', name, check=False)
            (evidence / 'container.log').write_bytes(logs.stdout + logs.stderr)
            inspected = json.loads(self.command('inspect', name).stdout)[0]
            isolation = {k: inspected['HostConfig'].get(k) for k in ['NetworkMode', 'ReadonlyRootfs', 'CapDrop', 'CapAdd', 'Memory', 'MemorySwap', 'NanoCpus', 'PidsLimit', 'SecurityOpt', 'Binds', 'Tmpfs']}
            isolation['mounts'] = inspected['Mounts']
            (evidence / 'isolation.json').write_text(json.dumps(isolation, indent=2), encoding='utf-8')
            if result is None:
                result = {'status': 'timeout' if time.monotonic() >= deadline else 'runtime_error', 'goal_satisfied': None, 'resources': {}}
            trace_path = evidence / 'syscalls.log'
            result['audit'] = parse_trace(trace_path.read_text(encoding='utf-8', errors='replace')) if trace_path.exists() else None
            result['isolation'] = isolation
            result['wall_seconds_including_container'] = time.monotonic() - start
            result['image_id'] = inspected['Image']
            result['job'] = job
            result['run_metadata'] = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'model_id': None, 'model_version': None, 'temperature': None, 'seed': None, 'seed_status': 'deterministic fixture; no model called', 'max_tool_steps': 64 if job['kind'] == 'fixture' else None, 'arbitrary_script_step_limit': 'unsupported; CPU, PIDs, RAM, file-size and wall-clock limited', 'tool_catalog_version': 'os-fixtures-v1', 'policy_version': 'exact-scope-v1', 'raw_trace_path': str(trace_path), 'source_archive_sha256': hashlib.sha256(Path(source_archive).read_bytes()).hexdigest() if source_archive else None}
            (evidence / 'host_result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
            return result
        finally:
            self.command('rm', '-f', '-v', name, check=False)
            self.command('rm', '-f', '-v', staging, check=False)
            self.command('volume', 'rm', volume, check=False)
