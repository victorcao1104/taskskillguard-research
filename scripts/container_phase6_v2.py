"""Explicit-entrypoint launch amendment; preserves the first failed launch."""
import argparse
import json
import subprocess
from phase6_common import ROOT,read_rows,sha,jb,rb,immutable
from experiment_phase6 import IMAGE

WORKER='''import json,sys,types,os
p=json.load(sys.stdin)
pkg=types.ModuleType("tsg");pkg.__path__=[];sys.modules["tsg"]=pkg
for name,source in p["modules"].items():
    m=types.ModuleType(name);sys.modules[name]=m
    exec(compile(source,name+".py","exec"),m.__dict__)
runtime=sys.modules["tsg.runtime_v6"]
rows=[]
for j in p["jobs"]:
    try:
        fun=(sys.modules["tsg.selection_v6"].execute_selection if j["args"]["mode"] in ("first_feasible","search_equal") else runtime.execute)
        rows.append({**j["meta"],"result":fun(**j["args"]),"runner_status":"completed"})
    except Exception as e:
        rows.append({**j["meta"],"runner_status":"error","exception":type(e).__name__+": "+str(e)})
json.dump({"uid":os.getuid(),"rows":rows},sys.stdout,sort_keys=True)
'''


def command():
    return ['docker','run','--rm','-i','--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','64','--memory','256m','--cpus','1',
            '--user','65534:65534','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
            '--entrypoint','python3',IMAGE,'-I','-B','-c',WORKER]


def run(directory):
    directory=ROOT/directory
    resultpath=directory/'container_results.jsonl'
    if resultpath.exists():
        print(json.dumps({'preserved_conditions':len(read_rows(resultpath))}));return
    out=directory/'container_v2';jobs=read_rows(directory/'jobs.jsonl')
    modules={'tsg.runtime_v6':(ROOT/'src/tsg/runtime_v6.py').read_text(encoding='utf-8')}
    if any(j['args']['mode'] in ('first_feasible','search_equal') for j in jobs):
        modules['tsg.selection_v6']=(ROOT/'src/tsg/selection_v6.py').read_text(encoding='utf-8')
    payload=jb({'modules':modules,'jobs':jobs})
    pre=subprocess.run(['docker','image','inspect',IMAGE,'--format','{{.Id}}'],capture_output=True,timeout=20)
    immutable(out/'image_inspect.json',jb({'exit_code':pre.returncode,'stdout':pre.stdout.decode().strip(),'stderr':pre.stderr.decode(errors='replace')}))
    if pre.returncode or pre.stdout.decode().strip()!=IMAGE:raise RuntimeError('IMAGE_NOT_AVAILABLE')
    plan={'conditions':len(jobs),'container_count':1,'image':IMAGE,'args':command(),
          'payload_sha256':sha(payload),'jobs_sha256':sha(rb(jobs)),
          'modules_sha256':{n:sha(s.encode()) for n,s in modules.items()},
          'amendment':'override inherited image ENTRYPOINT; same frozen runtime and jobs, no host mounts/network'}
    immutable(out/'plan.json',jb(plan))
    marker=out/'intent.json'
    if marker.exists():raise RuntimeError('PREVIOUS_ATTEMPT_NO_AUTO_RETRY')
    immutable(marker,jb({'payload_sha256':sha(payload)}))
    proc=subprocess.run(command(),input=payload,capture_output=True,timeout=180)
    immutable(out/'stdout.json',proc.stdout);immutable(out/'stderr.txt',proc.stderr)
    immutable(out/'exit.json',jb({'exit_code':proc.returncode}))
    if proc.returncode:raise RuntimeError('CONTAINER_V2_FAILED')
    parsed=json.loads(proc.stdout)
    if parsed['uid']!=65534:raise RuntimeError('UID_MISMATCH')
    rows=parsed['rows'];immutable(resultpath,rb(rows))
    vm=read_rows(directory/'vm_results.jsonl')
    audit={'conditions':len(rows),'container_count':1,'uid':parsed['uid'],'exact_vm_agreement':rows==vm,
           'runner_errors':sum(r['runner_status']!='completed' for r in rows)}
    immutable(directory/'container_audit.json',jb(audit));print(json.dumps(audit))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',choices=['results/phase6/recovery','results/phase6/integrated',
                              'results/phase6/challenge/recovery','results/phase6/challenge/integrated'])
    run(p.parse_args().directory)
