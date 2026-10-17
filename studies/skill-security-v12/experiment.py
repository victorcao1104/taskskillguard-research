"""Reproducible, offline synthetic experiment. Never invokes source natively."""
import argparse,hashlib,json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from adapter import compile_bundle,compile_script,Unsupported,ROOT
from runtime import execute,run_semantics,MODES,FAULTS
import reference
from tsg.runtime_v6 import run_semantics as old_runtime,edges
from tsg.truth_v6 import run as old_reference
from tsg.extraction_v5 import extract_graph_v5

D=Path(__file__).resolve().parent
def encoded(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def digest(data):return hashlib.sha256(data).hexdigest()
def save(path,value):
    path=Path(path);data=encoded(value);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:raise ValueError('IMMUTABLE_OUTPUT_DIFFERS:'+str(path))
    else:path.write_bytes(data)
def read(name):return json.loads((D/name).read_text(encoding='utf-8'))
def scenario(case,grid):
    c=deepcopy(case);c['quota']=grid['quota'];c['catalog_closed']=grid['catalog_closed']
    if grid['route_policy']=='none':c['trusted_routes']=[]
    return c
def legal(run):return run['goal'] and all(e['authorized'] and e['flow_allowed'] for e in run['trace'])
def gold(case,compiled):
    source=case['bundle'][compiled['entry']];file=compiled['entry']
    sites=reference.static_sites(source,file)
    original=reference.run(source,file,case['world'],case['goal'])
    routes=[original]+[reference.run(r['source'],f'trusted/{i}.py',case['world'],case['goal']) for i,r in enumerate(case['trusted_routes'],1)]
    solutions=[r for r in routes if legal(r)]
    labels={};interventions={}
    for s in sites:
        sid=s['id'];seen=[e for e in original['trace'] if e['id']==sid]
        changed=reference.run(source,file,case['world'],case['goal'],sid);interventions[sid]=changed
        scope=('yes' if all(e['authorized'] for e in seen) else 'no') if seen else 'unknown'
        flow=('yes' if all(e['flow_allowed'] for e in seen) else 'no') if seen else 'unknown'
        if s['op']!='emit':flow='na'
        current=('no' if changed['goal'] else 'yes') if original['goal'] and seen else 'unknown'
        targets={(e['op'],e['resource']) for e in seen}
        catalogue='unknown'
        if targets and case['catalog_closed'] and solutions:
            catalogue='no' if any(not targets.intersection((e['op'],e['resource']) for e in r['trace']) for r in solutions) else 'yes'
        labels[sid]={'scope':scope,'flow':flow,'current':current,'catalogue':catalogue}
    return {'sites':sites,'labels':labels,'original':original,'routes':routes,'interventions':interventions}

def prepare():
    freeze=read('provenance/pre_evaluation_freeze/manifest.json')
    for name,sha in freeze['sha256'].items():
        if digest((D/name).read_bytes())!=sha:raise ValueError('PRE_EVALUATION_SOURCE_CHANGED:'+name)
    from fixtures import build_cases,build_unsupported,FAMILY_DESCRIPTIONS,STRUCTURAL_ASSUMPTIONS,BUDGET_GRID
    cases=build_cases();unsupported=build_unsupported()
    save(D/'data/cases.json',cases);save(D/'data/unsupported.json',unsupported)
    save(D/'data/specification.json',{'families':FAMILY_DESCRIPTIONS,'assumptions':STRUCTURAL_ASSUMPTIONS,'grid':BUDGET_GRID})
    diff=[];bridge=[];coverage=[];truth={};probes=[]
    for case in cases:
        c=compile_bundle(case['bundle']);g=gold(case,c);truth[case['case_id']]=g
        ids=set(c['provenance']);expected={s['id'] for s in g['sites']}
        graph=extract_graph_v5(case['case_id'],case['bundle'])
        save(D/f"results/phase5_extractor/{case['case_id']}.json",graph)
        # Source-line presence is a deliberately loose locator metric, not correct effect classification.
        found={(n.get('file'),line) for n in graph['nodes'] for line in range(n.get('line_start',0),n.get('line_end',0)+1)}
        coverage.append({'case_id':case['case_id'],'source_sites':len(expected),'adapter_missed':sorted(expected-ids),
          'adapter_extra':sorted(ids-expected),'phase5_nodes':len(graph['nodes']),
          'phase5_located_sites':sum((c['entry'],s['line']) in found for s in g['sites']),
          'phase5_unresolved':len(graph.get('unresolved',[]))})
        runs=[(None,g['original'])]+list(g['interventions'].items())
        for suppress,ref in runs:
            actual=run_semantics(c['program'],case['world'],case['goal'],suppress)
            diff.append({'case_id':case['case_id'],'suppress':suppress,'equal':actual==ref,
                         **({} if actual==ref else {'production':actual,'reference':ref})})
            # Phase6 bridge compares its own unchanged pair; extra v12 fields/limits/preservation are not claims of v6 equivalence.
            a=old_runtime(c['program'],case['world'],case['goal'],suppress)
            b=old_reference(c['program'],case['world'],case['goal'],suppress)
            project=lambda r:{k:r[k] for k in ('files','emits','error')}
            bridge.append({'case_id':case['case_id'],'suppress':suppress,'old_pair_equal':a==b,
                           'v12_value_projection_equal':project(actual)==project(a),
                           'eligible':ref['error'] is None})
        for i,r in enumerate(case['trusted_routes'],1):
            file=f'trusted/{i}.py';p=compile_script(r['source'],file)['program']
            ref=reference.run(r['source'],file,case['world'],case['goal'])
            actual=run_semantics(p,case['world'],case['goal'])
            diff.append({'case_id':case['case_id'],'route':i,'equal':actual==ref,
                         **({} if actual==ref else {'production':actual,'reference':ref})})
    for case in unsupported:
        try:compile_bundle(case['bundle']);reason=None
        except Unsupported as exc:reason=str(exc)
        r=execute(case,'flow');probes.append({'case_id':case['case_id'],'compile_rejection':reason,'result':r})
    save(D/'results/first_differential.json',diff)
    save(D/'results/phase6_bridge.json',bridge)
    save(D/'results/coverage.json',coverage)
    save(D/'results/truth.json',truth)
    save(D/'results/unsupported.json',probes)
    summary={'cases':len(cases),'sites':sum(x['source_sites'] for x in coverage),'differential':len(diff),
      'differential_mismatches':sum(not x['equal'] for x in diff),'bridge_checks':len(bridge),
      'old_pair_mismatches':sum(not x['old_pair_equal'] for x in bridge),
      'value_projection_mismatches':sum(x['eligible'] and not x['v12_value_projection_equal'] for x in bridge),
      'adapter_missing':sum(len(x['adapter_missed']) for x in coverage),'unsupported_rejected':sum(x['compile_rejection'] is not None for x in probes)}
    save(D/'results/preparation_summary.json',summary);print(json.dumps(summary))

def deterministic():
    cases=read('data/cases.json');spec=read('data/specification.json');rows=[]
    if read('results/aligned/summary.json')['differential_mismatches']:raise ValueError('UNRESOLVED_DIFFERENTIAL')
    for case in cases:
        for grid in spec['grid']:
            c=scenario(case,grid)
            for fault in FAULTS:
                for mode in MODES:
                    r=execute(c,mode,fault)
                    rows.append({'case_id':case['case_id'],'family':case['family'],'variant':case['variant'],
                                 'grid':grid['grid_id'],'mode':mode,'fault':fault,**r})
    save(D/'results/deterministic.json',rows)
    # Gate ablation: all-allow is gateway alone; all-block tests rescue dependence on trusted routes.
    gates=[]
    for case in cases:
        ids=list(compile_bundle(case['bundle'])['provenance'])
        for gate,allowed in [('allow_all',ids),('block_all',[])]:
            for mode in ('flow','first','cost'):
                for fault in FAULTS:
                    gates.append({'case_id':case['case_id'],'family':case['family'],'variant':case['variant'],
                                  'gate':gate,'mode':mode,'fault':fault,**execute(case,mode,fault,allowed)})
    save(D/'results/gate_controls.json',gates)
    print(json.dumps({'deterministic_conditions':len(rows),'gate_control_conditions':len(gates)}))

def align():
    # First results are immutable. This explicitly new revision applies the recorded reference amendment.
    cases=read('data/cases.json');diff=[];truth={}
    for case in cases:
        c=compile_bundle(case['bundle']);g=gold(case,c);truth[case['case_id']]=g
        for suppress,ref in [(None,g['original'])]+list(g['interventions'].items()):
            actual=run_semantics(c['program'],case['world'],case['goal'],suppress)
            diff.append({'case_id':case['case_id'],'suppress':suppress,'equal':actual==ref,
                        **({} if actual==ref else {'production':actual,'reference':ref})})
        for i,r in enumerate(case['trusted_routes'],1):
            file=f'trusted/{i}.py';p=compile_script(r['source'],file)['program']
            ref=reference.run(r['source'],file,case['world'],case['goal'])
            actual=run_semantics(p,case['world'],case['goal'])
            diff.append({'case_id':case['case_id'],'route':i,'equal':actual==ref,
                        **({} if actual==ref else {'production':actual,'reference':ref})})
    summary={'differential':len(diff),'differential_mismatches':sum(not x['equal'] for x in diff),
             'reference_sha256':digest((D/'reference.py').read_bytes()),
             'original_first_result':'results/first_differential.json','post_holdout_alignment':True}
    save(D/'results/aligned/differential.json',diff);save(D/'results/aligned/truth.json',truth)
    save(D/'results/aligned/summary.json',summary);print(json.dumps(summary))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','align','deterministic']);args=p.parse_args()
    globals()[args.command]()
