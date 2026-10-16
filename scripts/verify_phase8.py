"""Offline reproduction of saved requests, truth, effects, statistics and hashes."""
import argparse
import json
import sys
from phase8_common import ROOT,sha,jb,rb,immutable,read_rows,cases,verify_freeze,CAP
sys.path.insert(0,str(ROOT/'src'))


def release_files():
    paths=[]
    for directory in ('data/phase8','results/phase8'):
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file())
    for directory in ('src/tsg','scripts','tests','docs','.github/workflows'):
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file()
                     and ('phase8' in p.name or '_v8' in p.name) and '__pycache__' not in p.parts)
    paths.append(ROOT/'PHASE8.md')
    excluded={'results/phase8/provenance/release_hashes.json','results/phase8/provenance/release_verification.json'}
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(set(paths))
            if p.relative_to(ROOT).as_posix() not in excluded}


def verify():
    baseline=json.loads((ROOT/'results/phase8/provenance/baseline.json').read_text())
    for p,h in baseline['files'].items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('OLD_FILE_CHANGED:'+p)
    production=verify_freeze('production');frozen=verify_freeze()
    from build_phase8_heldout import build_cases,reference_record,coverage_audit,novelty_audit,jsonl_bytes
    new_cases=build_cases();records=[reference_record(c) for c in new_cases]
    assert jsonl_bytes(new_cases)==(ROOT/'data/phase8/heldout.jsonl').read_bytes()
    assert jsonl_bytes(records)==(ROOT/'results/phase8/reference/truth.jsonl').read_bytes()
    normalize=lambda obj:json.loads(json.dumps(obj))
    for name,value in [('coverage',coverage_audit(new_cases,records)),('novelty',novelty_audit(new_cases))]:
        assert normalize(value)==json.loads((ROOT/f'results/phase8/reference/{name}.json').read_text())
    provenance=json.loads((ROOT/'results/phase8/reference/provenance.json').read_text())
    for p,h in provenance['source_sha256'].items():assert sha((ROOT/p).read_bytes())==h
    for name,h in provenance['artifact_sha256'].items():
        p=ROOT/'data/phase8/heldout.jsonl' if name=='heldout.jsonl' else ROOT/f'results/phase8/reference/{name}'
        assert sha(p.read_bytes())==h
    from run_phase8 import prepare,observation
    jobs,manifest,budget=prepare()
    obs=read_rows(ROOT/'results/phase8/api/observations.jsonl');index={r['job_id']:r for r in obs}
    assert len(obs)==480 and len(index)==480 and set(index)=={j['job_id'] for j in jobs}
    cs={c['case_id']:c for c in cases()};rids=[]
    for j in jobs:
        raw=json.loads((ROOT/index[j['job_id']]['raw_ref']).read_text(encoding='utf-8'))
        expected=j['expected_request_hash'];assert raw['request_hash']==expected
        if 'request' in raw:
            assert sha(json.dumps({'request':raw['request'],'replicate':raw['replicate']},sort_keys=True,ensure_ascii=False).encode())==expected
        dispatch=json.loads((ROOT/f'results/phase8/api/dispatch/{j["job_id"]}.json').read_text())
        assert dispatch=={'job_id':j['job_id'],'request_hash':expected}
        assert observation(j,raw,cs[j['case_id']])==index[j['job_id']]
        assert json.loads((ROOT/f'results/phase8/api/jobs/{j["job_id"]}.json').read_text(encoding='utf-8'))==index[j['job_id']]
        if raw.get('reservation_id'):
            rid=raw['reservation_id'];rids.append(rid);entry=budget.entries[rid]
            assert entry['model']==j['model']
            assert entry['reserved_usd']==j['reservation_upper_usd']
            if entry['status']=='settled':
                from tsg.budget_v4 import UPPER_PRICES
                assert entry['usage']==raw['usage']
                ip,op=UPPER_PRICES[j['model']];u=raw['usage']
                assert entry['cost_usd']==(u['input_tokens']*ip+u['output_tokens']*op)/1e6
    old=read_rows(ROOT/'results/phase7/api/budget.jsonl');oldids={r['reservation_id'] for r in old}
    assert len(rids)==len(set(rids)) and set(budget.entries)-oldids==set(rids)
    assert budget.total_cost<=CAP and manifest['reservation_upper_usd']<=4
    from experiment_phase8 import semantics,batch
    semantic=semantics();totals={}
    from container_phase8 import command,IMAGE
    for track in ('recovery','integrated'):
        totals[track]=batch(track)['conditions']
        directory=ROOT/f'results/phase8/{track}'
        vm=read_rows(directory/'vm_results.jsonl');saved=read_rows(directory/'container_results.jsonl')
        assert vm==saved
        combined=[];grid=read_rows(directory/'jobs.jsonl')
        modules={'tsg.'+n:(ROOT/f'src/tsg/{n}.py').read_text(encoding='utf-8') for n in ('runtime_v6','recovery_v7','recovery_v8')}
        for i,start in enumerate(range(0,len(grid),400),1):
            out=directory/f'container_batches/{i:03}';subset=grid[start:start+400]
            plan=json.loads((out/'plan.json').read_text());intent=json.loads((out/'intent.json').read_text())
            assert plan['image']==IMAGE and plan['command']==command()
            assert plan['jobs_sha256']==sha(rb(subset))
            assert plan['payload_sha256']==sha(jb({'modules':modules,'jobs':subset}))==intent['payload_sha256']
            assert json.loads((out/'exit.json').read_text())['exit_code']==0
            result=json.loads((out/'stdout.json').read_text());assert result['uid']==65534
            combined.extend(result['rows'])
        assert combined==vm
        audit=json.loads((directory/'container_audit.json').read_text())
        assert audit=={'conditions':len(vm),'containers':(len(grid)+399)//400,
                       'exact_vm_agreement':True,'uid':65534,'image':IMAGE}
        for r in vm:
            v=r['result']
            assert v['unauthorized_effects']==v['duplicate_effects']==0
            assert v['charged_calls']<=r['quota'] and v['attempts']<=4
    from analyze_phase8 import analyze
    analyze()
    from diagnose_phase8_v2 import main as diagnose
    diagnose()
    return {'status':'pass','baseline_files_unchanged':len(baseline['files']),
            'production_frozen_files':len(production['files']),'data_frozen_files':len(frozen['files']),
            'model_conditions':len(obs),'unique_requests':len({r['request_hash'] for r in obs}),
            'new_reservations':len(rids),'semantic_comparisons':semantic['comparisons'],
            'executions':totals,'cumulative_upper_usd':budget.total_cost,'remaining_usd':CAP-budget.total_cost}


def main():
    p=argparse.ArgumentParser();p.add_argument('--freeze-release',action='store_true');a=p.parse_args()
    result=verify();path=ROOT/'results/phase8/provenance/release_hashes.json'
    if a.freeze_release:
        hashes=release_files();immutable(path,jb({'files':hashes,'count':len(hashes)}))
    hashes=json.loads(path.read_text())['files']
    assert release_files()==hashes
    result['release_files']=len(hashes)
    immutable(ROOT/'results/phase8/provenance/release_verification.json',jb(result))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
