"""Offline release verification: provenance, evidence, spending and full replay."""
import argparse
import json
import sys
from phase10_common import ROOT,CAP,sha,jb,rb,immutable,read_rows,read_chunks,cases,verify_freeze
sys.path.insert(0,str(ROOT/'src'))


def release_files():
    paths=set()
    for directory in ('data/phase10','results/phase10'):
        paths.update(p for p in (ROOT/directory).rglob('*') if p.is_file())
    for directory in ('src/tsg','scripts','tests','docs','.github/workflows'):
        paths.update(p for p in (ROOT/directory).rglob('*') if p.is_file()
                     and ('phase10' in p.name or '_v10' in p.name) and '__pycache__' not in p.parts)
    paths.add(ROOT/'PHASE10.md')
    excluded={'results/phase10/provenance/release_hashes.json','results/phase10/provenance/release_verification.json'}
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(paths)
            if p.relative_to(ROOT).as_posix() not in excluded}


def verify():
    baseline=json.loads((ROOT/'results/phase10/provenance/baseline.json').read_text(encoding='utf-8'))
    for i,(name,digest) in enumerate(baseline['files'].items(),1):
        assert sha((ROOT/name).read_bytes())==digest,'OLD_FILE_CHANGED:'+name
        if i%4000==0:print(json.dumps({'old_files_verified':i}),flush=True)
    production,data=verify_freeze('production'),verify_freeze()
    from build_phase10_heldout import build_cases,reference_record,jsonl_bytes,coverage_audit,novelty_audit
    new=build_cases();refs=[reference_record(c) for c in new]
    artifacts={'heldout.jsonl':jsonl_bytes(new),'truth.jsonl':jsonl_bytes(refs),
        'coverage.json':jb(coverage_audit(new,refs)),'novelty.json':jb(novelty_audit(new))}
    provenance=json.loads((ROOT/'results/phase10/reference/provenance.json').read_text(encoding='utf-8'))
    assert len(new)==24 and len({c['family'] for c in new})==12
    for name,content in artifacts.items():
        path=ROOT/('data/phase10/heldout.jsonl' if name=='heldout.jsonl' else 'results/phase10/reference/'+name)
        assert path.read_bytes()==content==(ROOT/'results/phase10/reference/first-pass'/name).read_bytes()
        assert sha(content)==provenance['artifact_sha256'][name]
    assert (ROOT/'results/phase10/reference/provenance.json').read_bytes()==(ROOT/'results/phase10/reference/first-pass/provenance.json').read_bytes()
    for path,digest in provenance['source_sha256'].items():assert sha((ROOT/path).read_bytes())==digest
    print(json.dumps({'reference_reproduced':True}),flush=True)
    from run_phase10 import prepare,acquire_stream,finalize,request_cost
    streams,manifest,budget=prepare();cs={c['case_id']:c for c in cases()};api=ROOT/'results/phase10/api'
    observations=read_rows(api/'observations.jsonl');saved={r['stream_id']:r for r in observations}
    assert len(observations)==len(saved)==len(streams)==288
    request_ids=[];reservations=[]
    for i,spec in enumerate(streams,1):
        replay=acquire_stream(spec,cs[spec['case_id']],api,None)
        assert replay==saved[spec['stream_id']]
        for d in replay['decisions']:
            job=json.loads((api/'requests'/f'{d["job_id"]}.json').read_text(encoding='utf-8'))
            raw=json.loads((ROOT/d['raw_ref']).read_text(encoding='utf-8'))
            assert raw['request_hash']==job['expected_request_hash']==d['request_hash']
            if 'request' in raw:
                assert sha(json.dumps({'request':raw['request'],'replicate':raw['replicate']},sort_keys=True,ensure_ascii=False).encode())==d['request_hash']
            assert json.loads((api/'dispatch'/f'{d["job_id"]}.json').read_text(encoding='utf-8'))=={'job_id':d['job_id'],'request_hash':d['request_hash']}
            assert request_cost(raw,job)==(d['cost_upper_usd'],d['cost_basis'])
            request_ids.append(d['request_hash'])
            if raw.get('reservation_id'):
                rid=raw['reservation_id'];reservations.append(rid);entry=budget.entries[rid]
                assert entry['model']==job['model'] and entry['reserved_usd']==job['reservation_upper_usd']
                if entry['status']=='settled':assert entry['usage']==raw['usage'] and entry['cost_usd']==d['cost_upper_usd']
        if i%48==0:print(json.dumps({'streams_reproduced':i}),flush=True)
    assert len(request_ids)==len(set(request_ids))
    assert len(reservations)==len(set(reservations))
    oldids={r['reservation_id'] for r in read_rows(ROOT/'results/phase9/api/budget.jsonl')}
    assert set(budget.entries)-oldids==set(reservations)
    assert budget.total_cost<=budget.limit<=CAP
    api_summary=finalize(streams,budget)
    from experiment_phase10 import semantics,query_scenarios,batch
    semantic,query=semantics(),query_scenarios()
    from container_phase10 import command,payload,IMAGE
    totals={}
    for track in ('interface','recovery','integrated'):
        totals[track]=batch(track)['conditions'];directory=ROOT/f'results/phase10/{track}'
        jobs=read_chunks(directory/'jobs');vm=read_chunks(directory/'vm_results')
        assert vm==read_chunks(directory/'container_results')
        combined=[]
        for i,start in enumerate(range(0,len(jobs),250),1):
            subset=jobs[start:start+250];out=directory/f'container_batches/{i:03}'
            plan=json.loads((out/'plan.json').read_text(encoding='utf-8'));intent=json.loads((out/'intent.json').read_text(encoding='utf-8'))
            assert plan['command']==command() and plan['image']==IMAGE
            assert plan['jobs_sha256']==sha(rb(subset))
            assert plan['payload_sha256']==intent['payload_sha256']==sha(payload(subset))
            assert json.loads((out/'exit.json').read_text(encoding='utf-8'))['exit_code']==0
            result=json.loads((out/'stdout.json').read_text(encoding='utf-8'));assert result['uid']==65534;combined.extend(result['rows'])
        assert combined==vm
        assert json.loads((directory/'container_audit.json').read_text(encoding='utf-8'))=={
            'conditions':len(vm),'containers':(len(vm)+249)//250,'exact_vm_agreement':True,'uid':65534,'image':IMAGE}
        print(json.dumps({'track_reproduced':track,'conditions':len(vm)}),flush=True)
    from analyze_phase10 import main as analyze
    analyze([])
    return {'status':'pass','baseline_files_unchanged':len(baseline['files']),
        'production_frozen_files':len(production['files']),'data_frozen_files':len(data['files']),
        'streams':len(streams),'unique_requests':len(request_ids),'new_reservations':len(reservations),
        'semantic_comparisons':semantic['comparisons'],'query_conditions':query['conditions'],
        'executions':totals,'cumulative_upper_usd':budget.total_cost,'remaining_usd':CAP-budget.total_cost}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--release',action='store_true');a=p.parse_args()
    value=verify();hashes=release_files();value['release_files']=len(hashes)
    if a.release:
        immutable(ROOT/'results/phase10/provenance/release_hashes.json',jb(hashes))
        immutable(ROOT/'results/phase10/provenance/release_verification.json',jb(value))
    else:
        assert hashes==json.loads((ROOT/'results/phase10/provenance/release_hashes.json').read_text(encoding='utf-8'))
        assert value==json.loads((ROOT/'results/phase10/provenance/release_verification.json').read_text(encoding='utf-8'))
    print(json.dumps(value),flush=True)
