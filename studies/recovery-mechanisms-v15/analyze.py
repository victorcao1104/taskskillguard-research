"""Descriptive results and prespecified paired template-level contrasts; no API."""
import csv,gzip,itertools,json,math,random,statistics
from collections import Counter,defaultdict
from pathlib import Path
from rm15.tasks import TEMPLATES,structure
from rm15.protocol import MODELS,LEVELS,HISTORIES
ROOT=Path(__file__).resolve().parent


def load_records(pattern='formal--*.json.gz'):
    return [json.loads(gzip.decompress(p.read_bytes())) for p in sorted((ROOT/'results/episodes').glob(pattern))]


def api_cost(a):
    api=a['api']
    if not api:return 0
    usage=api.get('usage');model=a['_model']
    if usage and all(type(usage.get(k)) is int for k in ('input_tokens','output_tokens')):
        ip,op=(.125,.5) if model=='gpt-6-luna' else (.4,1.6)
        return (usage['input_tokens']*ip+usage['output_tokens']*op)/1e6
    request_id=api.get('request_id',a['_id']+'--slot'+str(a['slot']))
    req=ROOT/'api/requests'/(request_id+'.json')
    return json.loads(req.read_text())['reservation_upper_usd']


def flatten(r):
    j=r['job'];selected=r['selected'];final=r['final'];scale=r['scale']
    last=r['attempts'][-1]['validation'];actual=final or last
    codes=Counter(x['score']['stop_code'] or ('WRONG_CONTENT' if x['score']['wrong_content'] else 'MISSING_OBLIGATION') for x in actual['records'] if not x['success'])
    cost={};prefix={}
    for ev in [a['validation'] for a in r['attempts']]+([final,scale] if final else []):
        for k,v in ev['cost'].items():cost[k]=cost.get(k,0)+v
        for k,v in ev['prefix_cost'].items():prefix[k]=prefix.get(k,0)+v
    attempts=[]
    for a in r['attempts']:
        attempts.append({**a,'_model':j['model'],'_id':j['id']})
    source=j['campaign_kind']=='source'
    feasible=source or j['history']!='unknown_no_query'
    row={**j,'structure':structure(j['template']),'accepted':bool(selected),
         'success':bool(final and final['accepted']),'safe_complete':bool(final and final['safe_complete']),
         'correct_stop':bool(final and final['correct_stop']),'scale_success':bool(scale and scale['accepted']),
         'feasible':feasible,'wrong_stop':feasible and any(x['score']['wrong_stop'] for x in actual['records']),
         'failure_codes':dict(codes),'api_requests':r['api_requests'],'candidate_slots':len(r['attempts']),
         'cost_upper_usd':sum(api_cost(a) for a in attempts),
         'model_seconds':sum(a['api']['elapsed_seconds'] for a in attempts if a['api']),
         'prompt_seconds':sum(a['api'].get('prompt_preparation_seconds',0) for a in attempts if a['api']),
         'local_cost':cost,'logical_prefix_cost':prefix,
         'failure_after_acceptance':bool(final and not final['accepted']),
         'scale_failure_after_acceptance':bool(scale and not scale['accepted']),
         'first_slot_success':bool(final and final['accepted'] and len(r['attempts'])==1),
         'first_model_request_success':bool(final and final['accepted'] and r['api_requests']<=1)}
    for field in ('duplicate_attempts','duplicates_executed','wrong_cache_reads','invalid_cache_selected','permission_attempts','disclosure_attempts','unauthorized_executed','disclosure_executed'):
        row[field+'_episodes']=any(rec['score'].get(field,False) for a in r['attempts'] for rec in a['validation']['records']) or any(rec['score'].get(field,False) for rec in (final['records'] if final else []))
    return row


def summary(rows):
    n=len(rows);feasible=[r for r in rows if r['feasible']];boundary=[r for r in rows if not r['feasible']]
    return {'episodes':n,'accepted':sum(r['accepted'] for r in rows),'successful_final':sum(r['success'] for r in rows),
        'safe_complete_feasible':sum(r['safe_complete'] for r in feasible),'feasible_episodes':len(feasible),
        'correct_stop_boundary':sum(r['correct_stop'] for r in boundary),'boundary_episodes':len(boundary),
        'wrong_stop_feasible':sum(r['wrong_stop'] for r in feasible),
        'failure_after_acceptance':sum(r['failure_after_acceptance'] for r in rows),
        'scale_failure_after_acceptance':sum(r['scale_failure_after_acceptance'] for r in rows),
        'successful_scale':sum(r['scale_success'] for r in rows),
        'model_requests':sum(r['api_requests'] for r in rows),'cost_upper_usd':sum(r['cost_upper_usd'] for r in rows),
        'mean_model_seconds':statistics.mean(r['model_seconds'] for r in rows) if n else 0,
        'local_steps':sum(r['local_cost'].get('steps',0) for r in rows),'prefix_steps':sum(r['logical_prefix_cost'].get('steps',0) for r in rows),
        'local_seconds':sum(r['local_cost'].get('elapsed_seconds',0) for r in rows),'checker_seconds':sum(r['local_cost'].get('checker_seconds',0) for r in rows),
        'failure_episodes_by_code':dict(Counter(code for r in rows for code in r['failure_codes'])),
        'diagnostic_episodes':{f:sum(r[f+'_episodes'] for r in rows) for f in ('duplicate_attempts','duplicates_executed','wrong_cache_reads','invalid_cache_selected','permission_attempts','disclosure_attempts','unauthorized_executed','disclosure_executed')}}


def contrast(left,right,metric='success'):
    def cluster(rows):
        return {t:statistics.mean(float(r[metric]) for r in rows if r['template']==t) for t in TEMPLATES}
    l,r=cluster(left),cluster(right);diffs=[l[t]-r[t] for t in TEMPLATES];observed=statistics.mean(diffs)
    rng=random.Random(20261018);boot=sorted(statistics.mean(rng.choices(diffs,k=16)) for _ in range(10000))
    nonzero=[d for d in diffs if d];extreme=0
    for signs in itertools.product((-1,1),repeat=len(nonzero)):
        if abs(sum(d*s for d,s in zip(nonzero,signs)))>=abs(sum(diffs))-1e-12:extreme+=1
    return {'difference':observed,'bootstrap_95':[boot[249],boot[9749]],'paired_signflip_p_descriptive':extreme/(2**len(nonzero)),
        'templates':16,'nonzero_templates':len(nonzero),'per_template':dict(zip(TEMPLATES,diffs)),
        'per_structure':{s:statistics.mean(diffs[i] for i,t in enumerate(TEMPLATES) if structure(t)==s) for s in ('aggregation','graph','reports','service')},
        'warning':'Authored template clusters, four related structures, single model run; no multiplicity-adjusted confirmatory significance claim.'}


def make_plots(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=ROOT/'reports/figures';folder.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(10,3.7),layout='constrained')
    for ax,model in zip(axes,MODELS):
        for method in ('full','repair','replan'):
            y=[]
            for level in LEVELS:
                rs=[r for r in rows if r['campaign_kind']=='source' and r['model']==model and r['method']==method and (method=='replan' or r['source_level']==level)]
                y.append(100*statistics.mean(r['success'] for r in rs))
            ax.plot(LEVELS,y,marker='o',label=method)
        ax.axhline(100,color='gray',ls=':',label='specialist solver (offline)');ax.set_title(model);ax.set_ylim(-3,105);ax.set_ylabel('Safe completion (%)');ax.tick_params(axis='x',rotation=20);ax.grid(alpha=.2)
    axes[1].legend(fontsize=8);fig.savefig(folder/'source_integrity.png',dpi=180);fig.savefig(folder/'source_integrity.pdf');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.7),layout='constrained')
    for ax,model in zip(axes,MODELS):
        for history in HISTORIES:
            values=[100*statistics.mean(r['success'] for r in rows if r['campaign_kind']=='state' and r['model']==model and r['method']==m and r['history']==history) for m in 'ABCD']
            ax.plot(list('ABCD'),values,marker='o',label=history)
        ax.set_title(model);ax.set_ylim(-3,105);ax.set_ylabel('Correct outcome (%)');ax.set_xlabel('State support');ax.grid(alpha=.2)
    axes[1].legend(fontsize=8);fig.savefig(folder/'state_support.png',dpi=180);fig.savefig(folder/'state_support.pdf');plt.close(fig)


def main():
    records=load_records()
    if len(records)!=864:raise RuntimeError('INCOMPLETE_GRID:'+str(len(records)))
    rows=[flatten(r) for r in records];groups={}
    for model in MODELS:
        for method in ('full','repair'):
            for level in LEVELS:groups[f'source/{model}/{method}/{level}']=summary([r for r in rows if r['campaign_kind']=='source' and r['model']==model and r['method']==method and r['source_level']==level])
        groups[f'source/{model}/replan']=summary([r for r in rows if r['campaign_kind']=='source' and r['model']==model and r['method']=='replan'])
        for method in 'ABCD':
            rs=[r for r in rows if r['campaign_kind']=='state' and r['model']==model and r['method']==method]
            groups[f'state/{model}/{method}']=summary(rs)
            for h in HISTORIES:groups[f'state/{model}/{method}/{h}']=summary([r for r in rs if r['history']==h])
    comparisons={}
    for model in MODELS:
        for level in LEVELS:
            common=[r for r in rows if r['campaign_kind']=='source' and r['model']==model and r['source_level']==level]
            for metric in ('success','api_requests'):
                comparisons[f'source/{model}/{level}/full-minus-repair/{metric}']=contrast([r for r in common if r['method']=='full'],[r for r in common if r['method']=='repair'],metric)
        common=[r for r in rows if r['campaign_kind']=='state' and r['model']==model]
        for left,right in (('B','A'),('C','B'),('D','C')):
            comparisons[f'state/{model}/{left}-minus-{right}']=contrast([r for r in common if r['method']==left],[r for r in common if r['method']==right])
    curves={}
    for kind in ('source','state'):
        for model in MODELS:
            for method in (('full','repair','replan') if kind=='source' else tuple('ABCD')):
                rs=[r for r in rows if r['campaign_kind']==kind and r['model']==model and r['method']==method]
                curves[f'{kind}/{model}/{method}']={'n':len(rs),'candidate_slots':{str(k):sum(r['success'] and r['candidate_slots']<=k for r in rs) for k in (1,2)},'requests':{str(k):sum(r['success'] and r['api_requests']<=k for r in rs) for k in (0,1,2)},'cost_upper_usd':{str(k):sum(r['success'] and r['cost_upper_usd']<=k for r in rs) for k in (0,.0005,.001,.002,.004,.008,.016)},'model_seconds':{str(k):sum(r['success'] and r['model_seconds']<=k for r in rs) for k in (0,2,5,10,20,60,120)}}
    folder=ROOT/'reports';folder.mkdir(exist_ok=True)
    heldout=[r for r in rows if r['template'] not in (TEMPLATES[0],TEMPLATES[-1])]
    sensitivity={}
    for model in MODELS:
        for method in ('full','repair','replan','A','B','C','D'):
            rs=[r for r in heldout if r['model']==model and r['method']==method]
            sensitivity[f'{model}/{method}']=summary(rs)
    for name,value in [('episode_table.json',rows),('main_summary.json',{'groups':groups,'contrasts':comparisons,'curves':curves,'overall':summary(rows),'exploratory_excluding_two_pilot_templates':sensitivity})]:
        (folder/name).write_bytes((json.dumps(value,sort_keys=True,indent=2)+'\n').encode())
    cols=['id','template','structure','campaign_kind','source_level','history','method','model','accepted','success','safe_complete','correct_stop','scale_success','api_requests','cost_upper_usd','model_seconds']
    with (folder/'episode_table.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    make_plots(rows)
    print(json.dumps({'episodes':len(rows),'successful':sum(r['success'] for r in rows),'formal_cost_upper':sum(r['cost_upper_usd'] for r in rows)}))

if __name__=='__main__':main()
