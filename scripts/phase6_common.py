"""Shared serialization only, not semantic code."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(data):return hashlib.sha256(data).hexdigest()
def jb(obj):return (json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def rb(rows):return ''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows).encode()
def read_rows(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf-8-sig').splitlines() if s]
def immutable(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:raise ValueError('IMMUTABLE_MISMATCH '+str(path))
    else:path.write_bytes(data)
def cases():return read_rows(ROOT/'data/phase6/dev.jsonl')+read_rows(ROOT/'data/phase6/heldout.jsonl')

if __name__=='__main__':
    names=(ROOT/'work/phase6-baseline-names.txt').read_text(encoding='utf-8-sig').splitlines()
    baseline={'commit':'efd19d5e8704bdaec24fd183b81026d1d7fffccd',
              'files':{n:sha((ROOT/n).read_bytes()) for n in names},'count':len(names)}
    immutable(ROOT/'results/phase6/provenance/baseline.json',jb(baseline))
    print(json.dumps({'baseline_files':len(names)}))
