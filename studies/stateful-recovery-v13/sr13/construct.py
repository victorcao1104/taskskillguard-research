"""Residual-effect lowering and a deliberately strong source-free comparator."""
from copy import deepcopy
from .contracts import build,observe


def uses(a):
    op=a.get('op')
    if op in {'copy','filter','project','sort','aggregate','derive','write','send'}:return {a['src']}
    if op in {'join','concat'}:return {a['left'],a['right']}
    if op=='if':return {a['var']}
    return set()


def _slice(seq,needed=None,reusable=frozenset()):
    live=set(needed or []);out=[]
    for a in reversed(seq):
        op=a.get('op');b=deepcopy(a)
        if op=='if':
            left,l=_slice(a.get('then',[]),live,reusable);right,r=_slice(a.get('else',[]),live,reusable)
            if left or right:
                b['then']=left;b['else']=right;out.append(b);live=l|r|{a['var']}
            continue
        if op=='retry':
            body,l=_slice(a.get('body',[]),live,reusable)
            if body:b['body']=body;out.append(b);live=l
            continue
        name=a.get('out')
        if name in reusable:continue
        needed_effect=op in {'write','send','delete'}
        if needed_effect or (name is not None and name in live):
            out.append(b);live.discard(name);live|=uses(a)
    return list(reversed(out)),live


def construct(program,case,inputs,*,omit=None):
    contract=build(case,inputs,omit=omit);t=case['task'];obs=observe(case,inputs);changes=[]
    tainted=set();counter=0
    def lower(seq):
        nonlocal counter
        out=[]
        for original in seq:
            a=deepcopy(original);op=a.get('op')
            bad=(op=='read' and (a.get('path') in t.get('secret_paths',[]) or a.get('path') not in t['grants']['read'])) or bool(uses(a)&tainted)
            if a.get('out'):
                if bad:tainted.add(a['out'])
                else:tainted.discard(a['out'])
            if op=='if':
                if omit!='dependency' and a['var'] in tainted:
                    changes.append('sever_untrusted_condition');out+=lower(a.get('then',[]))+lower(a.get('else',[]))
                else:
                    a['then']=lower(a.get('then',[]));a['else']=lower(a.get('else',[]));out.append(a)
                continue
            if op=='retry':a['body']=lower(a['body']);out.append(a);continue
            if omit!='residual':
                if op=='write' and (a.get('path')!=t['artifact'] or contract.get('artifact_verified')):
                    changes.append('remove_completed_or_irrelevant_write');continue
                if op=='delete' and (a.get('path') not in t.get('cleanup',[]) or a.get('path') not in obs['files']):
                    changes.append('remove_completed_or_irrelevant_delete');continue
            if op=='send' and omit!='history':
                d=a.get('delivery')
                if d in contract['confirmed_deliveries']:
                    changes.append('remove_confirmed_send');continue
                if d in contract['must_query']:
                    counter+=1;v='_receipt_'+str(counter)
                    out.append({'op':'retry','retries':2,'body':[{'op':'status','delivery':d,'out':v}]})
                    out.append({'op':'if','var':v,'equals':'not_sent',
                                'then':[{'op':'retry','retries':2,'body':[a]}],'else':[]})
                    changes.append('guard_uncertain_send');continue
            if op in {'write','send','delete','status','read'}:
                out.append({'op':'retry','retries':2,'body':[a]})
            else:out.append(a)
        return out
    result=lower(program)
    if omit!='dependency':
        reuse=set(contract.get('reusable_result_variables',[])) if omit!='residual' else set()
        result,_=_slice(result,reusable=reuse);changes.append('backward_slice')
    return {'program':result,'changes':changes,'contract':contract}


def from_task(case,inputs,*,state_aware=True):
    """Compile a declarative table query; no Skill/source or case-name dispatch."""
    t=case['task'];q=t['query'];p=[{'op':'read','path':t['source'],'out':'v0'}];v='v0';i=0
    def add(op):
        nonlocal i,v
        i+=1;new='v'+str(i);p.append({**op,'out':new});v=new
    if q.get('join'):
        j=q['join'];p.append({'op':'read','path':j['source'],'out':'right_input'})
        add({'op':'join','left':v,'right':'right_input','on':j['on']})
    for f in q.get('where',[]):add({'op':'filter','src':v,**f})
    for f in q.get('computed',[]):add({'op':'derive','src':v,**f})
    if q.get('metrics'):add({'op':'aggregate','src':v,'group_by':q.get('group_by',[]),'metrics':q['metrics']})
    if q.get('columns'):add({'op':'project','src':v,'fields':q['columns']})
    if q.get('order_by'):add({'op':'sort','src':v,'fields':q['order_by']})
    p.append({'op':'write','path':t['artifact'],'src':v})
    p.extend({'op':'send','delivery':d['id'],'to':d['to'],'src':v} for d in t['deliveries'])
    p.extend({'op':'delete','path':path} for path in t.get('cleanup',[]))
    if not state_aware:return p
    # The strong comparator shares receipt handling. It need not retain source names.
    c=build(case,inputs)
    if c['reusable_result_variables']:
        src=c['reusable_result_variables'][0]
        p=[{'op':'copy','src':src,'out':v}]+[a for a in p if a['op'] in {'write','send','delete'}]
    return construct(p,case,inputs)['program']
