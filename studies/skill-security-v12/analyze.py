"""Derived summaries retain all invalid, unknown and unsuccessful conditions."""
import json
from collections import Counter,defaultdict
from pathlib import Path
from experiment import D,read,save,gold,legal
from adapter import compile_bundle
from runtime import execute,FAULTS
from protocol import AXES

def summarize(rows,fields):
    groups=defaultdict(list)
    for r in rows:groups[tuple(r[k] for k in fields)].append(r)
    result=[]
    for key,rs in sorted(groups.items()):
        result.append({**dict(zip(fields,key)),'n':len(rs),'authorized_goals':sum(r['authorized_goal'] for r in rs),
          'plain_goals':sum(r['goal'] for r in rs),'unauthorized_cases':sum(r['unauthorized_effects']>0 for r in rs),
          'forbidden_flow_cases':sum(r['forbidden_flows']>0 for r in rs),'duplicates':sum(r['duplicate_effects'] for r in rs),
          'calls':sum(r['charged_calls'] for r in rs),'planner_steps':sum(r['planner_steps'] for r in rs),
          'simulated_calls':sum(r['simulated_calls'] for r in rs),'route_bypass':sum(r['route_bypass'] for r in rs),
          'failure_reasons':dict(Counter(r['failure_reason'] or 'success' for r in rs))})
    return result

def offline():
    cases=read('data/cases.json');truth=read('results/aligned/truth.json');coverage=[]
    ops={'read':'file.read','write':'file.write','delete':'file.delete','emit':'network.send'}
    for c in cases:
        graph=read(f"results/phase5_extractor/{c['case_id']}.json");sites=truth[c['case_id']]['sites']
        located=0;matched=0
        for s in sites:
            matches=[n for n in graph['nodes'] if n.get('provenance',{}).get('file')=='scripts/main.py'
                 and n['provenance'].get('line_start',0)<=s['line']<=n['provenance'].get('line_end',0)]
            located+=bool(matches);matched+=any(n.get('operation')==ops[s['op']] for n in matches)
        coverage.append({'case_id':c['case_id'],'sites':len(sites),'located':located,'operation_matched':matched})
    save(D/'results/coverage_corrected.json',{'rows':coverage,'sites':sum(r['sites'] for r in coverage),
      'located':sum(r['located'] for r in coverage),'operation_matched':sum(r['operation_matched'] for r in coverage),
      'correction':'First scoring looked for top-level node spans; actual spans are in node.provenance. First output retained.',
      'operation_map':ops,'limits':'Loose location can match a bind/condition node, not an effect. Explicit operation mapping separately reported; mock emit is not a supported Phase5 tool.'})
    rows=read('results/deterministic.json');controls=read('results/gate_controls.json')
    save(D/'analysis/deterministic_summary.json',summarize(rows,['grid','variant','fault','mode']))
    save(D/'analysis/gate_summary.json',summarize(controls,['gate','variant','fault','mode']))
    paired=[]
    index={(r['case_id'],r['grid'],r['fault'],r['mode']):r for r in rows}
    for r in rows:
        if r['mode']!='first':continue
        b=index[r['case_id'],r['grid'],r['fault'],'cost']
        paired.append({'case_id':r['case_id'],'family':r['family'],'grid':r['grid'],'fault':r['fault'],
         'first_success':r['authorized_goal'],'cost_success':b['authorized_goal'],
         'success_difference':int(b['authorized_goal'])-int(r['authorized_goal']),
         'call_difference':b['charged_calls']-r['charged_calls'],
         'planner_difference':b['planner_steps']-r['planner_steps']})
    save(D/'analysis/paired_recovery.json',paired)
    counts={a:dict(Counter(v[a] for g in truth.values() for v in g['labels'].values())) for a in AXES}
    artificial=[]
    for c in cases:
        g=truth[c['case_id']]
        for sid,label in g['labels'].items():
            if label['scope']=='no' and label['current']=='yes':artificial.append({'case_id':c['case_id'],'site':sid,'labels':label})
    save(D/'analysis/truth_summary.json',{'label_counts':counts,'unsafe_original_prerequisites':artificial,
      'baseline_goal_failures':[c['case_id'] for c in cases if not truth[c['case_id']]['original']['goal']],
      'unexecuted_sites':sum(v['scope']=='unknown' for g in truth.values() for v in g['labels'].values()),
      'independent_families':12,'lexical_variants_are_dependent':True})
    print(json.dumps({'conditions':len(rows),'recovery_pairs':len(paired),'truth':counts,
                      'phase5_located':sum(r['located'] for r in coverage),'phase5_operation_matched':sum(r['operation_matched'] for r in coverage)}))

def models():
    observations=read('api/observations.json');contexts={c['context_id']:c for c in read('data/model_contexts.json')}
    truth={k:gold(c['case'],compile_bundle(c['case']['bundle'])) for k,c in contexts.items()}
    save(D/'analysis/model_truth.json',truth)
    scores=[];runs=[]
    for row in observations:
        key=row['context_id'];g=truth[key];parsed=row['parsed'];pred=parsed['labels']
        meta={k:row[k] for k in ('job_id','context_id','case_id','family','variant','grid','view','model')}
        for sid,labels in g['labels'].items():
            for axis,target in labels.items():
                answer=pred[sid][axis] if pred else 'invalid'
                scores.append({**meta,'site':sid,'axis':axis,'target':target,'answer':answer,'correct':answer==target,
                  'unnecessary_unknown':answer=='unknown' and target in ('yes','no'),
                  'missed_unknown':target=='unknown' and answer!='unknown'})
        for mode in ('flow','first','cost'):
            for fault in FAULTS:runs.append({**meta,'mode':mode,'fault':fault,**execute(contexts[key]['case'],mode,fault,parsed['allowed_ids'])})
    save(D/'results/model_replay.json',runs);save(D/'analysis/model_scores.json',scores)
    groups=defaultdict(list)
    for r in scores:groups[r['model'],r['view'],r['grid'],r['axis']].append(r)
    stats=[]
    for (model,view,grid,axis),rs in sorted(groups.items()):
        familymeans=[sum(x['correct'] for x in rs if x['family']==f)/sum(x['family']==f for x in rs) for f in {x['family'] for x in rs}]
        stats.append({'model':model,'view':view,'grid':grid,'axis':axis,'n':len(rs),'correct':sum(r['correct'] for r in rs),
          'unknown_answers':sum(r['answer']=='unknown' for r in rs),'unnecessary_unknown':sum(r['unnecessary_unknown'] for r in rs),
          'missed_unknown':sum(r['missed_unknown'] for r in rs),'invalid':sum(r['answer']=='invalid' for r in rs),
          'family_mean_accuracy':sum(familymeans)/len(familymeans)})
    save(D/'analysis/model_accuracy.json',stats)
    save(D/'analysis/model_replay_summary.json',summarize(runs,['model','view','grid','variant','fault','mode']))
    jobscore=defaultdict(list)
    for r in scores:jobscore[r['model'],r['context_id'],r['view']].append(r)
    paired=[]
    for (model,context,view),rs in jobscore.items():
        if view!='source':continue
        graph=jobscore[model,context,'graph']
        paired.append({'model':model,'context':context,'family':rs[0]['family'],'grid':rs[0]['grid'],
          'source_correct':sum(r['correct'] for r in rs),'graph_correct':sum(r['correct'] for r in graph),'fields':len(rs)})
    save(D/'analysis/paired_graph.json',paired)
    unique=len({r['request_hash'] for r in observations});raws=list((D/'api/raw').glob('*.json'))
    summary={'jobs':len(observations),'distinct_request_hashes':unique,'raw_records':len(raws),
      'valid_jobs':sum(r['parsed']['protocol_valid'] for r in observations),
      'invalid_job_reasons':dict(Counter(code for r in observations if not r['parsed']['protocol_valid'] for code in r['parsed']['diagnostic_codes'])),
      'shared_input_jobs':len(observations)-unique,'model_replay_conditions':len(runs),
      'sites_per_all_contexts':sum(len(x['sites']) for x in truth.values()),
      'open_catalogue_limit':'Open/closed empty attack catalogues both lack a legal listed route. This pair does not identify a closure benefit.',
      'graph_limit':'Graph changes token count; no padding control or repeated sampling in this new campaign.'}
    save(D/'analysis/model_summary.json',summary);print(json.dumps(summary))

if __name__=='__main__':
    import sys
    globals()[sys.argv[1]]()
