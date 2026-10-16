"""Replay all recorded synthetic policy/runtime conditions in restricted Docker."""
import argparse
import json
import subprocess
from phase11_common import ROOT,sha,jb,rb,immutable,verify_freeze,read_rows,read_chunks,write_chunks

IMAGE='sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244'
MODULE_PATHS=[('tsg.'+n,'src/tsg/'+n+'.py') for n in ('runtime_v6','recovery_v7','observation_v9',
    'recovery_v9','observation_v10','recovery_v10','certificate_v11','commit_v11')]
MODULE_PATHS += [(n,'scripts/'+n+'.py') for n in ('phase6_common','phase10_common','phase11_common','experiment_phase11')]
WORKER='''import json,sys,types,os
p=json.load(sys.stdin)
pkg=types.ModuleType('tsg');pkg.__path__=[];sys.modules['tsg']=pkg
for name in p['module_order']:
 m=types.ModuleType(name);m.__file__='/synthetic/'+name.replace('.','/')+'.py';sys.modules[name]=m
 exec(compile(p['modules'][name],m.__file__,'exec'),m.__dict__)
cert=sys.modules['tsg.certificate_v11'];commit=sys.modules['tsg.commit_v11'];exp=sys.modules['experiment_phase11']
rows=[]
for j in p['jobs']:
 c=p['cases'][j['case_id']];a=j['args'];k=j['kind']
 if k=='semantics':
  prog=sys.modules['tsg.runtime_v6'].parse_source(c['source']) if a['route_index']==0 else c['routes'][a['route_index']-1]
  value={'audit':cert.audit_run(prog,c['worlds'][a['world_index']],c['goal'],32),
         'execution':commit.execute_certified(cert.public_case(c),**a)}
 elif k=='policy':value=exp.policy_record(c,**a)
 elif k=='previous':value=sys.modules['tsg.recovery_v10'].execute(c,**a)
 elif k=='execute':value=commit.execute_certified(cert.public_case(c),**a) if a['route_index'] is not None else None
 else:raise ValueError('UNKNOWN_JOB')
 rows.append({'job_id':j['job_id'],'result':value})
json.dump({'uid':os.getuid(),'rows':rows},sys.stdout,sort_keys=True)
'''

def command():
    return ['docker','run','--rm','-i','--network','none','--read-only','--cap-drop','ALL',
        '--security-opt','no-new-privileges','--pids-limit','64','--memory','256m','--cpus','1',
        '--user','65534:65534','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
        '--entrypoint','python3',IMAGE,'-I','-B','-c',WORKER]

def build(track):
    jobs=[];expected=[]
    names=('semantics','policies','recovery','previous') if track=='deterministic' else ('integrated',)
    for name in names:
        for i,row in enumerate(read_chunks(f'results/phase11/{name}')):
            jid=f'{name}-{i:06}';w=row['world_index'];c=row['case_id']
            if name=='semantics':
                kind='semantics';args={'route_index':row['route'],'world_index':w}
                value={k:row[k] for k in ('audit','execution')}
            elif name=='policies':
                kind='policy';args={'w':w,'policy':row['policy'],'budget':row['budget'],'stop':row['stop']};value=row
            elif name=='previous':
                kind='previous';args={'world_index':w,'planning_budget':512,'observation_budget':2,'quota':32,'observation_mode':'goal'}
                value=row['old_runtime']
            else:
                kind='execute';args={'route_index':row['route'] if name=='recovery' else row['certificate']['route'],
                    'world_index':w,'fault':row['fault'],'policy':row['policy'],'quota':32,
                    'status_budget':row.get('status_budget',1)};value=row['result']
            jobs.append({'job_id':jid,'case_id':c,'kind':kind,'args':args});expected.append({'job_id':jid,'result':value})
    return jobs,expected

def cases():
    return {c['case_id']:c for f in ('heldout.jsonl','challenge.jsonl','scaling.jsonl')
            for c in read_rows(ROOT/'data/phase11'/f)}

def payload(jobs,cs):
    modules={n:(ROOT/path).read_text(encoding='utf-8') for n,path in MODULE_PATHS}
    return jb({'modules':modules,'module_order':[n for n,_ in MODULE_PATHS],'jobs':jobs,
               'cases':{k:cs[k] for k in sorted({j['case_id'] for j in jobs})}})

def run(track):
    verify_freeze();jobs,expected=build(track);cs=cases();directory=ROOT/f'results/phase11/isolation/{track}'
    pre=subprocess.run(['docker','image','inspect',IMAGE,'--format','{{.Id}}'],capture_output=True,timeout=20)
    if pre.returncode or pre.stdout.decode().strip()!=IMAGE:raise RuntimeError('PINNED_IMAGE_UNAVAILABLE')
    write_chunks(directory/'jobs',jobs);rows=[]
    for i,start in enumerate(range(0,len(jobs),250),1):
        subset=jobs[start:start+250];data=payload(subset,cs);out=directory/f'batches/{i:03}'
        immutable(out/'plan.json',jb({'conditions':len(subset),'image':IMAGE,'command':command(),
            'payload_sha256':sha(data),'jobs_sha256':sha(rb(subset)),
            'scope':'fresh memory per condition; shared batch container; no network or host mounts'}))
        if (out/'exit.json').exists():
            if json.loads((out/'exit.json').read_text())['exit_code']!=0:raise RuntimeError('PRIOR_FAILURE_NO_RETRY')
            parsed=json.loads((out/'stdout.json').read_text(encoding='utf-8'))
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
        assert parsed['rows']==expected[start:start+250],'CONTAINER_DIVERGENCE'
        rows.extend(parsed['rows'])
        if i%10==0:print(json.dumps({'track':track,'batches':i,'conditions':len(rows)}),flush=True)
    write_chunks(directory/'results',rows)
    audit={'conditions':len(rows),'containers':(len(jobs)+249)//250,'exact_agreement':rows==expected,
        'null_abstention_results':sum(r['result'] is None for r in rows),'uid':65534,'image':IMAGE}
    immutable(directory/'audit.json',jb(audit));return audit

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('track',choices=['deterministic','integrated']);a=p.parse_args()
    print(json.dumps(run(a.track)),flush=True)
