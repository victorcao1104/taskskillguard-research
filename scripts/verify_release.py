"""Offline consistency checks; never contacts a model or executes corpus code."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.models import parse_prediction


def read(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]


def main():
    failures=[]; checked=0
    cases={r['case_id']:r for r in read(ROOT/'data/benchmark/synthetic_cases.jsonl')}
    expected={'development':{'detection':528,'plans':264,'contracts':264,'metamorphic':36},
              'validation':{'detection':176,'plans':88,'contracts':88,'metamorphic':12},
              'held_out':{'detection':352,'plans':176,'contracts':176,'metamorphic':24},
              'real':{'real':60},'transfer':{'predictions':360},'judge':{'predictions':72},'prompt_ablation':{'predictions':48}}
    for phase,tracks in expected.items():
        for track,n in tracks.items():
            path=ROOT/f'results/{phase}/{track}.jsonl'
            if not path.exists():
                failures.append(f'missing {phase}/{track}');continue
            rows=read(path)
            if len(rows)!=n: failures.append(f'{phase}/{track}: {len(rows)} != {n}')
            for row in rows:
                raw_path=ROOT/f'results/api/raw/{row["request_hash"]}.json'
                if not raw_path.exists():
                    failures.append(f'missing raw {row["request_hash"]}');continue
                raw=json.loads(raw_path.read_text(encoding='utf-8'))
                actual=hashlib.sha256(json.dumps({'request':raw['request'],'replicate':raw['replicate']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                if actual!=row['request_hash']:failures.append(f'fingerprint mismatch {raw_path.name}')
                if row['status']=='valid' and track in {'detection','metamorphic'}:
                    ids=[a['id'] for a in cases[row['case_id']]['actions'] if a['operation']!='transform']
                    if parse_prediction(raw['text'],ids)!=row['prediction']:failures.append(f'prediction/raw mismatch {row["case_id"]}')
                checked+=1
    families={}
    for row in read(ROOT/'data/manifests/skills_manifest.jsonl'):
        families.setdefault(row['family_id'],set()).add(row['split'])
        if row['download_status']!='completed':failures.append('noncompleted corpus record')
    if any(len(s)>1 for s in families.values()):failures.append('family split overlap')
    # Only report paths/counts if credential-shaped bytes occur; never print values.
    import re
    pattern=re.compile(rb'\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,})\b')
    for folder in ('src','scripts','docs','data','results','configs'):
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and path.suffix in {'.json','.jsonl','.py','.md','.csv','.txt'} and pattern.search(path.read_bytes()):
                failures.append('credential-shaped data: '+str(path.relative_to(ROOT)))
    manifest=ROOT/'results/verification/artifact_manifest.json'
    if manifest.exists():
        for record in json.loads(manifest.read_text(encoding='utf-8'))['files']:
            path=ROOT/record['path']
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
                failures.append('release hash mismatch: '+record['path'])
    report={'checked_result_records':checked,'corpus_families':len(families),'failures':failures}
    print(json.dumps(report,ensure_ascii=False))
    return bool(failures)


if __name__=='__main__':raise SystemExit(main())
