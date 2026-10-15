"""Read immutable evidence; report denominators, paired effects and execution stages."""
from collections import defaultdict,Counter
import json
import sys
from phase6_common import ROOT,cases,read_rows,immutable,jb,rb
sys.path.insert(0,str(ROOT/'src'))
from tsg.analysis_v6 import paired_interval,label_counts
from tsg.protocol_v6 import AXES


def summarize_execution(rows,keys):
    groups=defaultdict(list)
    for r in rows:groups[tuple(r.get(k) for k in keys)].append(r)
    output=[]
    for key,rs in sorted(groups.items(),key=lambda v:str(v[0])):
        result=[r.get('result',{}) for r in rs]
        out=dict(zip(keys,key));out.update(n=len(rs),completed=sum(r['runner_status']=='completed' for r in rs),
             goal=sum(bool(r.get('goal')) for r in result),authorized_goal=sum(bool(r.get('authorized_goal')) for r in result),
             charged_calls=sum(r.get('charged_calls',0) for r in result),attempts=sum(r.get('attempts',0) for r in result),
             unauthorized_effects=sum(r.get('unauthorized_effects',0) for r in result),
             duplicate_effects=sum(r.get('duplicate_effects',0) for r in result),
             runner_errors=sum(r['runner_status']!='completed' for r in rs),
             protocol_invalid=sum(r.get('protocol_valid') is False for r in rs),
             parse_failures=sum(r.get('failure_reason')=='parse_error' for r in result),
             recovered_success=sum(bool(r.get('authorized_goal')) and r.get('attempts',0)>1 for r in result),
             route_bypass=sum(bool(r.get('route_bypass')) for r in result),
             ambiguous_stops=sum(bool(r.get('ambiguous_stop')) for r in result),
             initial_catalog_infeasible=sum(r.get('initial_legal_route') is False for r in rs),
             planner_steps=sum(r.get('planner_steps',0) for r in result),
             simulated_effects=sum(r.get('simulated_effects',0) for r in result),
             stage_failures=dict(Counter(t.get('status') for r in result for t in r.get('trace',[])
                                         if t.get('status') not in ('committed','receipt_reused'))),
             failures=dict(Counter(str(r.get('failure_reason')) for r in result if not r.get('authorized_goal'))))
        output.append(out)
    return output


def main():
    cs={c['case_id']:c for c in cases()}
    truth=read_rows(ROOT/'results/phase6/first/truth.jsonl')
    gold={r['case_id']:{n['id']:n for n in r['labels']} for r in truth}
    obs=read_rows(ROOT/'results/phase6/api/observations.jsonl')
    mainobs=[r for r in obs if r['replicate']==0]
    details=[]
    for r in mainobs:
        for nid,t in gold[r['case_id']].items():
            prediction=r['parsed']['by_id'].get(nid,{})
            for axis in AXES:
                details.append({k:r[k] for k in ('case_id','family','split','model','view','job_id')}|
                               {'id':nid,'axis':axis,'gold':t[axis],'predicted':prediction.get(axis),
                                'correct':prediction.get(axis)==t[axis],'gold_reasons':t.get('reasons',{}).get(axis,[])})
    metrics=[]
    for split in ('all','dev','heldout'):
        groups=defaultdict(list)
        for r in details:
            if split=='all' or r['split']==split:groups[(r['model'],r['view'],r['axis'])].append((r['gold'],r['predicted']))
        for (m,v,a),ps in sorted(groups.items()):metrics.append({'split':split,'model':m,'view':v,'axis':a}|label_counts(ps))
    comparisons=[]
    for split in ('all','dev','heldout'):
        for m in sorted({r['model'] for r in details}):
            for axis in AXES:
                index={(r['case_id'],r['id'],r['view']):r for r in details if r['model']==m and r['axis']==axis and (split=='all' or r['split']==split)}
                for v,base in [('graph','table'),('graph','shuffled'),('graph','padding')]:
                    pairs=[]
                    for (cid,nid,view),r in index.items():
                        if view!=v:continue
                        b=index[(cid,nid,base)]
                        pairs.append({'family':r['family'],'difference':int(r['correct'])-int(b['correct'])})
                    comparisons.append({'split':split,'model':m,'axis':axis,'contrast':v+'-'+base}|paired_interval(pairs))
    recovery=read_rows(ROOT/'results/phase6/recovery/container_results.jsonl')
    integrated=read_rows(ROOT/'results/phase6/integrated/container_results.jsonl')
    from tsg.truth_v6 import run
    for r in recovery+integrated:
        c=cs[r['case_id']];w=c['worlds'][0]
        if r['grant_condition']=='undergrant':w={**w,'grants':[g for g in w['grants'] if g[0]=='read']}
        routes=[run(p,w,c['goal']) for p in [c['program']]+c['routes']]
        r['initial_legal_route']=any(x['goal'] and all(t['authorized'] for t in x['trace']) for x in routes)
    recsummary=summarize_execution(recovery,['grant_condition','quota','fault','mode'])
    intsummary=summarize_execution(integrated,['gate','model','view','fault','mode'])
    recovery_pairs=[]
    ri={(r['case_id'],r['grant_condition'],r['quota'],r['fault'],r['mode']):r for r in recovery}
    for grants in ('supplied','undergrant'):
        for quota in (4,16):
            for fault in ('none','transient_before','known_after','ambiguous_after'):
                for metric in ('authorized_goal','charged_calls','duplicate_effects'):
                    ps=[]
                    for c in cs.values():
                        a=ri[(c['case_id'],grants,quota,fault,'search')].get('result',{})
                        b=ri[(c['case_id'],grants,quota,fault,'checkpoint')].get('result',{})
                        ps.append({'family':c['family'],'difference':int(a.get(metric,0))-int(b.get(metric,0))})
                    recovery_pairs.append({'grant_condition':grants,'quota':quota,'fault':fault,'metric':metric,
                                           'contrast':'search-checkpoint'}|paired_interval(ps))
    repeat_groups=defaultdict(list)
    for r in obs:
        repeat_groups[(r['case_id'],r['model'],r['view'])].append(r)
    repeats=[]
    for (cid,m,v),rs in repeat_groups.items():
        if len(rs)<3:continue
        valid=all(r['parsed']['protocol_valid'] for r in rs)
        same=valid and len({json.dumps(r['parsed']['by_id'],sort_keys=True) for r in rs})==1
        repeats.append({'case_id':cid,'family':cs[cid]['family'],'model':m,'view':v,'n':len(rs),'all_valid':valid,'identical':same})
    unknown=Counter()
    for r in truth:
        for t in r['labels']:
            for axis in AXES:
                if t[axis]=='unknown':
                    reasons=t.get('reasons',{}).get(axis,[])
                    if isinstance(reasons,str):reasons=[reasons]
                    for reason in reasons:unknown[(axis,str(reason))]+=1
    summary={'cases':len(cs),'families':len({c['family'] for c in cs.values()}),'main_conditions':len(mainobs),
             'main_protocol_valid':sum(r['parsed']['protocol_valid'] for r in mainobs),'all_conditions':len(obs),
             'unique_requests':len({r['request_hash'] for r in obs}),
             'metrics':metrics,'representation_comparisons':comparisons,'recovery':recsummary,
             'recovery_pairs':recovery_pairs,'integrated':intsummary,'repeats':repeats,
             'unknown_reasons':[{'axis':a,'reason':r,'count':n} for (a,r),n in sorted(unknown.items())],
             'recovery_conditions':len(recovery),'integrated_conditions':len(integrated),
             'container_count':2,'no_real_skill_or_human_annotation':True}
    out=ROOT/'results/phase6/analysis'
    immutable(out/'candidate_scores.jsonl',rb(details));immutable(out/'summary.json',jb(summary))
    print(json.dumps({k:summary[k] for k in ('cases','families','main_conditions','main_protocol_valid','all_conditions','unique_requests','recovery_conditions','integrated_conditions')}))


if __name__=='__main__':main()
