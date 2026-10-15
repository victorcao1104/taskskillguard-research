"""Same frozen campaign, with progress reads protected by the budget lock."""
import argparse
import json
from pathlib import Path
from run_phase7_v2 import amendment
from experiment_phase7_v2 import semantics
from run_phase7 import prepare,execute
from tsg.budget_v7_locked import BudgetV7Locked

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--env-file',type=Path);a=p.parse_args()
    amendment();semantics()
    jobs,manifest,previous=prepare()
    budget=BudgetV7Locked(previous.path,previous.limit)
    print(json.dumps(manifest),flush=True)
    if a.execute:
        if not a.env_file or not a.env_file.is_file():raise ValueError('AUTHORIZED_CONFIG_REQUIRED')
        execute(jobs,budget,a.env_file)
