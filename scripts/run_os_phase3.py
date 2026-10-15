"""Third-round actual OS observations with the same pinned finite adapter image."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.experiment_v3 import read_rows, write_rows, save_json, verify_freeze
from run_os_e2e_phase2 import execute, FROZEN_IMAGE, ContainerSandbox


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=3)
    args = parser.parse_args()
    out = ROOT/'results/phase3/os'
    frozen = json.loads((ROOT/'results/phase3/provenance/formal_freeze.json').read_text(encoding='utf-8'))
    if verify_freeze(ROOT,frozen):
        raise ValueError('FORMAL_INPUTS_CHANGED')
    image = ContainerSandbox(image=FROZEN_IMAGE).command('image','inspect',FROZEN_IMAGE,'--format','{{.Id}}')
    if image.returncode or image.stdout.decode().strip() != FROZEN_IMAGE:
        raise ValueError('FROZEN_IMAGE_UNAVAILABLE')
    cases = json.loads((ROOT/'results/phase2/os_e2e/frozen_tasks.json').read_text(encoding='utf-8'))
    contracts = read_rows(ROOT/'results/phase3/api/os_contracts.jsonl')
    if len(contracts)!=48:
        raise ValueError('OS_CONTRACT_GRID_INCOMPLETE')
    jobs = []
    for case in cases:
        for guard in (False,True):
            for rep in (0,1):
                jobs.append((case,'oracle_correct_policy',None,{},guard,rep,out))
                for row in contracts:
                    if row['case_id']==case['case_id']:
                        # A failed/uncertain contract still runs fail-closed; it is not scored as known success.
                        copied = dict(row)
                        if not isinstance(copied.get('prediction'),dict):
                            copied['prediction']={'rules':[],'unknowns':[]}
                        jobs.append((case,'LLM_generated_mixed' if row['mixed'] else 'LLM_generated_separated',
                                     row['model'],copied,guard,rep,out))
    save_json(out/'manifest.json',{'expected_runs':len(jobs),'image_id':FROZEN_IMAGE,
        'tasks_origin':'unchanged phase2 frozen tasks; prospective new model contracts',
        'source_execution':False,'scope':'finite tool adapters, not arbitrary source mediation'})
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(execute,*job,image=FROZEN_IMAGE):job[3] for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            contract = futures[future]
            row['contract_declared_unknowns'] = (contract.get('prediction') or {}).get('unknowns',[])
            row['contract_decided'] = (row['origin']=='oracle_correct_policy' or
                                       row['contract_status']=='valid' and not row['contract_declared_unknowns'])
            records.append(row)
            write_rows(out/'runs.jsonl',records)
            if len(records)%12==0:
                print(json.dumps({'os_runs':len(records),'planned':len(jobs)}),flush=True)


if __name__=='__main__':
    main()
