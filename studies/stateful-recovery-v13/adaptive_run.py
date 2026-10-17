"""Fixed-budget post-freeze adversary and matched defender evaluation."""
import argparse
from run import D,assert_frozen,model_run
from sr13.adaptive import search
from sr13.io import save,read

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--env-file');p.add_argument('--cached',action='store_true');p.add_argument('--output');a=p.parse_args()
    assert_frozen();path=D/'data/adaptive_search.json'
    if not path.exists():save(path,search())
    evidence=read(path)
    model_run(a.env_file,cached=a.cached,output=a.output,cases_override=evidence['selected'])
