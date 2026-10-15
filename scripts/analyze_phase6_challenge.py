"""Separate targeted-challenge results, never pooled with structural holdout."""
from collections import defaultdict,Counter
import json
import sys
from phase6_common import ROOT,read_rows,immutable,jb,rb
sys.path.insert(0,str(ROOT/'src'))
from tsg.protocol_v6 import AXES
from tsg.analysis_v6 import label_counts,paired_interval
from analyze_phase6 import summarize_execution
OUT=ROOT/'results/phase6/challenge'


def main():
    cs={c['case_id']:c for c in read_rows(ROOT/'data/phase6/challenge.jsonl')}
    truth=read_rows(OUT/'first/truth.jsonl');gold={r['case_id']:{s['id']:s for s in r['labels']} for r in truth}
    obs=read_rows(OUT/'api/observations.jsonl');details=[]
    for r in obs:
        for sid,g in gold[r['case_id']].items():
            for axis in AXES:
                pred=r['parsed']['by_id'].get(sid,{}).get(axis)
                details.append({k:r[k] for k in ('case_id','family','model','view')}|{'id':sid,'axis':axis,
                    'gold':g[axis],'predicted':pred,'correct':pred==g[axis]})
    groups=defaultdict(list)
    for r in details:groups[(r['model'],r['view'],r['axis'])].append((r['gold'],r['predicted']))
    metrics=[dict(zip(('model','view','axis'),key))|label_counts(rows) for key,rows in sorted(groups.items())]
    contrasts=[]
    for model in sorted({r['model'] for r in details}):
        for axis in AXES:
            index={(r['case_id'],r['id'],r['view']):r for r in details if r['model']==model and r['axis']==axis}
            for baseline in ('table','shuffled','padding'):
                pairs=[]
                for (cid,sid,v),r in index.items():
                    if v=='graph':pairs.append({'family':r['family'],'difference':int(r['correct'])-int(index[(cid,sid,baseline)]['correct'])})
                contrasts.append({'model':model,'axis':axis,'contrast':'graph-'+baseline}|paired_interval(pairs))
    recovery=read_rows(OUT/'recovery/container_results.jsonl');integrated=read_rows(OUT/'integrated/container_results.jsonl')
    from tsg.truth_v6 import run
    for r in recovery+integrated:
        c=cs[r['case_id']];world=c['worlds'][0]
        if r['grant_condition']=='undergrant':world={**world,'grants':[g for g in world['grants'] if g[0]=='read']}
        paths=[run(p,world,c['goal']) for p in [c['program']]+c['routes']]
        r['initial_legal_route']=any(p['goal'] and all(t['authorized'] for t in p['trace']) for p in paths)
    index={(r['case_id'],r['grant_condition'],r['quota'],r['fault'],r['mode']):r for r in recovery}
    comparisons=[]
    for grants in ('supplied','undergrant'):
        for quota in (4,16):
            for fault in ('none','transient_before','known_after','ambiguous_after'):
                for a,b in [('search','checkpoint'),('first_feasible','checkpoint'),('search_equal','first_feasible')]:
                    for metric in ('authorized_goal','charged_calls','planner_steps'):
                        pairs=[];successful=[]
                        for c in cs.values():
                            ra=index[(c['case_id'],grants,quota,fault,a)].get('result',{})
                            rb_=index[(c['case_id'],grants,quota,fault,b)].get('result',{})
                            p={'family':c['family'],'difference':int(ra.get(metric,0))-int(rb_.get(metric,0))}
                            pairs.append(p)
                            if ra.get('authorized_goal') and rb_.get('authorized_goal'):successful.append(p)
                        comparisons.append({'grant_condition':grants,'quota':quota,'fault':fault,'contrast':a+'-'+b,'metric':metric,
                                            'all_conditions':paired_interval(pairs),'joint_success':paired_interval(successful)})
    summary={'cases':len(cs),'families':6,'model_conditions':len(obs),'protocol_valid':sum(r['parsed']['protocol_valid'] for r in obs),
             'unique_requests':len({r['request_hash'] for r in obs}),'metrics':metrics,'representation_comparisons':contrasts,
             'recovery':summarize_execution(recovery,['grant_condition','quota','fault','mode']),
             'integrated':summarize_execution(integrated,['gate','model','view','fault','mode']),
             'recovery_comparisons':comparisons,
             'gold_distribution':{axis:dict(Counter(s[axis] for r in truth for s in r['labels'])) for axis in AXES},
             'recovery_conditions':len(recovery),'integrated_conditions':len(integrated),
             'scope':'targeted mechanism pressure test; six authored families; no prevalence or confirmatory generalization claim'}
    immutable(OUT/'analysis/candidate_scores.jsonl',rb(details));immutable(OUT/'analysis/summary.json',jb(summary))
    print(json.dumps({k:summary[k] for k in ('cases','families','model_conditions','protocol_valid','unique_requests','gold_distribution','recovery_conditions','integrated_conditions')}))


if __name__=='__main__':main()
