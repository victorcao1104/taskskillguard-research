import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from tsg.corpus import build_manifest, verify_manifest

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path)
p.add_argument('--out', type=Path, default=Path('data/manifests'))
p.add_argument('--sample-size', type=int, default=180)
p.add_argument('--verify', action='store_true')
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
if a.verify:
    rows = [json.loads(s) for s in (a.out/'skills_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    report = verify_manifest(rows)
    (a.out/'immutability_after.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
else:
    rows, report = build_manifest(a.root, a.sample_size)
    (a.out/'skills_manifest.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    (a.out/'corpus_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in {'exclusions'}}))
