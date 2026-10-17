"""Replay the trusted finite gateway in restricted containers, never package code."""
import json,subprocess,time
from adapter import compile_bundle,compile_script
from experiment import D,read,save,digest,scenario
from runtime import MODES,FAULTS

IMAGE='sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244'
BOOT=r'''
import sys,json,hashlib
p=json.load(sys.stdin)
originals=p['originals'];scripts=p['scripts']
class Unsupported(ValueError):pass
def compile_bundle(files):return originals[json.dumps(files,sort_keys=True)]
def compile_script(source,file):return scripts[file+'\n'+source]
code=p['runtime'].replace('from adapter import compile_bundle, compile_script, Unsupported','')
# This is the trusted, hash-recorded experiment interpreter, not package source.
exec(compile(code,'trusted-runtime.py','exec'),globals())
rows=[]
for c in p['cases']:
 for fault in FAULTS:
  for mode in MODES:
   rows.append({'case_id':c['case_id'],'family':c['family'],'variant':c['variant'],'grid':p['grid'],'mode':mode,'fault':fault,**execute(c,mode,fault)})
data=(json.dumps(rows,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
print(json.dumps({'conditions':len(rows),'sha256':hashlib.sha256(data).hexdigest(),'uid':__import__('os').getuid()}))
'''
def main():
    cases=read('data/cases.json');grids=read('data/specification.json')['grid'];expected=read('results/deterministic.json')
    originals={json.dumps(c['bundle'],sort_keys=True):compile_bundle(c['bundle']) for c in cases};scripts={}
    for c in cases:
        for i,r in enumerate(c['trusted_routes'],1):
            file=f'trusted/{i}.py';scripts[file+'\n'+r['source']]=compile_script(r['source'],file)
    runtime=(D/'runtime.py').read_text(encoding='utf-8');records=[]
    flags=['--rm','-i','--entrypoint','python','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
           '--pids-limit','64','--memory','256m','--cpus','1','--user','65534:65534']
    for grid in grids:
        payload={'cases':[scenario(c,grid) for c in cases],'originals':originals,'scripts':scripts,
                 'runtime':runtime,'grid':grid['grid_id']}
        started=time.monotonic()
        completed=subprocess.run(['docker','run',*flags,IMAGE,'-B','-c',BOOT],input=json.dumps(payload)+'\n',
                                 text=True,capture_output=True,timeout=90)
        want=[r for r in expected if r['grid']==grid['grid_id']]
        expected_hash=digest((json.dumps(want,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
        row={'grid':grid['grid_id'],'returncode':completed.returncode,'elapsed_seconds':time.monotonic()-started,
             'stderr':completed.stderr,'expected_sha256':expected_hash}
        if completed.returncode==0:row.update(json.loads(completed.stdout));row['equal']=row['sha256']==expected_hash
        else:row.update(equal=False,stdout=completed.stdout)
        records.append(row);print(json.dumps(row),flush=True)
    save(D/'results/container_replay.json',{'image':IMAGE,'flags':flags,'host_mounts':[],
      'runtime_sha256':digest((D/'runtime.py').read_bytes()),'boot_sha256':digest(BOOT.encode()),
      'scope':'Compiled finite programs replayed; source adapter runs on host without native source execution. No real filesystem/network tool tested.',
      'containers':records,'all_equal':all(r['equal'] for r in records)})
    if not all(r['equal'] for r in records):raise SystemExit(1)
if __name__=='__main__':main()
