"""Phase 7 serialization, immutable data and prospective freeze."""
from phase6_common import ROOT, sha, jb, rb, immutable, read_rows
import json

def cases():
    old = [c for p in ('dev','heldout','challenge') for c in read_rows(ROOT/f'data/phase6/{p}.jsonl')]
    return [{**c, 'split': 'regression'} for c in old] + read_rows(ROOT/'data/phase7/heldout.jsonl')

def freeze():
    paths = [p for pattern in ('src/tsg/*v7.py','scripts/*phase7*.py','tests/test_phase7*.py','data/phase7/*',
                               'docs/phase7_design.md','docs/superpowers/plans/*phase7*.md') for p in ROOT.glob(pattern) if p.is_file()]
    record = {'baseline': 'aac66f057408dafeca817e1dc059ff47b7027954',
              'registration': 'local prospective freeze, not external preregistration',
              'source_sha256': {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(set(paths))},
              'holdout_access': 'generator author did not read new production/protocol; production authors did not read heldout before freeze'}
    immutable(ROOT/'results/phase7/provenance/freeze.json', jb(record))
    return record

def verify_freeze():
    record = json.loads((ROOT/'results/phase7/provenance/freeze.json').read_text())
    for p, h in record['source_sha256'].items():
        if sha((ROOT/p).read_bytes()) != h:
            raise ValueError('FROZEN_SOURCE_CHANGED:' + p)
    return record

if __name__ == '__main__':
    print(json.dumps({'frozen_files': len(freeze()['source_sha256'])}))
