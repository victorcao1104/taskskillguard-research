"""Bounded, no-network batches of the frozen synthetic recovery machine."""
import argparse
import json
import subprocess
from phase7_common import ROOT,read_rows,sha,jb,rb,immutable,verify_freeze
IMAGE='sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244'
WORKER='''import json,sys,types,os
p=json.load(sys.stdin)
pkg=types.ModuleType("tsg");pkg.__path__=[];sys.modules["tsg"]=pkg
for name,source in p["modules"].items():
 m=types.ModuleType(name);sys.modules[name]=m
 exec(compile(source,name+".py","exec"),m.__dict__)
fun=sys.modules["tsg.recovery_v7"].execute
rows=[dict(j["meta"],result=fun(**j["args"]),runner_status="completed") for j in p["jobs"]]
json.dump({"uid":os.getuid(),"rows":rows},sys.stdout,sort_keys=True)
'''
def command():
    return ['docker','run','--rm','-i','--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','64','--memory','256m','--cpus','1',
            '--user','65534:65534','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
            '--entrypoint','python3',IMAGE,'-I','-B','-c',WORKER]

def run(track):
    verify_freeze(); directory=ROOT/f'results/phase7/{track}'
    jobs=read_rows(directory/'jobs.jsonl');modules={}
    for name in ('runtime_v6','recovery_v7'):
        modules['tsg.'+name]=(ROOT/f'src/tsg/{name}.py').read_text(encoding='utf-8')
    pre=subprocess.run(['docker','image','inspect',IMAGE,'--format','{{.Id}}'],capture_output=True,timeout=20)
    if pre.returncode or pre.stdout.decode().strip()!=IMAGE:raise RuntimeError('PINNED_IMAGE_UNAVAILABLE')
    allrows=[];batches=0
    for start in range(0,len(jobs),500):
        batches+=1;subset=jobs[start:start+500];out=directory/f'container_batches/{batches:03}'
        payload=jb({'modules':modules,'jobs':subset})
        plan={'conditions':len(subset),'image':IMAGE,'command':command(),'payload_sha256':sha(payload),
              'jobs_sha256':sha(rb(subset)),'modules_sha256':{k:sha(v.encode()) for k,v in modules.items()},
              'scope':'fresh in-memory state per condition, shared batch container, no host mounts'}
        immutable(out/'plan.json',jb(plan))
        if (out/'exit.json').exists():
            if json.loads((out/'exit.json').read_text())['exit_code']!=0:raise RuntimeError('PRIOR_FAILURE_NO_RETRY')
            parsed=json.loads((out/'stdout.json').read_text())
        else:
            if (out/'intent.json').exists():raise RuntimeError('ORPHAN_INTENT_NO_RETRY')
            immutable(out/'intent.json',jb({'payload_sha256':sha(payload)}))
            try:
                proc=subprocess.run(command(),input=payload,capture_output=True,timeout=60)
            except (subprocess.TimeoutExpired,OSError) as exc:
                immutable(out/'stdout.json',getattr(exc,'stdout',None) or b'')
                immutable(out/'stderr.txt',getattr(exc,'stderr',None) or b'')
                immutable(out/'exit.json',jb({'exit_code':-1,'failure_type':type(exc).__name__,
                                              'message':str(exc),'automatic_retry':False}))
                raise RuntimeError('CONTAINER_LAUNCH_FAILED_NO_RETRY') from exc
            immutable(out/'stdout.json',proc.stdout);immutable(out/'stderr.txt',proc.stderr)
            immutable(out/'exit.json',jb({'exit_code':proc.returncode}))
            if proc.returncode:raise RuntimeError('CONTAINER_FAILED')
            parsed=json.loads(proc.stdout)
        if parsed['uid']!=65534:raise RuntimeError('UID_MISMATCH')
        allrows.extend(parsed['rows']);print(json.dumps({'track':track,'batch':batches,'completed':len(allrows)}),flush=True)
    immutable(directory/'container_results.jsonl',rb(allrows))
    audit={'conditions':len(allrows),'container_count':batches,'exact_vm_agreement':allrows==read_rows(directory/'vm_results.jsonl'),
           'uid':65534,'image':IMAGE}
    immutable(directory/'container_audit.json',jb(audit));print(json.dumps(audit),flush=True)
    assert audit['exact_vm_agreement']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('track',choices=['recovery','integrated']);run(p.parse_args().track)
