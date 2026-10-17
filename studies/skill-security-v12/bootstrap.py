"""Preserve old tracked bytes; never edits archived research."""
import hashlib
import json
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def main():
    target = HERE / 'provenance' / 'baseline.json'
    if target.exists():
        raise SystemExit('Baseline already saved; refusing overwrite')
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    names = [n for n in names if n]
    def one(name):
        p = ROOT / name
        return name, hashlib.sha256(p.read_bytes()).hexdigest()
    with ThreadPoolExecutor(max_workers=8) as pool:
        hashes = dict(pool.map(one, names))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'base_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'files':hashes,'count':len(hashes)},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'preserved_files':len(hashes),'baseline_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))

if __name__ == '__main__': main()
