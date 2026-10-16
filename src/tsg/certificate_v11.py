"""Paid finite evidence, small certificate checker, and public query policies.

The environment supplies the reader capability. Selectors see neither its state
nor an actual world index. Only consume() invokes that capability or the VM.
Evidence is a trusted local store, not JSON accepted from a model.
"""
from copy import deepcopy
import hashlib
import json
import random
from .runtime_v6 import _Machine, _goal, _validate, parse_source, edges, STEP_LIMIT
from .observation_v9 import TrustedObservations, observable_queries, _answer

VM_ID='runtime_v6-guarded-receipts-step100'
POLICIES=('original_first','route_cover','observe_cover','random')

def dump(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(v):return hashlib.sha256(dump(v).encode()).hexdigest()

def public_case(case):
    return deepcopy({k:case[k] for k in ('source','routes','worlds','goal','catalog_closed',
        'observable_files','observable_grants') if k in case})

def make_reader(case,world_index):
    keys=observable_queries(case)
    reader=TrustedObservations(case['worlds'][world_index],
        [q[1] for q in keys if q[0]=='file'],[q[1:] for q in keys if q[0]=='grant'])
    return reader.query

def audit_run(program,world,goal,quota):
    m=_Machine(world,quota,reuse=True,enforce=True)
    try:error=m.run(_validate(program))
    except (ValueError,TypeError,RecursionError):error='parse_error'
    goal_met=error is None and _goal(m.files,m.emits,goal)
    return {'error':error,'goal':goal_met,'safe_success':goal_met and m.unauthorized==0,
        'files':m.files,'emits':m.emits,'trace':m.trace,'charged_calls':m.charged,
        'receipt_reuses':m.reuses,'interpreter_steps':m.steps,'unauthorized_effects':m.unauthorized}

def decide(compatible,route_count,outcomes,separable):
    """Read trusted booleans only. No semantic execution or world selection."""
    checks=0
    if not compatible:return {'status':'observation_mismatch','route':None,'checks':checks}
    for r in range(route_count):
        values=[]
        for w in compatible:
            checks+=1;values.append(outcomes.get((w,r)))
        if all(v is True for v in values):
            return {'status':'certified','route':r,'checks':checks}
    rejected=[]
    for r in range(route_count):
        bad=[]
        for w in compatible:
            checks+=1
            if outcomes.get((w,r)) is False:bad.append(w)
        rejected.append(bool(bad))
    return {'status':'infeasible' if all(rejected) and not separable else 'unknown',
            'route':None,'checks':checks}

class CertificateSession:
    def __init__(self,case,reader,quota=32):
        if type(quota) is not int or quota<0:raise ValueError('INVALID_QUOTA')
        self.case=public_case(case)
        if not self.case['worlds'] or self.case['catalog_closed'] is not True:
            raise ValueError('CLOSED_NONEMPTY_WORLDS_REQUIRED')
        self.programs=[parse_source(case['source']),*deepcopy(case['routes'])]
        for p in self.programs:_validate(p)
        self.quota=quota;self._reader=reader;self._cache={};self._order=[]
        self._compatible=list(range(len(case['worlds'])))
        self._keys=observable_queries(self.case)
        self.catalog=[{'id':f'w{w}r{r}','kind':'run','world':w,'route':r}
            for w in range(len(case['worlds'])) for r in range(len(self.programs))]
        self.catalog += [{'id':f'o{i}','kind':'observe','query':list(k)} for i,k in enumerate(self._keys)]
        self._lookup={q['id']:q for q in self.catalog}
        self.binding=digest({'case':self.case,'quota':quota,'vm':VM_ID})
        self._checks=0;self._observation_comparisons=0;self._check_calls=0

    @property
    def remaining_ids(self):return [q['id'] for q in self.catalog if q['id'] not in self._cache]

    @property
    def observations(self):return deepcopy(self._cache)

    def consume(self,qid):
        if type(qid) is not str or qid not in self.remaining_ids:raise ValueError('INVALID_QUERY_SELECTION')
        q=self._lookup[qid]
        if q['kind']=='run':
            value=audit_run(self.programs[q['route']],self.case['worlds'][q['world']],self.case['goal'],self.quota)
        else:
            answer=self._reader(tuple(q['query']))
            if not isinstance(answer,dict) or type(answer.get('available')) is not bool:
                raise ValueError('MALFORMED_TRUSTED_OBSERVATION')
            value={'answer':deepcopy(answer)}
            if answer['available']:
                key=tuple(q['query'])
                actual=(answer.get('present'),answer.get('value')) if key[0]=='file' else answer.get('value')
                if key[0]=='file' and type(answer.get('present')) is not bool:raise ValueError('MALFORMED_PRESENCE')
                if key[0]=='grant' and type(actual) is not bool:raise ValueError('MALFORMED_GRANT')
                self._observation_comparisons+=len(self._compatible)
                self._compatible=[w for w in self._compatible if _answer(self.case['worlds'][w],key)==actual]
        self._cache[qid]={**value,'query_id':qid,'binding':self.binding}
        self._order.append(qid)

    def _separable(self):
        for q in self.catalog:
            if q['kind']!='observe':continue
            if q['id'] in self._cache and self._cache[q['id']]['answer']['available']:continue
            answers={dump(_answer(self.case['worlds'][w],tuple(q['query']))) for w in self._compatible}
            self._observation_comparisons+=len(self._compatible)
            if len(answers)>1:return True
        return False

    def check(self):
        outcomes={(q['world'],q['route']):self._cache[q['id']]['safe_success']
            for q in self.catalog if q['kind']=='run' and q['id'] in self._cache}
        d=decide(self._compatible,len(self.programs),outcomes,self._separable())
        self._checks+=d['checks'];self._check_calls+=1
        witnesses=([f'w{w}r{d["route"]}' for w in self._compatible] if d['status']=='certified' else [])
        return {**d,'binding':self.binding,'compatible_worlds':list(self._compatible),
            'witnesses':witnesses,'evidence_refs':list(self._order),
            'observation_refs':[q for q in self._order if self._lookup[q]['kind']=='observe'],
            'claim':'safe completion of witnessed route in current finite class, not optimal-route equality'}

    def result(self):
        runs=[self._cache[q] for q in self._order if self._lookup[q]['kind']=='run']
        return {'binding':self.binding,'order':list(self._order),'query_count':len(self._order),
            'interpreter_calls':len(runs),'initial_observation_calls':len(self._order)-len(runs),
            'interpreter_steps':sum(r['interpreter_steps'] for r in runs),
            'audit_effect_calls':sum(r['charged_calls'] for r in runs),
            'certificate_pair_checks':self._checks,'certificate_check_calls':self._check_calls,
            'observation_comparisons':self._observation_comparisons,
            'compatible_worlds':list(self._compatible),'observations':deepcopy(self._cache)}

def verify_certificate(case,trusted_store,certificate,quota=32):
    """Check a serialized positive/negative certificate against a trusted store.

    The store must originate from the trusted query service. Hashes bind content;
    they do not authenticate attacker-controlled execution records. No VM runs.
    """
    try:
        binding=digest({'case':public_case(case),'quota':quota,'vm':VM_ID})
        if certificate['binding']!=binding:return False
        refs=certificate['evidence_refs'];obsrefs=certificate['observation_refs']
        if not isinstance(refs,list) or len(refs)!=len(set(refs)):return False
        if not isinstance(obsrefs,list) or len(obsrefs)!=len(set(obsrefs)):return False
        keys=observable_queries(case);compatible=list(range(len(case['worlds'])))
        outcomes={};seen_observations={}
        for ref in refs:
            rec=trusted_store[ref]
            if rec['binding']!=binding or rec['query_id']!=ref:return False
            if ref.startswith('o'):
                i=int(ref[1:])
                if ref!=f'o{i}' or not 0<=i<len(keys):return False
                answer=rec['answer'];seen_observations[ref]=answer
                if type(answer['available']) is not bool:return False
                if answer['available']:
                    key=keys[i]
                    actual=(answer['present'],answer.get('value')) if key[0]=='file' else answer['value']
                    compatible=[w for w in compatible if _answer(case['worlds'][w],key)==actual]
            else:
                w,r=map(int,ref[1:].split('r'))
                if ref!=f'w{w}r{r}' or not 0<=w<len(case['worlds']) or not 0<=r<=len(case['routes']):return False
                if type(rec['safe_success']) is not bool:return False
                if rec['safe_success'] != (rec['error'] is None and rec['goal'] is True and rec['unauthorized_effects']==0):return False
                outcomes[w,r]=rec['safe_success']
        if obsrefs!=list(seen_observations) or compatible!=certificate['compatible_worlds'] or not compatible:return False
        if certificate['status']=='certified':
            route=certificate['route']
            if type(route) is not int or not 0<=route<=len(case['routes']):return False
            expected=[f'w{w}r{route}' for w in compatible]
            return certificate['witnesses']==expected and all(outcomes.get((w,route)) is True for w in compatible)
        if certificate['status']=='infeasible':
            if certificate['route'] is not None or certificate['witnesses']:return False
            for i,key in enumerate(keys):
                if f'o{i}' in seen_observations and seen_observations[f'o{i}']['available']:continue
                if len({dump(_answer(case['worlds'][w],key)) for w in compatible})>1:return False
            return all(any(outcomes.get((w,r)) is False for w in compatible) for r in range(len(case['routes'])+1))
        return False
    except (KeyError,TypeError,ValueError,IndexError):return False

def _structural_cost(program):
    def cost(steps):
        total=0
        for s in steps:
            total+=1
            if s['kind']=='if':total+=max(cost(s['then']),cost(s['else']))
            elif s['kind']=='repeat':total+=s['count']*cost(s['body'])
            elif s['kind']=='call':total+=cost(program.get('functions',{})[s['fn']])
        return total
    return cost(program['steps'])

def choose_query(session,policy='observe_cover',seed=11101):
    """Only public structure and paid records; never a free interpreter call."""
    if policy not in POLICIES:raise ValueError('UNKNOWN_POLICY')
    remaining=session.remaining_ids
    if not remaining:return None
    if policy=='random':return random.Random(seed+len(session._order)).choice(remaining)
    worlds=session._compatible;cache=session._cache;queries=session._lookup
    if policy=='original_first':
        return min(remaining,key=lambda q:(queries[q]['kind']!='run',queries[q].get('route',0),queries[q].get('world',0),q))
    if policy=='observe_cover' and len(worlds)>1:
        scores=[]
        for qid in remaining:
            q=queries[qid]
            if q['kind']!='observe':continue
            sizes={}
            for w in worlds:
                a=dump(_answer(session.case['worlds'][w],tuple(q['query'])));sizes[a]=sizes.get(a,0)+1
            gain=len(worlds)-sum(v*v for v in sizes.values())/len(worlds)
            if gain>=1:scores.append((-gain,qid))
        if scores:return min(scores)[1]
    ranks=[]
    for r,p in enumerate(session.programs):
        ids=[f'w{w}r{r}' for w in worlds]
        rejected=any(q in cache and not cache[q]['safe_success'] for q in ids)
        missing=[q for q in ids if q not in cache]
        if missing:ranks.append((rejected,len(missing),_structural_cost(p),r,missing[0]))
    viable=[row for row in ranks if not row[0]]
    if viable:return min(viable)[-1]
    # A negative partial table may become feasible after a distinguishing read.
    observes=[q for q in remaining if queries[q]['kind']=='observe']
    if observes:return observes[0]
    return min(ranks)[-1] if ranks else remaining[0]

def run_policy(case,world_index,chooser,budget=12,stop=True,quota=32):
    session=CertificateSession(case,make_reader(case,world_index),quota)
    earliest=None;stop_reason='budget'
    while session.remaining_ids and session.result()['query_count']<budget:
        cert=session.check()
        if cert['status']!='unknown' and earliest is None:earliest=deepcopy(cert)
        if stop and cert['status']!='unknown':stop_reason=cert['status'];break
        q=chooser(session);session.consume(q)
    final=session.check()
    if earliest is None and final['status']!='unknown':earliest=deepcopy(final)
    if not session.remaining_ids:stop_reason='catalog_exhausted'
    return {**session.result(),'certificate':final,'first_certificate':earliest,'stop_reason':stop_reason}

SYSTEM='''Select one paid query to obtain a CHECKED safe-completion certificate with few calls.
Return ONLY {"query_id":"one remaining ID"}. Do not supply facts or explanations.
A run query executes a public world/route in a fresh guarded VM with durable receipt reuse,
quota 32 and step limit 100. It does not reveal which world is actual. An observe query
reads an allowed immutable initial file or grant in the actual world and filters hypotheses.
A certificate requires completed safe_success for ONE SAME route in EVERY compatible world.
Incomplete original labels are irrelevant if an alternate route has that certificate.
Each query costs one. Use only public programs and paid observations; no hidden truth is available.
Graphs are redundant static source edges, padding is inert. Never repeat or invent an ID.
'''

def selection_payload(session,representation='source'):
    if representation not in ('source','graph','padding'):raise ValueError('UNKNOWN_REPRESENTATION')
    value={'public':session.case,'quota':session.quota,'vm':VM_ID,'remaining_ids':session.remaining_ids,
        'queries':[q for q in session.catalog if q['id'] in session.remaining_ids],
        'compatible_worlds':list(session._compatible),'observations':session.observations}
    if representation=='source':return dump(value)
    value['representation']={'kind':'graph','edges_by_route':[edges(p) for p in session.programs]}
    graph=dump(value)
    if representation=='graph':return graph
    # UTF-8 character control only unless token_equal_padding is explicitly used.
    value['representation']={'kind':'padding','inert':''}
    value['representation']['inert']='.'*max(0,len(graph)-len(dump(value)))
    return dump(value)
