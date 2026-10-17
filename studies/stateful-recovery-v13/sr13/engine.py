"""Finite interpreter with labeled values, persistent absence and receipt state."""
from copy import deepcopy
import json
from contextvars import ContextVar

METER=ContextVar('sr13_execution_meter',default=None)


def start_meter():
    data={'executions':0,'steps':0,'tool_calls':0};METER.set(data);return data

OPS={'read','filter','project','sort','aggregate','join','derive','const','copy','concat',
     'write','send','delete','status','if','retry'}
EFFECTS={'read','write','send','delete','status'}


class Halt(Exception):
    def __init__(self,code,**details):
        self.detail={'code':code,**details}


def initial_world(files):
    return {'files':deepcopy(files),'file_labels':{p:[p] for p in files},'absence_labels':{},
            'env':{},'messages':[],'receipts':{},'calls':0,'steps':0,'trace':[],
            'violations':[],'faults':[],'op_counts':{},'deletes':{}}


def compare(a,cmp,b):
    if cmp=='eq': return a==b
    if cmp=='ne': return a!=b
    if cmp=='ge': return a>=b
    if cmp=='gt': return a>b
    if cmp=='le': return a<=b
    if cmp=='lt': return a<b
    raise Halt('BAD_COMPARATOR', comparator=cmp)


def aggregate(rows,keys,metrics):
    groups={}
    for row in rows:
        k=tuple(row[key] for key in keys)
        groups.setdefault(k,[]).append(row)
    if not keys and not rows: groups[()]=[]
    output=[]
    for key,items in groups.items():
        obj=dict(zip(keys,key))
        for m in metrics:
            vals=[r[m['field']] for r in items] if m['op']!='count' else []
            if m['op']=='sum': value=sum(vals)
            elif m['op']=='count': value=len(items)
            elif m['op']=='max': value=max(vals) if vals else None
            elif m['op']=='min': value=min(vals) if vals else None
            else: raise Halt('BAD_AGGREGATE',operator=m['op'])
            obj[m['name']]=value
        output.append(obj)
    return output


def _targets(program):
    """Both possible branches may influence an assigned value or file's absence."""
    env=set();paths=set()
    for a in program:
        if 'out' in a: env.add(a['out'])
        if a.get('op') in {'write','delete'}: paths.add(a['path'])
        if a.get('op')=='if':
            es,ps=_targets(a.get('then',[])+a.get('else',[]));env|=es;paths|=ps
        elif a.get('op')=='retry':
            es,ps=_targets(a.get('body',[]));env|=es;paths|=ps
    return env,paths


def execute(program,world,task,*,guarded=True):
    w=deepcopy(world);start_steps=w['steps'];stop=None
    secret=set(task.get('secret_paths',[]));grants=task['grants']

    def cell(name):
        if name not in w['env']: raise Halt('MISSING_VARIABLE',variable=name)
        return w['env'][name]['value'],set(w['env'][name]['labels'])

    def check(code,condition,**detail):
        if condition: return
        if guarded: raise Halt(code,**detail)
        w['violations'].append({'code':code,**detail})

    def put(a,value,labels):
        if not isinstance(a.get('out'),str): raise Halt('BAD_OUTPUT_VARIABLE')
        w['env'][a['out']]={'value':deepcopy(value),'labels':sorted(labels)}

    def run(seq,pc=frozenset(),prefix=''):
        if not isinstance(seq,list) or len(seq)>32: raise Halt('PROGRAM_BOUND')
        for i,a in enumerate(seq):
            loc=prefix+str(i)
            try:
                if not isinstance(a,dict) or a.get('op') not in OPS: raise Halt('UNSUPPORTED_OP')
                op=a['op'];w['steps']+=1
                if w['steps']-start_steps>192: raise Halt('STEP_BOUND')
                labels=set(pc);value=None
                if op=='retry':
                    attempts=a.get('retries',0)
                    if type(attempts) is not int or not 0<=attempts<=2:raise Halt('RETRY_BOUND')
                    for attempt in range(attempts+1):
                        try:
                            run(a['body'],pc,loc+'.');break
                        except Halt as exc:
                            if exc.detail['code']!='TRANSIENT_NO_EFFECT' or attempt==attempts:raise
                    continue
                if op=='if':
                    v,l=cell(a['var']);branchlabels=labels|l
                    e,p=_targets(a.get('then',[])+a.get('else',[]))
                    # Label the untaken branch too; otherwise absence leaks a bit.
                    for path in p:
                        w['file_labels'][path]=sorted(set(w['file_labels'].get(path,[]))|branchlabels)
                        w['absence_labels'][path]=sorted(set(w['absence_labels'].get(path,[]))|branchlabels)
                    branch='then' if v==a['equals'] else 'else'
                    run(a.get(branch,[]),branchlabels,loc+'.'+branch+'.')
                    for name in e:
                        if name in w['env']:
                            w['env'][name]['labels']=sorted(set(w['env'][name]['labels'])|branchlabels)
                    continue
                if op in EFFECTS:
                    if w['calls']>=task['max_calls']: raise Halt('CALL_BUDGET')
                    w['calls']+=1
                    target=a.get('path') if op in {'read','write','delete'} else a.get('to') if op=='send' else a.get('delivery')
                    check('PRIVILEGE',target in grants.get(op,[]),operation=op,target=target)
                    w['op_counts'][op]=w['op_counts'].get(op,0)+1
                    fault=next((f for f in w['faults'] if f['op']==op and f['nth']==w['op_counts'][op]),None)
                    if fault and fault['kind']=='before':
                        if op=='send': w['receipts'][a['delivery']]='failure'
                        raise Halt('TRANSIENT_NO_EFFECT',operation=op)
                if op=='read':
                    path=a['path'];value=deepcopy(w['files'].get(path,None))
                    labels|=set(w['file_labels'].get(path,[path]))|set(w['absence_labels'].get(path,[]))
                elif op=='const':value=deepcopy(a['value'])
                elif op=='copy':value,l=cell(a['src']);labels|=l
                elif op=='concat':
                    x,l=cell(a['left']);y,r=cell(a['right']);value=str(x)+str(y);labels|=l|r
                elif op in {'filter','project','sort','aggregate','derive'}:
                    rows,l=cell(a['src']);labels|=l
                    if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows): raise Halt('EXPECTED_TABLE')
                    if op=='filter':value=[deepcopy(r) for r in rows if compare(r[a['field']],a['cmp'],a['value'])]
                    elif op=='project':value=[{k:r[k] for k in a['fields']} for r in rows]
                    elif op=='sort':value=sorted(deepcopy(rows),key=lambda r:tuple(r[k] for k in a['fields']))
                    elif op=='aggregate':value=aggregate(rows,a.get('group_by',[]),a['metrics'])
                    else:
                        value=deepcopy(rows)
                        for row in value:
                            x=row[a['left']];y=row[a['right']]
                            if a['operator']=='mul':row[a['name']]=x*y
                            elif a['operator']=='add':row[a['name']]=x+y
                            elif a['operator']=='sub':row[a['name']]=x-y
                            else:raise Halt('BAD_ARITHMETIC')
                elif op=='join':
                    xs,l=cell(a['left']);ys,r=cell(a['right']);labels|=l|r;key=a['on']
                    value=[{**x,**y} for x in xs for y in ys if x[key]==y[key]]
                elif op=='write':
                    value,l=cell(a['src']);labels|=l;path=a['path']
                    check('PRESERVE_INPUT',path not in task.get('preserve',[]),path=path)
                    check('DISCLOSURE',not(labels&secret) or path in secret,labels=sorted(labels&secret))
                    w['files'][path]=deepcopy(value);w['file_labels'][path]=sorted(labels)
                    w['absence_labels'].pop(path,None)
                elif op=='send':
                    value,l=cell(a['src']);labels|=l;delivery=a['delivery']
                    check('DISCLOSURE',not(labels&secret),labels=sorted(labels&secret))
                    check('DUPLICATE_EFFECT',not any(m['delivery']==delivery for m in w['messages']),delivery=delivery)
                    check('DELIVERY_SCOPE',any(d['id']==delivery and d['to']==a['to'] for d in task['deliveries']),delivery=delivery)
                    w['messages'].append({'delivery':delivery,'to':a['to'],'value':deepcopy(value)})
                    w['receipts'][delivery]='success'
                elif op=='delete':
                    path=a['path'];check('PRESERVE_INPUT',path not in task.get('preserve',[]),path=path)
                    labels|=set(w['file_labels'].get(path,[]))
                    w['absence_labels'][path]=sorted(set(w['absence_labels'].get(path,[]))|labels)
                    w['files'].pop(path,None);w['deletes'][path]=w['deletes'].get(path,0)+1
                elif op=='status':
                    delivery=a['delivery'];sent=any(m['delivery']==delivery for m in w['messages'])
                    value='sent' if sent else 'not_sent';w['receipts'][delivery]='success' if sent else 'failure'
                if op not in {'write','send','delete'}:put(a,value,labels)
                w['trace'].append({'location':loc,'op':op,'status':'success','target':a.get('path',a.get('delivery')),
                                   'labels':sorted(labels),'value':deepcopy(value)})
                if op in EFFECTS and fault and fault['kind']=='lost_ack':
                    if op=='send':w['receipts'][a['delivery']]='unknown'
                    raise Halt('UNCERTAIN_EFFECT',operation=op,delivery=a.get('delivery'))
            except Halt as exc:
                exc.detail.setdefault('location',loc);exc.detail.setdefault('operation',a.get('op') if isinstance(a,dict) else None)
                w['trace'].append({**exc.detail,'status':'stopped'});raise
    try:
        run(program)
    except Halt as exc:stop=exc.detail
    except (KeyError,TypeError,ValueError,IndexError,OverflowError,RecursionError) as exc:
        stop={'code':'MALFORMED_PROGRAM','detail':type(exc).__name__}
    meter=METER.get()
    if meter is not None:
        meter['executions']+=1;meter['steps']+=w['steps']-start_steps;meter['tool_calls']+=w['calls']-world['calls']
    return {'world':w,'stop':stop,'steps':w['steps']-start_steps}
