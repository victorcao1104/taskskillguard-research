"""Package paper sources and audit the additive release without network access."""
from pathlib import Path
import gzip
import hashlib
import json
import re
import subprocess
import zipfile

from run import D, ROOT, assert_frozen, budget
from corrected_run import assert_amended
from robust_run import hashes as robust_hashes
from typed_roles import source_hash as typed_hash
from reproduce import audit_cache, preserve_old


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    assert_frozen()
    assert_amended()
    assert robust_hashes() == read(D/'provenance/robust_protocol_freeze.json')['source_hashes']
    assert typed_hash() == read(D/'provenance/typed_roles_freeze.json')['source_sha256']
    assert digest((D/'adaptive_network_rerun.py').read_bytes()) == read(D/'provenance/adaptive_network_rerun.json')['source_sha256']
    old = preserve_old()
    assert not old['changed_old_paths']
    cache = audit_cache()
    b, a = budget()
    exposure = b.total_cost - a['inherited_upper_usd']
    assert exposure <= a['new_cap_usd']
    ledger = (D/'api/budget.jsonl').read_bytes()
    assert digest(ledger[:a['inherited_bytes']]) == a['inherited_sha256']
    paper = read(D/'qa/paper_check.json')
    assert paper['pass'] and paper['pdf_sha256'] == digest((D/'paper.pdf').read_bytes())
    assert (D/'paper.pdf').read_bytes() == (D/'output/paper.pdf').read_bytes()
    replay = read(D/'reproduction/verification.json')
    assert not any(v['mismatches'] for v in replay['comparison'].values())
    assert replay['network_calls'] == 0 and replay['budget_ledger_unchanged']

    sources = sorted([*D.glob('*.tex'), *D.glob('figures/*.pdf'), D/'BUILD.md'])
    with zipfile.ZipFile(D/'ieee-source.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sources:
            entry = zipfile.ZipInfo(path.relative_to(D).as_posix(), (2026, 10, 18, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(D/'ieee-source.zip') as archive:
        assert archive.testzip() is None

    raw_paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z', '--', 'studies/stateful-recovery-v13', 'PHASE13.md'], cwd=ROOT)
    paths = sorted(set(p.decode('utf-8') for p in raw_paths.split(b'\0') if p))
    excluded = {'studies/stateful-recovery-v13/provenance/release_manifest.json'}
    # Format scan, not a claim that every possible secret can be recognized.
    patterns = [re.compile(rb'(?<![A-Za-z0-9])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{25,}'),
                re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
                re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
    findings = []
    inventory = []
    for relative in paths:
        if relative in excluded:
            continue
        path = ROOT/relative
        content = path.read_bytes()
        assert len(content) < 100*1024*1024, ('GIT_LARGE_FILE', relative)
        if path.name.startswith('.env'):
            findings.append({'path': relative, 'reason': 'env_file'})
        if path.suffix.lower() in {'.json', '.jsonl', '.md', '.py', '.tex', '.txt', '.csv', '.log'}:
            content.decode('utf-8')
            if any(pattern.search(content) for pattern in patterns):
                findings.append({'path': relative, 'reason': 'credential_format'})
        elif path.suffix == '.gz':
            expanded = gzip.decompress(content)
            if any(pattern.search(expanded) for pattern in patterns):
                findings.append({'path': relative, 'reason': 'credential_format_in_trace'})
        inventory.append({'path': relative, 'bytes': len(content), 'sha256': digest(content)})
    if findings:
        raise ValueError(json.dumps({'suspicious_files': findings}))
    for scope in ([], ['--cached']):
        whitespace = subprocess.run(['git', '-c', 'core.whitespace=cr-at-eol', 'diff', *scope, '--check', '--', '.', ':(exclude)studies/stateful-recovery-v13/output/paper.log'], cwd=ROOT, capture_output=True)
        assert whitespace.returncode == 0, 'WHITESPACE_CHECK_FAILED'
    report = {'scope': 'All Git-visible study files and additive PHASE13.md, excluding this manifest itself; no old file is rewritten.',
              'prepublication_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
              'old_preservation': old, 'frozen_sources_unchanged': True, 'cache': cache,
              'new_budget_upper_usd': exposure, 'new_budget_limit_usd': a['new_cap_usd'],
              'remaining_usd': a['new_cap_usd']-exposure, 'invoice': False,
              'inherited_ledger_prefix_unchanged': True,
              'credential_format_scan': {'files_with_matches': 0, 'scope': 'Text and decompressed trace files; no credential values printed. Pattern scan is not an exhaustive secrecy proof.'},
              'line_endings': 'Original CRLF bytes retained; whitespace check treats CR at line end as a line ending. Unedited compiler log excluded from style checks (one package-generated trailing space).',
              'paper': paper, 'paper_source_members': len(sources),
              'files': len(inventory), 'total_bytes': sum(i['bytes'] for i in inventory), 'inventory': inventory}
    (D/'provenance/release_manifest.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in {'inventory', 'paper'}}))


if __name__ == '__main__':
    main()
