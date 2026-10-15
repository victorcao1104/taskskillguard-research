"""Same frozen 480 jobs, gated on corrected site-coverage validation."""
import argparse
import json
from pathlib import Path
from phase7_common import ROOT,sha,jb,immutable,verify_freeze

PATHS=('scripts/experiment_phase7_v2.py','scripts/run_phase7_v2.py','scripts/verify_phase7_v2.py','scripts/container_phase7_v2.py',
       'tests/test_phase7_amendment.py','docs/phase7_amendment.md')
def amendment(freeze=False):
    verify_freeze()
    obj={'initial_freeze_sha256':sha((ROOT/'results/phase7/provenance/freeze.json').read_bytes()),
         'reason':'candidate order is not coverage; content and uniqueness remain mandatory',
         'model_calls_before_amendment':0,'files':{p:sha((ROOT/p).read_bytes()) for p in PATHS}}
    path=ROOT/'results/phase7/provenance/freeze_amendment.json'
    if freeze:immutable(path,jb(obj))
    if json.loads(path.read_text())!=obj:raise ValueError('AMENDMENT_CHANGED')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze-amendment',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--env-file',type=Path);a=p.parse_args()
    amendment(a.freeze_amendment)
    from experiment_phase7_v2 import semantics
    semantics()
    from run_phase7 import prepare,execute
    jobs,manifest,budget=prepare();print(json.dumps(manifest),flush=True)
    if a.execute:
        if not a.env_file or not a.env_file.is_file():raise ValueError('AUTHORIZED_CONFIG_REQUIRED')
        execute(jobs,budget,a.env_file)
