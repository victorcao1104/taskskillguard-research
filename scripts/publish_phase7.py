"""Finalize hashes after the completed outcome review; retain first manifest."""
import argparse
import json
from phase7_common import ROOT,sha,jb,immutable
from verify_phase7_v2 import verify as verify_evidence

def release_files():
    paths=[]
    for directory in ('data/phase7','results/phase7'):
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file())
    for directory in ('src/tsg','scripts','tests','docs','.github/workflows'):
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and ('phase7' in p.name or '_v7' in p.name) and '__pycache__' not in p.parts)
    paths.append(ROOT/'PHASE7.md')
    excluded={'results/phase7/provenance/release_hashes_v2.json','results/phase7/provenance/release_verification.json'}
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(set(paths)) if p.relative_to(ROOT).as_posix() not in excluded}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze-release',action='store_true');args=parser.parse_args()
    audit=verify_evidence(False)
    path=ROOT/'results/phase7/provenance/release_hashes_v2.json'
    if args.freeze_release:
        files=release_files()
        immutable(path,jb({'files':files,'count':len(files),'supersedes':'release_hashes.json',
            'reason':'final outcome-review append arrived during initial verification; original manifest and exact reviewed prefix retained'}))
    hashes=json.loads(path.read_text())['files']
    for p,h in hashes.items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('FINAL_RELEASE_CHANGED:'+p)
    audit.update(release_files=len(hashes),release_manifest='results/phase7/provenance/release_hashes_v2.json')
    immutable(ROOT/'results/phase7/provenance/release_verification.json',jb(audit))
    print(json.dumps(audit),flush=True)

if __name__=='__main__':main()
