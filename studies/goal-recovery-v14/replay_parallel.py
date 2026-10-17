"""Fresh cached-only replay of completed episodes; no budget or credential access."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
from gr14.campaign import STUDY,grid,episode,save_result,source_hashes
from gr14.provider import decode

class Cached:
    def call(self,job):
        saved=json.loads((STUDY/'api/requests'/f"{job['job_id']}.json").read_text(encoding='utf-8'))
        if saved!=job:raise ValueError('REQUEST_REPLAY_MISMATCH')
        raw=json.loads((STUDY/'api/raw'/f"{job['expected_request_hash']}.json").read_text(encoding='utf-8'))
        if raw['request_hash']!=job['expected_request_hash']:raise ValueError('RAW_REPLAY_MISMATCH')
        return decode(raw)

def family_job(args):
    family,campaign,out=args;out=Path(out);n=0
    for c,m,model,r in grid(campaign):
        if c['family']!=family:continue
        name=f"{c['case_id']}--{m}--{model}--r{r}.json"
        if not (STUDY/'results'/campaign/name).exists() or (out/name).exists():continue
        result=episode(c,m,model,r,campaign,Cached());save_result(out/name,result);n+=1
    return {'family':family,'replayed_now':n}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('campaign',choices=['main','combined']);p.add_argument('--out',required=True);a=p.parse_args()
    freeze=json.loads((STUDY/'provenance'/f'{a.campaign}_freeze.json').read_text())
    if freeze['source_hashes']!=source_hashes():raise ValueError('FROZEN_SOURCE_CHANGED')
    families=sorted({c['family'] for c,_,_,_ in grid(a.campaign)})
    with ProcessPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(family_job,(family,a.campaign,a.out)) for family in families]
        for f in as_completed(futures):print(json.dumps(f.result()),flush=True)
