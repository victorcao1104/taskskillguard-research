"""Offline reproduction from committed sources/cases/cached answers; no API access."""
import argparse,json,platform
from pathlib import Path
from fixtures import build_cases,build_unsupported
from adapter import compile_bundle,compile_script
from runtime import execute,run_semantics,FAULTS,MODES
from experiment import D,read,save,digest,encoded,scenario,gold
from protocol import parse

def main(out):
    checks=[];cases=build_cases()
    checks.append({'check':'generator_cases','equal':cases==read('data/cases.json')})
    checks.append({'check':'generator_unsupported','equal':build_unsupported()==read('data/unsupported.json')})
    truth={};comparisons=0;mismatches=[]
    for c in cases:
        compiled=compile_bundle(c['bundle']);g=gold(c,compiled);truth[c['case_id']]=g
        for sid,ref in [(None,g['original'])]+list(g['interventions'].items()):
            comparisons+=1
            if run_semantics(compiled['program'],c['world'],c['goal'],sid)!=ref:mismatches.append([c['case_id'],sid])
        for i,r in enumerate(c['trusted_routes'],1):
            comparisons+=1
            if run_semantics(compile_script(r['source'],f'trusted/{i}.py')['program'],c['world'],c['goal'])!=g['routes'][i]:mismatches.append([c['case_id'],'route',i])
    checks.append({'check':'differential','equal':not mismatches,'comparisons':comparisons,'mismatches':mismatches})
    checks.append({'check':'aligned_truth','equal':truth==read('results/aligned/truth.json')})
    generated=[]
    for c in cases:
        for grid in read('data/specification.json')['grid']:
            sc=scenario(c,grid)
            for fault in FAULTS:
                for mode in MODES:generated.append({'case_id':c['case_id'],'family':c['family'],'variant':c['variant'],
                  'grid':grid['grid_id'],'mode':mode,'fault':fault,**execute(sc,mode,fault)})
    checks.append({'check':'deterministic_traces','conditions':len(generated),'equal':generated==read('results/deterministic.json'),
                   'sha256':digest(encoded(generated))})
    jobs={j['job_id']:j for j in read('api/jobs_frozen.json')};observed=read('api/observations.json');parsed={};bad=[]
    for row in observed:
        j=jobs[row['job_id']];raw=read('api/raw/'+row['request_hash']+'.json');p=parse(raw,j['ids']);parsed[row['job_id']]=p
        if p!=row['parsed']:bad.append(row['job_id'])
    checks.append({'check':'cached_model_parsing','jobs':len(observed),'equal':not bad,'mismatches':bad})
    contexts={r['context_id']:r['case'] for r in read('data/model_contexts.json')};replay=[]
    for row in observed:
        meta={k:row[k] for k in ('job_id','context_id','case_id','family','variant','grid','view','model')}
        for mode in ('flow','first','cost'):
            for fault in FAULTS:replay.append({**meta,'mode':mode,'fault':fault,**execute(contexts[row['context_id']],mode,fault,parsed[row['job_id']]['allowed_ids'])})
    checks.append({'check':'model_replay','conditions':len(replay),'equal':replay==read('results/model_replay.json'),
                   'sha256':digest(encoded(replay))})
    summary={'python':platform.python_version(),'offline':True,'new_api_calls':0,'checks':checks,'all_equal':all(r['equal'] for r in checks)}
    save(out/'reproduction.json',summary);print(json.dumps(summary))
    if not summary['all_equal']:raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();main(a.output)
