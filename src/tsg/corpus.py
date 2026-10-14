"""Read-only adapter for the user's skills.sh materializations catalog."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path

SCRIPT_EXT = {'.py', '.js', '.ts', '.sh', '.ps1', '.bash', '.mjs', '.cjs'}
CATEGORIES = {
    'document': r'\b(pdf|docx|document|markdown|presentation|slides|convert)\b',
    'data': r'\b(csv|data|analysis|analytics|report|spreadsheet|excel|statistics)\b',
    'development': r'\b(git|code|test|debug|review|develop|react|frontend|typescript)\b',
    'devops': r'\b(deploy|cloud|docker|kubernetes|ci|devops|infrastructure|automation)\b',
    'communication': r'\b(email|mail|slack|discord|telegram|message|communication|calendar)\b',
    'integration': r'\b(api|database|sql|integration|mcp|query|endpoint|service)\b',
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@contextmanager
def readonly_connection(path: Path):
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    try:
        yield db
    finally:
        db.close()


def _rank(value: str, seed: int) -> str:
    return sha256(f'{seed}:{value}'.encode())


def _category(text: str) -> str:
    counts = {k: len(re.findall(v, text.lower())) for k, v in CATEGORIES.items()}
    return max(counts, key=counts.get) if max(counts.values()) else 'other'


def _files(root: Path):
    resolved_root = root.resolve()
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in {'.git', 'node_modules', '__pycache__'} and not (Path(folder)/d).is_symlink() and not (Path(folder)/d).is_junction())
        for name in sorted(files):
            path = Path(folder) / name
            if not path.is_symlink() and path.resolve().is_relative_to(resolved_root):
                yield path


def group_split(rows: list[dict], seed: int) -> list[dict]:
    """Union shared publishers/repos/exact selected text; not a full-corpus dedup."""
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen = {}
    for i, row in enumerate(rows):
        for field in ('publisher_id', 'repo_id', 'skill_sha256'):
            val = row.get(field)
            if not val:
                continue
            key = (field, val)
            if key in seen:
                parent[find(i)] = find(seen[key])
            seen[key] = i
    members = defaultdict(list)
    for i, row in enumerate(rows):
        members[find(i)].append(row['skill_id'])
    group_ids = {i: 'family-' + sha256('|'.join(sorted(v)).encode())[:16] for i, v in members.items()}
    result = []
    for i, row in enumerate(rows):
        family = group_ids[find(i)]
        bucket = int(_rank(family, seed)[:8], 16) / 2**32
        split = 'development' if bucket < .56 else 'validation' if bucket < .78 else 'held_out_test'
        result.append({**row, 'family_id': family, 'split': split})
    return result


def build_manifest(root: Path, sample_size=180, seed=76420261015):
    root = root.resolve()
    with readonly_connection(root / 'state.sqlite') as db:
        rows = [dict(r) for r in db.execute("SELECT source_native_id,raw_directory FROM materializations WHERE status='completed' ORDER BY source_native_id")]
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        occurrence = {r[0]: json.loads(r[1]) for r in db.execute('SELECT source_native_id,payload_json FROM occurrences')} if 'occurrences' in tables else {}
        dedup = {r[0]: json.loads(r[1]) for r in db.execute('SELECT source_native_id,payload_json FROM dedup_decisions')} if 'dedup_decisions' in tables else {}
    strata = defaultdict(list)
    excluded = []
    for row in rows:
        sid = row['source_native_id']
        bundle = root / 'raw' / row['raw_directory']
        if not bundle.resolve().is_relative_to((root / 'raw').resolve()):
            excluded.append({'source_native_id': sid, 'reason': 'path_outside_corpus'})
            continue
        files = list(_files(bundle))
        docs = sorted((p for p in files if p.name.lower() == 'skill.md'), key=lambda p: (len(p.parts), str(p)))
        if not docs:
            excluded.append({'source_native_id': sid, 'reason': 'missing_skill_md'})
            continue
        try:
            data = docs[0].read_bytes()
        except OSError:
            excluded.append({'source_native_id': sid, 'reason': 'unreadable_skill_md'})
            continue
        scripts = [p for p in files if p.suffix.lower() in SCRIPT_EXT]
        category = _category(sid + '\n' + data[:12000].decode('utf-8', errors='replace'))
        item = {
            'skill_id': 'real-' + sha256(sid.encode())[:16], 'source': 'skills.sh', 'source_native_id': sid,
            'source_url': occurrence.get(sid, {}).get('url'), 'repo_id': '/'.join(sid.split('/')[:2]),
            'publisher_id': sid.split('/')[0], 'download_status': 'completed',
            'raw_directory': row['raw_directory'], 'bundle_path': str(bundle),
            'skill_md_path': str(docs[0].resolve()), 'skill_sha256': sha256(data),
            'script_paths': [str(p.resolve()) for p in scripts], 'file_count': len(files),
            'skill_md_count': len(docs), 'category_heuristic': category,
            'has_scripts': bool(scripts), 'languages': sorted({p.suffix.lower().lstrip('.') for p in scripts}),
            'metadata_root': str(root / 'metadata'), 'source_database': str(root/'state.sqlite'),
            'existing_dedup_decision': dedup.get(sid), 'corpus_relative_path': str(docs[0].relative_to(root)),
        }
        strata[(category, bool(scripts))].append(item)
    for values in strata.values():
        values.sort(key=lambda row: _rank(row['source_native_id'], seed))
    selected = []
    offsets = Counter()
    while len(selected) < sample_size:
        advanced = False
        for key in sorted(strata):
            if offsets[key] < len(strata[key]) and len(selected) < sample_size:
                selected.append(strata[key][offsets[key]])
                offsets[key] += 1
                advanced = True
        if not advanced:
            break
    for item in selected:
        bundle = Path(item['bundle_path'])
        detailed_files = list(_files(bundle))
        file_hashes = {str(p.relative_to(bundle)): sha256(p.read_bytes()) for p in detailed_files}
        item['script_paths'] = [str(p.resolve()) for p in detailed_files if p.suffix.lower() in SCRIPT_EXT]
        item['has_scripts'] = bool(item['script_paths'])
        item['file_count'] = len(detailed_files)
        item['languages'] = sorted({p.suffix.lower().lstrip('.') for p in detailed_files if p.suffix.lower() in SCRIPT_EXT})
        item['file_sha256'] = file_hashes
        item['bundle_sha256'] = sha256(json.dumps(file_hashes, sort_keys=True).encode())
    selected = group_split(selected, seed)
    dev = sorted((r for r in selected if r['split'] == 'development'), key=lambda r: _rank(r['skill_id'], seed+1))
    pilot_ids = {r['skill_id'] for r in dev[:30]}
    for item in selected:
        item['pilot'] = item['skill_id'] in pilot_ids
    report = {
        'completed_count': len(rows), 'eligible_count': sum(map(len, strata.values())), 'sample_count': len(selected),
        'seed': seed, 'source_root': str(root), 'sampling': 'seeded round-robin category x script-presence strata',
        'stratum_population': {f'{k[0]}:{k[1]}': len(v) for k,v in strata.items()},
        'stratum_sample': {f'{k[0]}:{k[1]}': n for k,n in offsets.items()},
        'split_counts': dict(Counter(r['split'] for r in selected)),
        'family_counts': dict(Counter({f: next(r['split'] for r in selected if r['family_id']==f) for f in {r['family_id'] for r in selected}}.values())),
        'exclusions': excluded, 'pilot_count': len(pilot_ids),
    }
    return selected, report


def verify_manifest(rows: list[dict]):
    errors = []
    for row in rows:
        for rel, expected in row['file_sha256'].items():
            path = Path(row['bundle_path']) / rel
            if not path.is_file() or sha256(path.read_bytes()) != expected:
                errors.append({'skill_id': row['skill_id'], 'file': rel})
    return {'checked_bundles': len(rows), 'checked_files': sum(len(r['file_sha256']) for r in rows), 'changes': errors}
