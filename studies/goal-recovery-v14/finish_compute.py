"""Wait for complete acquired grids, then finish offline audits without API calls."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
import sys
import time

def command(name,args):
    log=Path('../../work')/('v14-'+name+'.log');log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('w',encoding='utf-8') as f:
        result=subprocess.run([sys.executable,*args],stdout=f,stderr=subprocess.STDOUT)
    print(json.dumps({'job':name,'exit_code':result.returncode,'log':str(log)}),flush=True)
    if result.returncode:raise RuntimeError(name+' failed; inspect preserved log')

if __name__=='__main__':
    deadline=time.monotonic()+7200
    while len(list(Path('results/main').glob('*.json')))<864 or len(list(Path('results/combined').glob('*.json')))<144:
        if time.monotonic()>deadline:raise SystemExit('ACQUISITION_INCOMPLETE')
        time.sleep(10)
    print('Both acquired grids complete. Finishing cached-only replay.',flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(command,'replay-'+campaign,['replay_parallel.py',campaign,'--out','../../work/v14-'+campaign+'-fresh']) for campaign in ('main','combined')]
        for f in futures:f.result()
    command('stress-final',['stress_parallel.py'])
    command('analysis',['analyze.py'])
    command('audit',['audit_release.py'])
    command('figures',['figures.py'])
    print('Offline computation complete; reports and publication still require review.',flush=True)
