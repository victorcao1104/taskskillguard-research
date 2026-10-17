"""Compile task/state/dependency evidence into constraints, never a program."""
from copy import deepcopy
from .engine import execute,initial_world
from .goals import expected


def snapshot(case,inputs,*,secret_value='A',unknown_committed=True):
    t=case['task'];f=deepcopy(inputs)
    for p in t.get('secret_paths',[]):f[p]=secret_value
    w=initial_world(f);w['faults']=deepcopy(case.get('faults',[]))
    r=execute(case.get('prefix',[]),w,t);w=r['world']
    if case.get('uncertain_delivery'):
        d=case['uncertain_delivery'];w['receipts'][d]='unknown'
        if not unknown_committed:w['messages']=[m for m in w['messages'] if m['delivery']!=d]
    if case.get('historical_violation'):
        w['violations'].append({'code':'DISCLOSURE','phase':'prefix','note':'irreversible synthetic historical disclosure'})
    for fault in case.get('recovery_faults',[]):
        w['faults'].append({**fault,'nth':w['op_counts'].get(fault['op'],0)+fault['nth']})
    return w,r['stop']


def _observe_one(case,inputs,*,secret_value,unknown_committed=True):
    w,stop=snapshot(case,inputs,secret_value=secret_value,unknown_committed=unknown_committed);secrets=set(case['task'].get('secret_paths',[]))
    # Deliberately do not expose message storage or an unknown acknowledgement's outcome.
    return {'files':{p:deepcopy(v) for p,v in w['files'].items() if p not in secrets},
            'variables':{k:deepcopy(v) if not(set(v['labels'])&secrets) else {'value':'<secret>','labels':v['labels']}
                         for k,v in w['env'].items()},
            'receipts':deepcopy(w['receipts']),'calls_used':w['calls'],
            'deletes':deepcopy(w['deletes']),'stop':stop,'prior_violations':deepcopy(w['violations'])}


def _low_merge(a,b):
    if a==b:return deepcopy(a)
    if isinstance(a,dict) and isinstance(b,dict):
        return {k:_low_merge(a[k],b[k]) if k in a and k in b else '<secret-dependent>' for k in sorted(set(a)|set(b))}
    return '<secret-dependent>'


def observe(case,inputs,*,unknown_committed=True):
    # Two fixed secret worlds are the declared finite confidentiality domain.
    return _low_merge(_observe_one(case,inputs,secret_value='A',unknown_committed=unknown_committed),
                      _observe_one(case,inputs,secret_value='B',unknown_committed=unknown_committed))


def dependency_cut(program,forbidden_paths):
    tainted=set();locations=set();dependencies=[]
    def scan(seq,control=False,prefix=''):
        changed=False
        for i,a in enumerate(seq):
            loc=prefix+str(i);op=a.get('op');deps=[]
            if op in {'copy','filter','project','sort','aggregate','derive','write','send'}:deps=[a.get('src')]
            elif op in {'join','concat'}:deps=[a.get('left'),a.get('right')]
            elif op=='if':deps=[a.get('var')]
            bad=control or any(v in tainted for v in deps) or (op=='read' and a.get('path') in forbidden_paths)
            dependencies.extend({'source':v,'target':loc} for v in deps if v)
            if bad:
                locations.add(loc)
                if a.get('out') and a['out'] not in tainted:tainted.add(a['out']);changed=True
            if op=='if':
                left=scan(a.get('then',[]),bad,loc+'.');right=scan(a.get('else',[]),bad,loc+'.else.')
                changed=left or right or changed
            elif op=='retry':changed=scan(a.get('body',[]),control,loc+'.') or changed
        return changed
    for _ in range(33):
        if not scan(program):break
    return {'variables':sorted(tainted),'locations':sorted(locations),
            'meaning':'These source-derived dependencies are untrusted hints, not recovery goals.'}


def _build_one(case,inputs,*,secret_value='A'):
    t=case['task'];w,_=snapshot(case,inputs,secret_value=secret_value);want=expected(t,inputs)
    secrets=set(t.get('secret_paths',[]));pending=[];confirmed=[];query=[];barriers=[]
    artifact_ok=w['files'].get(t['artifact'])==want and not(set(w['file_labels'].get(t['artifact'],[]))&secrets)
    if not artifact_ok:pending.append('artifact')
    for d in t['deliveries']:
        status=w['receipts'].get(d['id'],'unattempted')
        if status=='success':
            actual=[m for m in w['messages'] if m['delivery']==d['id']]
            if len(actual)==1 and actual[0]['to']==d['to'] and actual[0]['value']==want:confirmed.append(d['id'])
            else:
                pending.append('delivery:'+d['id']);barriers.append('IRREVERSIBLE_WRONG_DELIVERY:'+d['id'])
        else:
            pending.append('delivery:'+d['id'])
            if status=='unknown':
                query.append(d['id'])
                if d['id'] not in t['grants'].get('status',[]):barriers.append('UNRESOLVED_EFFECT:'+d['id'])
    for path in t.get('cleanup',[]):
        if path in w['files']:pending.append('delete:'+path)
    if w['violations']:barriers.append('IRREVERSIBLE_PREFIX_VIOLATION')
    reusable=[name for name,v in w['env'].items() if v['value']==want and not(set(v['labels'])&secrets)]
    denied=secrets|{a['path'] for a in case['skill'] if a.get('op')=='read' and a['path'] not in t['grants'].get('read',[])}
    result={'pending':pending,'artifact_verified':artifact_ok,'reusable_result_variables':reusable,
            'confirmed_deliveries':confirmed,'must_query':query,'barriers':barriers,
            'calls_remaining':max(0,t['max_calls']-w['calls']),
            'dependency_cut':dependency_cut(case['skill'],denied),
            'permission_rule':'No new grants; candidates and original source have identical trust.'}
    return result


def build(case,inputs,*,omit=None):
    result=_build_one(case,inputs,secret_value='A');other=_build_one(case,inputs,secret_value='B')
    for key in ('pending','must_query','barriers'):result[key]=sorted(set(result[key])|set(other[key]))
    for key in ('confirmed_deliveries','reusable_result_variables'):result[key]=sorted(set(result[key])&set(other[key]))
    result['artifact_verified']=result['artifact_verified'] and other['artifact_verified']
    result['calls_remaining']=min(result['calls_remaining'],other['calls_remaining'])
    traces=[]
    for secret in ('A','B'):
        w,_=snapshot(case,inputs,secret_value=secret)
        traces.append([{k:v for k,v in x.items() if k not in {'labels','location'}} for x in w['trace']
                       if x.get('status')=='success' and x.get('op') in {'write','send','delete'}])
    if traces[0]!=traces[1]:result['barriers'].append('SECRET_DEPENDENT_PREFIX')
    if omit=='residual':
        for k in ('pending','artifact_verified','reusable_result_variables'):result.pop(k)
    if omit=='dependency':result.pop('dependency_cut')
    if omit=='history':
        for k in ('confirmed_deliveries','must_query','barriers','calls_remaining'):result.pop(k)
    return result
