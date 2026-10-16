"""Pinned restricted runtime replay; evidence before launch, no implicit retry."""
import argparse
import json
import subprocess
from phase10_common import ROOT,sha,jb,rb,immutable,verify_freeze,read_chunks,write_chunks

IMAGE='sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244'
MODULES=('runtime_v6','recovery_v7','observation_v9','recovery_v9','observation_v10','recovery_v10')
WORKER='''import json,sys,types,os
p=json.load(sys.stdin)
pkg=types.ModuleType("tsg");pkg.__path__=[];sys.modules["tsg"]=pkg
for name in p["module_order"]:
 m=types.ModuleType(name);sys.modules[name]=m
 exec(compile(p["modules"][name],name+".py","exec"),m.__dict__)
rows=[]
for j in p["jobs"]:
 fun=sys.modules["tsg.recovery_"+j["engine"]].execute
 rows.append(dict(j["meta"],result=fun(**j["args"]),runner_status="completed"))
json.dump({"uid":os.getuid(),"rows":rows},sys.stdout,sort_keys=True)
'''


def command():
    return ['docker','run','--rm','-i','--network','none','--read-only','--cap-drop','ALL',
        '--security-opt','no-new-privileges','--pids-limit','64','--memory','256m','--cpus','1',
        '--user','65534:65534','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
        '--entrypoint','python3',IMAGE,'-I','-B','-c',WORKER]


def payload(jobs):
    modules={'tsg.'+n:(ROOT/f'src/tsg/{n}.py').read_text(encoding='utf-8') for n in MODULES}
    return jb({'modules':modules,'module_order':['tsg.'+n for n in MODULES],'jobs':jobs})


def run(track):
    verify_freeze();directory=ROOT/f'results/phase10/{track}';jobs=read_chunks(directory/'jobs')
    pre=subprocess.run(['docker','image','inspect',IMAGE,'--format','{{.Id}}'],capture_output=True,timeout=20)
    if pre.returncode or pre.stdout.decode().strip()!=IMAGE:raise RuntimeError('PINNED_IMAGE_UNAVAILABLE')
    rows=[];batches=0
    for start in range(0,len(jobs),250):
        batches+=1;subset=jobs[start:start+250];out=directory/f'container_batches/{batches:03}'
        data=payload(subset)
        immutable(out/'plan.json',jb({'conditions':len(subset),'image':IMAGE,'command':command(),
            'payload_sha256':sha(data),'jobs_sha256':sha(rb(subset)),
            'scope':'fresh memory per condition; shared batch container; no network or host mounts'}))
        if (out/'exit.json').exists():
            if json.loads((out/'exit.json').read_text())['exit_code']!=0:raise RuntimeError('PRIOR_FAILURE_NO_RETRY')
            parsed=json.loads((out/'stdout.json').read_text())
        else:
            if (out/'intent.json').exists():raise RuntimeError('ORPHAN_INTENT_NO_RETRY')
            immutable(out/'intent.json',jb({'payload_sha256':sha(data)}))
            try:proc=subprocess.run(command(),input=data,capture_output=True,timeout=60)
            except (subprocess.TimeoutExpired,OSError) as exc:
                immutable(out/'stdout.json',getattr(exc,'stdout',None) or b'')
                immutable(out/'stderr.txt',getattr(exc,'stderr',None) or b'')
                immutable(out/'exit.json',jb({'exit_code':-1,'type':type(exc).__name__,'automatic_retry':False}))
                raise RuntimeError('LAUNCH_FAILED_NO_RETRY') from exc
            immutable(out/'stdout.json',proc.stdout);immutable(out/'stderr.txt',proc.stderr)
            immutable(out/'exit.json',jb({'exit_code':proc.returncode}))
            if proc.returncode:raise RuntimeError('CONTAINER_FAILED')
            parsed=json.loads(proc.stdout)
        assert parsed['uid']==65534
        rows.extend(parsed['rows']);print(json.dumps({'track':track,'batch':batches,'completed':len(rows)}),flush=True)
    write_chunks(directory/'container_results',rows)
    audit={'conditions':len(rows),'containers':batches,'exact_vm_agreement':rows==read_chunks(directory/'vm_results'),
           'uid':65534,'image':IMAGE}
    immutable(directory/'container_audit.json',jb(audit));assert audit['exact_vm_agreement']
    print(json.dumps(audit),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('track',choices=['interface','recovery','integrated']);run(p.parse_args().track)
