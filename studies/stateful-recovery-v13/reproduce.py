"""Fresh-output, identity-checked, zero-API reproduction of reported v13 trials."""
from pathlib import Path
import argparse,hashlib,json,subprocess
from run import D,ROOT,assert_frozen,model_run,offline
from sr13.io import read,save,semantic,digest
from sr13.campaign import request_job
from corrected_run import rerun,adaptive,offline_corrected
from robust_run import run as robust_run
from stress_inputs import run as stress_run
from adaptive_network_rerun import run as adaptive_network_run
from typed_roles import run as typed_run


def audit_cache():
    seen=set();statuses={}
    for path in sorted((D/'api/requests').glob('*.json')):
        j=read(path);h=j['expected_request_hash']
        if h in seen:raise ValueError('DUPLICATE_REQUEST_IDENTITY')
        seen.add(h);raw=read(D/'api/raw'/f'{h}.json');marker=read(D/'api/dispatch'/path.name)
        if raw['request_hash']!=h or marker['request_hash']!=h:raise ValueError('RAW_IDENTITY_MISMATCH')
        if 'request' in raw:
            actual=hashlib.sha256(json.dumps({'request':raw['request'],'replicate':raw['replicate']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if actual!=h or raw['tag']!=j['identity'] or raw['replicate']!=j['replicate']:raise ValueError('RAW_BODY_MISMATCH')
        elif raw.get('status')!='interrupted_unknown':raise ValueError('RAW_REQUEST_MISSING')
        statuses[raw['status']]=statuses.get(raw['status'],0)+1
    return {'distinct_requests':len(seen),'statuses':statuses,'identity_checks':True}


def normalized(r,offline_v1=False):
    r=semantic(r)
    if isinstance(r,dict):return {k:normalized(v,offline_v1) for k,v in r.items() if not(offline_v1 and k=='repeated_successful_effects')}
    if isinstance(r,list):return [normalized(v,offline_v1) for v in r]
    return r


def compare(original,replayed,*,offline_v1=False):
    paths=sorted(original.glob('*--*.json'));names={p.name for p in paths}
    replay_names={p.name for p in replayed.glob('*--*.json')}
    mismatches=sorted(names^replay_names)
    if not names:mismatches.append('EMPTY_ORIGINAL_CAMPAIGN')
    for p in paths:
        q=replayed/p.name
        if not q.exists() or normalized(read(p),offline_v1)!=normalized(read(q),offline_v1):mismatches.append(p.name)
        else:
            r=read(p)
            for folder in (original,replayed):
                if digest((folder/r['trace_file']).read_bytes())!=r['trace_sha256']:raise ValueError('TRACE_HASH_MISMATCH')
    return {'compared':len(paths),'replayed':len(replay_names),'mismatches':sorted(set(mismatches)),
            'trace_hashes_checked':2*sum(p.name not in mismatches for p in paths)}


def preserve_old():
    baseline=read(D/'provenance/baseline_git_objects.json');now={}
    for line in subprocess.check_output(['git','ls-tree','-r','HEAD'],cwd=ROOT).decode().splitlines():
        metadata,path=line.split('\t',1);mode,kind,blob=metadata.split();now[path]={'mode':mode,'git_blob':blob}
    changed=[p for p,v in baseline['files'].items() if now.get(p)!=v]
    working=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT).decode().splitlines()
    changed+=sorted(set(working)&set(baseline['files']))
    return {'base_commit':baseline['base_commit'],'old_git_objects':baseline['file_count'],'changed_old_paths':sorted(set(changed))}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('FRESH_OUTPUT_DIRECTORY_REQUIRED')
    assert_frozen();cache=audit_cache();ledger_before=(D/'api/budget.jsonl').read_bytes()
    a.output.mkdir(parents=True)
    offline(a.output/'offline')
    model_run(None,cached=True,output=a.output/'main')
    model_run(None,cached=True,output=a.output/'adaptive',cases_override=read(D/'data/adaptive_search.json')['selected'])
    model_run(None,cached=True,development=True,output=a.output/'development_v2')
    rerun(cached=True,output=a.output/'state_amendment')
    adaptive(cached=True,output=a.output/'adaptive_corrected')
    offline_corrected(a.output/'offline_corrected')
    robust_run(cached=True,output=a.output/'robust_protocol')
    robust_run(cached=True,output=a.output/'robust_adaptive',adaptive=True)
    adaptive_network_run(cached=True,output=a.output/'adaptive_net')
    typed_run(cached=True,output=a.output/'typed_roles')
    stress_run(a.output/'stress_inputs')
    comparison={name:compare(D/'results'/name,a.output/name,offline_v1=name=='offline')
                for name in ('offline','main','adaptive','development_v2')}
    comparison['state_amendment']=compare(D/'results/state_amendment',a.output/'state_amendment')
    comparison['offline_corrected']=compare(D/'results/offline_corrected',a.output/'offline_corrected')
    comparison['adaptive_corrected']=compare(D/'results/adaptive',a.output/'adaptive_corrected')
    comparison['robust_protocol']=compare(D/'results/robust_protocol',a.output/'robust_protocol')
    comparison['robust_adaptive']=compare(D/'results/robust_adaptive',a.output/'robust_adaptive')
    comparison['robust_adaptive_network']=compare(D/'results/adaptive_net',a.output/'adaptive_net')
    comparison['typed_roles']=compare(D/'results/typed_roles',a.output/'typed_roles')
    comparison['stress_inputs']=compare(D/'results/stress_inputs',a.output/'stress_inputs')
    ledger_unchanged=(D/'api/budget.jsonl').read_bytes()==ledger_before
    old=preserve_old()
    result={'cache':cache,'comparison':comparison,'budget_ledger_unchanged':ledger_unchanged,
            'old_preservation':old,'network_calls':0,
            'scope':'Fresh replay of original offline (ignoring only added duplicate diagnostic), strict main/adaptive/development v2, corrected state/offline, normalized main/adaptive, 64-seed stress. Pilot v1 retained, not replayed under amended protocol.'}
    save(a.output/'verification.json',result)
    if any(c['mismatches'] for c in comparison.values()) or not ledger_unchanged or old['changed_old_paths']:raise ValueError('REPRODUCTION_FAILED')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
