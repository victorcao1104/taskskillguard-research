"""Task-scoped finite gateway. All effects are in-memory; source never runs natively."""
from collections import Counter
from copy import deepcopy
from adapter import compile_bundle, compile_script, Unsupported

MODES=('observe','scope','flow','first','cost')
FAULTS=('none','transient_before','known_after','ambiguous_after')

class Stop(Exception): pass

def goal_met(files,emits,goal,initial):
    counts=Counter((e['resource'],e['value']) for e in emits)
    return (all(files.get(p)==v and p in files for p,v in goal.get('files',{}).items())
      and all(p not in files for p in goal.get('absent',[]))
      and all(counts[e['resource'],e['value']]==e['count'] for e in goal.get('emits',[]))
      and all(files.get(p)==initial.get(p) and (p in files)==(p in initial) for p in goal.get('preserve',[])))

class Machine:
    def __init__(self,world,quota=16,scope=True,flow=True,reuse=True,fault='none',suppress=None):
        self.files=deepcopy(world['files']);self.initial=deepcopy(self.files)
        self.grants={tuple(g) for g in world.get('grants',[])}
        self.limits=deepcopy(world.get('limits',{}));self.uses=Counter()
        self.readers=deepcopy(world.get('readers',{}))
        self.labels={p:({p} if p in self.readers else set()) for p in self.files}
        self.quota=quota;self.scope=scope;self.flow=flow;self.reuse=reuse;self.fault=fault;self.fault_used=False
        self.suppress={suppress} if isinstance(suppress,str) else set(suppress or [])
        self.emits=[];self.trace=[];self.receipts={};self.commits=Counter()
        self.charged=0;self.steps=0;self.total_steps=0;self.duplicate=0
    def run(self,program,route=0,allowed=None):
        env={};ordinals=Counter();self.steps=0
        def value(expr):
            if not isinstance(expr,dict):return expr,set()
            if 'var' in expr:
                if expr['var'] not in env:raise Stop('unbound_variable')
                v,t=env[expr['var']];return v,set(t)
            if 'upper' in expr:
                v,t=value(expr['upper'])
                if not isinstance(v,str):raise Stop('nonstring_upper')
                return v.upper(),t
            parts=[value(e) for e in expr['concat']]
            if any(not isinstance(v,str) for v,t in parts):raise Stop('nonstring_add')
            return ''.join(v for v,t in parts),set().union(*(t for v,t in parts))
        def walk(steps,pc=frozenset()):
            for s in steps:
                if self.steps>=100:raise Stop('step_limit')
                self.steps+=1;self.total_steps+=1
                kind=s['kind']
                if kind=='let':
                    v,t=value(s['value']);env[s['name']]=(v,t|set(pc))
                elif kind=='if':
                    a,ta=value(s['eq'][0]);b,tb=value(s['eq'][1])
                    walk(s['then'] if a==b else s['else'],set(pc)|ta|tb)
                elif kind=='repeat':
                    for _ in range(s['count']):walk(s['body'],pc)
                elif kind=='call':walk(program.get('functions',{})[s['fn']],pc)
                else:
                    if s['id'] in self.suppress:
                        returned,origins='',set(pc)
                    else:
                        resource,rt=value(s['resource']);payload,vt=value(s.get('value',''))
                        if not isinstance(resource,str) or not isinstance(payload,str):raise Stop('nonstring_effect')
                        origins=rt|vt|set(pc)
                        if s['op']=='read':origins=set(self.labels.get(resource,set()))|rt|set(pc)
                        sig=(s['op'],resource,payload);ordinals[sig]+=1;key=(*sig,ordinals[sig])
                        returned,origins=self.effect(s,resource,payload,origins,key,route,allowed)
                    if 'out' in s:env[s['out']]=(returned,origins)
        try:walk(program['steps']);return None
        except Stop as e:return str(e)
    def effect(self,s,resource,payload,origins,key,route,allowed):
        op=s['op'];scope_allowed=(op,resource) in self.grants
        within_limit=self.uses[(op,resource)]<self.limits.get(op+'|'+resource,10**9)
        reused=self.reuse and key in self.receipts
        authorized=scope_allowed and (within_limit or reused)
        flow_allowed=op!='emit' or all(resource in self.readers.get(origin,[]) for origin in origins)
        event={'id':s['id'],'op':op,'resource':resource,'value':payload,'authorized':authorized,
          'flow_allowed':flow_allowed,'origins':sorted(origins),'route':route,'key':list(key),'committed':False,'charged':False}
        deny=('model_gate' if route==0 and allowed is not None and s['id'] not in allowed else
              'scope_denied' if self.scope and not authorized else 'flow_denied' if self.flow and not flow_allowed else None)
        if not deny and self.reuse and key in self.receipts:
            event['status']='receipt_reused';self.trace.append(event)
            v,t=self.receipts[key];return v,set(t)
        if self.charged>=self.quota:
            event['status']='quota_exhausted';self.trace.append(event);raise Stop('quota_exhausted')
        self.charged+=1;event['charged']=True
        self.uses[(op,resource)]+=1
        if deny:event['status']=deny;self.trace.append(event);raise Stop(deny)
        trigger=op!='read' and self.fault!='none' and not self.fault_used
        if trigger:self.fault_used=True
        if trigger and self.fault=='transient_before':
            event['status']='transient_before';self.trace.append(event);raise Stop('transient_before')
        returned=''
        if op=='read':returned=self.files.get(resource,'')
        elif op=='write':self.files[resource]=payload;self.labels[resource]=set(origins)
        elif op=='delete':self.files.pop(resource,None);self.labels.pop(resource,None)
        elif op=='emit':self.emits.append({'resource':resource,'value':payload})
        event['committed']=True
        if op!='read':
            if self.commits[key]:self.duplicate+=1
            self.commits[key]+=1
        if trigger and self.fault=='ambiguous_after':
            event['status']='ambiguous_outcome';self.trace.append(event);raise Stop('ambiguous_outcome')
        self.receipts[key]=(returned,set(origins))
        event['status']='known_after' if trigger and self.fault=='known_after' else 'committed'
        self.trace.append(event)
        if event['status']=='known_after':raise Stop('known_after')
        return returned,set(origins)

def result(m,goal,error,attempts,plans,unsupported=False):
    committed=[e for e in m.trace if e['committed']]
    unauthorized=sum(not e['authorized'] for e in committed)
    forbidden=sum(not e['flow_allowed'] for e in committed)
    achieved=goal_met(m.files,m.emits,goal,m.initial)
    return {'files':m.files,'emits':m.emits,'trace':m.trace,'goal':achieved,'authorized_goal':bool(attempts) and achieved and error is None and not unauthorized and not forbidden,
       'unauthorized_effects':unauthorized,'forbidden_flows':forbidden,'duplicate_effects':m.duplicate,
       'charged_calls':m.charged,'remaining_quota':m.quota-m.charged,'attempts':len(attempts),'attempt_log':attempts,
       'planning_log':plans,'planner_steps':sum(e['steps'] for p in plans for e in p),'simulated_calls':sum(e['calls'] for p in plans for e in p),
       'failure_reason':error,'unsupported':unsupported,'ambiguous_stop':error=='ambiguous_outcome',
       'route_bypass':any(e['route']>0 and e['committed'] for e in m.trace)}

def execute(case,mode,fault='none',allowed_ids=None):
    if mode not in MODES or fault not in FAULTS:raise ValueError('invalid mode/fault')
    quota=case.get('quota',16)
    if type(quota) is not int or quota<0:raise ValueError('invalid quota')
    m=Machine(case['world'],quota,scope=mode!='observe',flow=mode not in ('observe','scope'),fault=fault)
    goal=case['goal'];attempts=[];plans=[]
    try:
        original=compile_bundle(case['bundle'])['program']
        alternatives=[compile_script(r['source'],f'trusted/{i}.py')['program'] for i,r in enumerate(case.get('trusted_routes',[]),1)]
    except Unsupported:
        return result(m,goal,'unsupported',attempts,plans,True)
    programs=[original]+alternatives
    route=0;error=None;available=set(range(1,len(programs)))
    for attempt in range(1,5 if mode in ('first','cost') else 2):
        before=m.charged
        error=m.run(programs[route],route,set(allowed_ids) if allowed_ids is not None else None)
        if error is None and not goal_met(m.files,m.emits,goal,m.initial):error='goal_unmet'
        attempts.append({'route':route,'error':error,'charged_calls':m.charged-before,'steps':m.steps})
        if error is None or error in ('ambiguous_outcome','quota_exhausted') or mode not in ('first','cost'):break
        if attempt==4:break
        eligible=sorted(available|({route} if error in ('transient_before','known_after') else set()))
        evaluations=[]
        for index in eligible:
            p=deepcopy(m);p.fault='none';start=p.charged
            pe=p.run(programs[index],index,set(allowed_ids) if allowed_ids is not None else None)
            ok=pe is None and goal_met(p.files,p.emits,goal,p.initial)
            evaluations.append({'route':index,'feasible':ok,'error':pe,'calls':p.charged-start,'steps':p.steps})
        plans.append(evaluations)
        feasible=[e for e in evaluations if e['feasible']]
        if not feasible:error='no_feasible_route';break
        selected=min(feasible,key=(lambda e:(e['calls'],e['route'])) if mode=='cost' else (lambda e:e['route']))
        route=selected['route'];available.discard(route)
    return result(m,goal,error,attempts,plans)

def run_semantics(program,world,goal,suppress=None):
    m=Machine(world,100,scope=False,flow=False,reuse=False,suppress=suppress)
    error=m.run(program)
    trace=[{k:e[k] for k in ('id','op','resource','value','authorized','flow_allowed','origins')} for e in m.trace if e['committed']]
    return {'files':m.files,'emits':m.emits,'trace':trace,'goal':error is None and goal_met(m.files,m.emits,goal,m.initial),'error':error}
