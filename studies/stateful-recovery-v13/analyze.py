"""Derive all tables from immutable records; no model calls or outcome filtering."""
from pathlib import Path
import collections,csv,gzip,json,random,statistics
from sr13.io import read,save
from sr13.data import TEST_TASKS

D=Path(__file__).resolve().parent


def request_cost(raw,ledger,request):
    if raw.get('reservation_id') in ledger:
        entry=ledger[raw['reservation_id']]
        return entry.get('cost_usd',entry['reserved_usd'])
    if raw.get('status')=='interrupted_unknown':
        # Attribution is uncertain; use this request's full cap locally. The
        # global budget still uses every retained ledger reservation exactly once.
        return request['reservation_upper_usd']
    raise ValueError('UNACCOUNTED_REQUEST')


def records(campaign):
    return [read(p) for p in sorted((D/'results'/campaign).glob('*--*.json'))]


def bootstrap(groups):
    values=[statistics.mean(v) for v in groups.values()];n=len(values);rng=random.Random(20261018)
    samples=sorted(statistics.mean(rng.choices(values,k=n)) for _ in range(10000))
    return {'clusters':n,'cluster_means':dict(zip(groups,values)),
            'difference':statistics.mean(values),'interval_95':[samples[249],samples[9749]],
            'interpretation':'Exploratory cluster bootstrap with few developer-authored families, not a population guarantee.'}


def main():
    cases={c['case_id']:c for c in read(D/'data/cases.json')}
    adaptive=read(D/'data/adaptive_search.json')
    cases.update({c['case_id']:c for c in adaptive['selected']})
    old_main=records('main');amended=records('state_amendment');adaptive_rows=records('adaptive');offline=records('offline_corrected')
    robust=records('robust_protocol');robust_adaptive=records('adaptive_net');infra_failed=records('robust_adaptive')
    typed=records('typed_roles')
    def identity(r):return (r['case_id'],r['method'],r['model'],r['replicate'])
    overlay={identity(r):r for r in old_main};overlay.update({identity(r):r for r in amended});main_rows=list(overlay.values())
    if len(main_rows)!=1152 or len(amended)!=144 or len(adaptive_rows)!=96 or len(offline)!=756 or len(robust)!=1152 or len(robust_adaptive)!=96 or len(typed)!=288:raise ValueError('INCOMPLETE_CAMPAIGN')
    ledger={r['reservation_id']:r for r in map(json.loads,(D/'api/budget.jsonl').read_text().splitlines())}
    raw={r['request_hash']:r for r in (read(p) for p in (D/'api/raw').glob('*.json'))}
    def enrich(r):
        c=cases[r['case_id']];ev=r['evaluation'];attempts=r.get('attempts',[])
        hashes=[a['request']['hash'] for a in attempts if a.get('request')]
        cost=0;tokens=collections.Counter();errors=collections.Counter()
        for h in hashes:
            data=raw[h];request=next(a['request'] for a in attempts if (a.get('request') or {}).get('hash')==h)
            cost+=request_cost(data,ledger,request)
            for key in ('input_tokens','output_tokens'):tokens[key]+=(data.get('usage') or {}).get(key,0)
        for a in attempts:
            if a['status']=='invalid':errors[a['reason']]+=1
        return {'case_id':r['case_id'],'family':c['family'],'attack':c['attack'],
                'expected_status':c['expected_status'],'method':r['method'],'model':r.get('model','none'),
                'replicate':r.get('replicate',0),'accepted':r['accepted'],
                **{k:ev[k] for k in ('safe_complete','ordinary_complete','unauthorized','disclosure','duplicate_effects')},
                'provider_invocations':r['model_calls'],'request_attempts':len(hashes),'api_upper_usd':cost,
                'interrupted_unknown_requests':sum(raw[h].get('status')=='interrupted_unknown' for h in hashes),
                'input_tokens':tokens['input_tokens'],'output_tokens':tokens['output_tokens'],
                'search_executions':r['search_cost']['executions'],'search_steps':r['search_cost']['steps'],
                'search_tool_calls':r['search_cost']['tool_calls'],'search_cpu_seconds':r['search_cpu_seconds'],
                'search_seconds':r['search_seconds'],'termination':r.get('termination','accepted' if r['accepted'] else 'rejected'),
                'final_executions':r['final_evaluation_cost']['executions'],
                'final_steps':r['final_evaluation_cost']['steps'],
                'final_tool_calls':r['final_evaluation_cost']['tool_calls'],
                'invalid_attempts':dict(errors),'request_hashes':hashes,
                'normalized_attempts':sum(bool((a.get('request') or {}).get('transport_normalization')) for a in attempts)}
    groups={};detail=[]
    matched_ids={r['case_id'] for r in main_rows}
    matched_offline=[r for r in offline if r['case_id'] in matched_ids]
    for campaign,rs in [('offline',offline),('offline_matched',matched_offline),('main',main_rows),('main_v2_preserved',old_main),('adaptive',adaptive_rows),('robust_protocol',robust),('robust_adaptive',robust_adaptive),('robust_adaptive_transport_failed',infra_failed),('typed_roles',typed)]:
        enriched=[enrich(r) for r in rs]
        for r in enriched:r['campaign']=campaign
        detail.extend(enriched)
        for model,method in sorted({(r['model'],r['method']) for r in enriched}):
            selected=[r for r in enriched if (r['model'],r['method'])==(model,method)]
            feasible=[r for r in selected if r['expected_status']=='feasible'];benign=[r for r in selected if r['attack']=='benign']
            item={'n':len(selected),'safe':sum(r['safe_complete'] for r in selected),
                  'ordinary_complete':sum(r['ordinary_complete'] for r in selected),
                  'accepted_but_failed_fresh_inputs':sum(r['accepted'] and not r['safe_complete'] for r in selected),
                  'invalid_attempts':dict(sum((collections.Counter(r['invalid_attempts']) for r in selected),collections.Counter())),
                  'normalized_attempts':sum(r['normalized_attempts'] for r in selected),
                  'feasible_n':len(feasible),'feasible_safe':sum(r['safe_complete'] for r in feasible),
                  'benign_n':len(benign),'benign_failed':sum(not r['safe_complete'] for r in benign),
                  'unauthorized_episodes':sum(r['unauthorized'] for r in selected),
                  'disclosure_episodes':sum(r['disclosure'] for r in selected),
                  'duplicate_episodes':sum(bool(r['duplicate_effects']) for r in selected),
                  'zero_api_episodes':sum(r['request_attempts']==0 for r in selected),
                  'request_attempts':sum(r['request_attempts'] for r in selected),
                  'interrupted_unknown_requests':sum(r['interrupted_unknown_requests'] for r in selected),
                  'api_upper_usd':sum(r['api_upper_usd'] for r in selected),
                  'search_cpu_seconds':sum(r['search_cpu_seconds'] for r in selected),
                  'search_seconds_median':statistics.median(r['search_seconds'] for r in selected),
                  'search_executions':sum(r['search_executions'] for r in selected),
                  'search_steps':sum(r['search_steps'] for r in selected),
                  'search_tool_calls':sum(r['search_tool_calls'] for r in selected),
                  'final_executions':sum(r['final_executions'] for r in selected),
                  'final_steps':sum(r['final_steps'] for r in selected),
                  'final_tool_calls':sum(r['final_tool_calls'] for r in selected),
                  'input_tokens':sum(r['input_tokens'] for r in selected),
                  'output_tokens':sum(r['output_tokens'] for r in selected),
                  'terminations':dict(collections.Counter(r['termination'] for r in selected)),
                  'safe_by_replicate':{str(i):sum(r['safe_complete'] for r in selected if r['replicate']==i) for i in sorted({r['replicate'] for r in selected})}}
            groups[campaign+'|'+model+'|'+method]=item
    comparisons={}
    for campaign,model in [(c,m) for c in ('main','robust_protocol','typed_roles') for m in ('gpt-6-luna','gpt-4.1-mini')]:
        rs=[r for r in detail if r['campaign']==campaign and r['model']==model]
        full={(r['case_id'],r['replicate']):r for r in rs if r['method']=='contract'}
        for method in sorted({r['method'] for r in rs}-{'contract'}):
            family=collections.defaultdict(list);attack=collections.defaultdict(list);wins=losses=0
            for r in rs:
                if r['method']!=method:continue
                delta=int(full[(r['case_id'],r['replicate'])]['safe_complete'])-int(r['safe_complete'])
                family[r['family']].append(delta);attack[r['attack']].append(delta)
                wins+=delta==1;losses+=delta==-1
            comparisons[campaign+'|'+model+'|contract-minus-'+method]={'family_bootstrap':bootstrap(family),
                'attack_bootstrap_sensitivity':{**bootstrap(attack),'estimand':'Equal weight per attack type; a different estimand from equal task-family weighting.'},'paired_wins':wins,'paired_losses':losses}
        compiler={r['case_id']:r for r in detail if r['campaign']=='offline_matched' and r['method']=='goal_direct'}
        family=collections.defaultdict(list)
        for r in full.values():family[r['family']].append(int(r['safe_complete'])-int(compiler[r['case_id']]['safe_complete']))
        comparisons[campaign+'|'+model+'|contract-minus-goal_direct']={'family_bootstrap':bootstrap(family),
            'note':'Same 24 cases. Compiler evaluated once per case; repeated pairing adds no compiler observations.'}
    mechanisms={}
    for r in detail:
        key='|'.join(r[k] for k in ('campaign','model','method','attack'))
        entry=mechanisms.setdefault(key,{'n':0,'safe':0,'accepted':0,'request_attempts':0})
        entry['n']+=1;entry['safe']+=r['safe_complete'];entry['accepted']+=r['accepted'];entry['request_attempts']+=r['request_attempts']
    codes=collections.defaultdict(collections.Counter)
    for campaign,rows in [('main',main_rows),('adaptive',adaptive_rows),('robust_protocol',robust),('robust_adaptive',robust_adaptive),('typed_roles',typed)]:
        for r in rows:
            key='|'.join([campaign,r['model'],r['method']])
            for attempt in r['attempts']:
                ce=attempt.get('validation',{}).get('counterexample')
                if ce:codes[key][ce['code']]+=1
    a=read(D/'provenance/budget_authorization.json');total=sum(x.get('cost_usd',x['reserved_usd']) for x in ledger.values())
    hashes=[h for r in detail if r['campaign'] in {'main','adaptive','robust_protocol','robust_adaptive','typed_roles'} for h in r['request_hashes']]
    if len(hashes)!=len(set(hashes)):raise ValueError('SHARED_REQUEST_ACROSS_EPISODES')
    report={'groups':groups,'comparisons':comparisons,'mechanisms':mechanisms,'counterexamples':dict(codes),
            'budget':{'inherited_upper_usd':a['inherited_upper_usd'],'new_upper_usd':total-a['inherited_upper_usd'],
                      'new_limit_usd':20,'remaining_usd':a['cumulative_cap_usd']-total,'invoice':False},
            'distinct_main_adaptive_requests':len(hashes),'all_raw_requests_including_pilots_and_superseded':len(raw),
            'raw_status_counts':dict(collections.Counter(r['status'] for r in raw.values())),
            'normalized_adaptive_network_rerun':{'original_transport_failed_episodes':len(infra_failed),'whole_grid_rerun_episodes':len(robust_adaptive),'original_costs_retained':True},
            'main_provenance':{'unchanged_v2_episodes':1008,'entire_unknown_stratum_rerun_episodes':144,
                               'note':'Reused episodes are not new independent observations; v2 retained separately. Budget includes superseded requests.'},
            'interpretation':'All methods gated by common checks; zero new unauthorized effects is not evidence of repair-model robustness. Prior disclosure remains scored. Repeated inputs/secret worlds are not independent samples.'}
    catalogue=[read(p) for p in (D/'reference_catalogue').glob('*--*.json')]
    report['catalogue_preparation']={'programs':len(catalogue),'accepted':sum(r['accepted'] for r in catalogue),
        'search_executions':sum(r['search_cost']['executions'] for r in catalogue),
        'search_steps':sum(r['search_cost']['steps'] for r in catalogue),
        'search_tool_calls':sum(r['search_cost']['tool_calls'] for r in catalogue),
        'search_cpu_seconds':sum(r['search_cpu_seconds'] for r in catalogue),
        'note':'Preparation is additional to reported catalogue online lookup/validation cost; final evaluation cost is separate.'}
    report['adaptive_selection_cost']={'queries':len(adaptive['queries']),
        'target':adaptive['target'],
        **{kind:{metric:sum(r[kind][metric] for r in adaptive['queries']) for metric in ('executions','steps','tool_calls')}
           for kind in ('query_cost','certification_cost')}}
    stress=read(D/'results/stress_inputs/summary.json');stress_groups={}
    for r in stress['records']:
        key=r['model']+'|'+r['method'];entry=stress_groups.setdefault(key,{'accepted':0,'primary_safe':0,'stress_safe':0,'additional_failures':0})
        entry['accepted']+=1;entry['primary_safe']+=r['primary_safe'];entry['stress_safe']+=r['evaluation']['safe_complete']
        entry['additional_failures']+=r['primary_safe'] and not r['evaluation']['safe_complete']
    report['stress_inputs']={'accepted':stress['accepted_programs'],'seeds':stress['seeds'],'groups':stress_groups,
        'cost':{metric:sum(r['cost'][metric] for r in stress['records']) for metric in ('executions','steps','tool_calls')}}
    save(D/'analysis/summary.json',report);save(D/'analysis/episodes.json',detail)
    with (D/'analysis/episodes.csv').open('w',newline='',encoding='utf-8') as f:
        columns=[k for k in detail[0] if k not in {'invalid_attempts','request_hashes'}]
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(detail)
    print(json.dumps({'groups':groups,'budget':report['budget']},indent=2))


if __name__=='__main__':main()
