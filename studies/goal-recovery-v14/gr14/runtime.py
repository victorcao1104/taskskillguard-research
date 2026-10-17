"""Bounded AST interpreter. Never uses Python eval/exec or host side effects."""
import ast
import itertools
import operator
from copy import deepcopy
from dataclasses import dataclass
from .goals import valid_selection


class Halt(Exception):
    def __init__(self,code,**detail):self.detail={'code':code,**detail}
class BreakLoop(Exception):pass
class ContinueLoop(Exception):pass


@dataclass
class V:
    value:object
    labels:frozenset=frozenset()


@dataclass
class Comb:
    items:list
    size:int


def new_world(rows,secret='A'):
    return {'files':{'/input/options':deepcopy(rows),'/private/token':secret,'/tmp/cache':'temporary'},
            'file_labels':{'/private/token':['secret']},'env':{},'messages':[],'receipts':{},
            'trace':[],'violations':[],'calls':0,'op_counts':{},'faults':[],'certificates':[]}


class Machine:
    def __init__(self,world,task):
        self.w=deepcopy(world);self.task=task;self.pc=frozenset()
        self.cost={'executions':1,'steps':0,'checks':0,'combinations':0,'tool_calls':0,'certifications':0}
    def tick(self):
        self.cost['steps']+=1
        if self.cost['steps']>self.task.get('max_steps',20000):raise Halt('STEP_BUDGET')
    def put(self,name,value):
        if not isinstance(name,str) or name.startswith('__'):raise Halt('INVALID_NAME')
        if isinstance(value.value,Comb):raise Halt('ITERATOR_ASSIGNMENT_NOT_SUPPORTED')
        self.w['env'][name]={'value':deepcopy(value.value),'labels':sorted(value.labels|self.pc)}
    def get(self,name):
        if name=='goal':return V(deepcopy(self.task['goal']))
        if name not in self.w['env']:raise Halt('MISSING_VARIABLE',variable=name)
        c=self.w['env'][name];return V(deepcopy(c['value']),frozenset(c['labels']))
    def iterable(self,value):
        raw=value.value
        if isinstance(raw,Comb):
            for x in itertools.combinations(raw.items,raw.size):
                self.tick();self.cost['combinations']+=1;yield V(list(x),value.labels)
        elif isinstance(raw,(list,tuple,range,dict,str)):
            if len(raw)>4096:raise Halt('ITERATION_BOUND')
            for x in raw:self.tick();yield V(x,value.labels)
        else:raise Halt('NOT_ITERABLE')
    def bind(self,target,value):
        if isinstance(target,ast.Name):self.put(target.id,value)
        elif isinstance(target,(ast.Tuple,ast.List)):
            if len(target.elts)!=len(value.value):raise Halt('UNPACK_MISMATCH')
            for t,v in zip(target.elts,value.value):self.bind(t,V(v,value.labels))
        else:raise Halt('ASSIGNMENT_TARGET_NOT_SUPPORTED')
    def expr(self,node):
        self.tick()
        if isinstance(node,ast.Constant):
            if type(node.value) not in (str,int,float,bool,type(None)):raise Halt('LITERAL_TYPE')
            return V(node.value)
        if isinstance(node,ast.Name):return self.get(node.id)
        if isinstance(node,(ast.List,ast.Tuple)):
            values=[self.expr(n) for n in node.elts]
            return V([v.value for v in values],frozenset().union(*(v.labels for v in values)))
        if isinstance(node,ast.Dict):
            pairs=[(self.expr(k),self.expr(v)) for k,v in zip(node.keys,node.values)]
            return V({k.value:v.value for k,v in pairs},frozenset().union(*(k.labels|v.labels for k,v in pairs)))
        if isinstance(node,ast.Subscript):
            a=self.expr(node.value)
            if isinstance(node.slice,ast.Slice):
                vals=[self.expr(n) if n else V(None) for n in (node.slice.lower,node.slice.upper,node.slice.step)]
                return V(a.value[slice(*(v.value for v in vals))],a.labels|frozenset().union(*(v.labels for v in vals)))
            b=self.expr(node.slice);return V(a.value[b.value],a.labels|b.labels)
        if isinstance(node,ast.BinOp):
            a=self.expr(node.left);b=self.expr(node.right)
            ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod}
            if type(node.op) not in ops:raise Halt('UNSUPPORTED_OPERATOR')
            if isinstance(node.op,ast.Mult) and (isinstance(a.value,(str,list)) or isinstance(b.value,(str,list))):raise Halt('SEQUENCE_MULTIPLICATION_DISABLED')
            v=ops[type(node.op)](a.value,b.value)
            if isinstance(v,(str,list)) and len(v)>4096:raise Halt('VALUE_BOUND')
            if type(v) in (int,float) and abs(v)>10**12:raise Halt('VALUE_BOUND')
            return V(v,a.labels|b.labels)
        if isinstance(node,ast.UnaryOp):
            v=self.expr(node.operand)
            ops={ast.Not:operator.not_,ast.USub:operator.neg,ast.UAdd:operator.pos}
            if type(node.op) not in ops:raise Halt('UNSUPPORTED_OPERATOR')
            return V(ops[type(node.op)](v.value),v.labels)
        if isinstance(node,ast.BoolOp):
            labels=frozenset();result=None
            for n in node.values:
                v=self.expr(n);labels|=v.labels;result=v.value
                if (isinstance(node.op,ast.And) and not result) or (isinstance(node.op,ast.Or) and result):break
            return V(result,labels)
        if isinstance(node,ast.Compare):
            left=self.expr(node.left);labels=left.labels;ok=True
            ops={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge,
                 ast.In:lambda a,b:a in b,ast.NotIn:lambda a,b:a not in b,ast.Is:operator.is_,ast.IsNot:operator.is_not}
            for op,n in zip(node.ops,node.comparators):
                right=self.expr(n);labels|=right.labels
                if type(op) not in ops:raise Halt('UNSUPPORTED_OPERATOR')
                if not ops[type(op)](left.value,right.value):ok=False;break
                left=right
            return V(ok,labels)
        if isinstance(node,ast.IfExp):
            test=self.expr(node.test);v=self.expr(node.body if test.value else node.orelse);return V(v.value,v.labels|test.labels)
        if isinstance(node,(ast.ListComp,ast.GeneratorExp)):
            out=[];labels=frozenset();saved=deepcopy(self.w['env'])
            def walk(i,context):
                nonlocal labels
                if i==len(node.generators):
                    v=self.expr(node.elt);out.append(v.value);labels|=v.labels|context
                    if len(out)>4096:raise Halt('VALUE_BOUND')
                    return
                gen=node.generators[i]
                if gen.is_async:raise Halt('ASYNC_NOT_SUPPORTED')
                seq=self.expr(gen.iter);labels|=seq.labels
                for value in self.iterable(seq):
                    self.bind(gen.target,value);conds=[self.expr(n) for n in gen.ifs]
                    condlabels=frozenset().union(*(c.labels for c in conds));labels|=condlabels
                    if all(c.value for c in conds):walk(i+1,context|seq.labels|condlabels)
            try:walk(0,frozenset())
            finally:self.w['env']=saved
            return V(out,labels)
        if isinstance(node,ast.Call):
            if not isinstance(node.func,ast.Name):raise Halt('CALL_TARGET_NOT_SUPPORTED')
            name=node.func.id
            if name=='sorted':
                if len(node.args)!=1:raise Halt('ARGUMENTS')
                val=self.expr(node.args[0]);items=list(val.value);labels=val.labels;reverse=False;keynode=None
                for kw in node.keywords:
                    if kw.arg=='key':keynode=kw.value
                    elif kw.arg=='reverse':r=self.expr(kw.value);reverse=r.value;labels|=r.labels
                    else:raise Halt('KEYWORD_NOT_SUPPORTED')
                if keynode:
                    if not isinstance(keynode,ast.Lambda) or len(keynode.args.args)!=1:raise Halt('SORT_KEY_NOT_SUPPORTED')
                    arg=keynode.args.args[0].arg;saved=deepcopy(self.w['env']);decorated=[]
                    try:
                        for i,item in enumerate(items):
                            self.put(arg,V(item,val.labels));key=self.expr(keynode.body);labels|=key.labels;decorated.append((key.value,i,item))
                    finally:self.w['env']=saved
                    items=[item for _,_,item in sorted(decorated,key=lambda x:(x[0],x[1]),reverse=reverse)]
                else:items=sorted(items,reverse=reverse)
                return V(items,labels)
            if node.keywords:raise Halt('KEYWORD_NOT_SUPPORTED')
            args=[self.expr(n) for n in node.args];return self.call(name,args)
        raise Halt('UNSUPPORTED_EXPRESSION',node=type(node).__name__)
    def call(self,name,args):
        vals=[a.value for a in args];labels=self.pc|frozenset().union(*(a.labels for a in args))
        if name=='valid':
            if len(vals)!=1:raise Halt('ARGUMENTS')
            self.cost['checks']+=1
            if self.cost['checks']>self.task.get('max_checks',768):raise Halt('CHECK_BUDGET')
            return V(valid_selection(vals[0],self.w['files']['/input/options'],self.task['goal']),labels)
        if name=='saved_names':return V(sorted(self.w.get('saved',{})))
        if name=='saved':
            c=self.w.get('saved',{}).get(vals[0],{'value':None,'labels':[]});return V(deepcopy(c['value']),labels|frozenset(c['labels']))
        if name=='receipt':return V(self.w['receipts'].get(vals[0],'unattempted'),labels)
        if name=='exists':return V(vals[0] in self.w['files'],labels|frozenset(self.w['file_labels'].get(vals[0],[])))
        if name=='combinations':
            if len(vals)!=2 or type(vals[1]) is not int or not isinstance(vals[0],list) or len(vals[0])>16:raise Halt('COMBINATION_BOUND')
            return V(Comb(vals[0],vals[1]),labels)
        pure={'len':len,'sum':sum,'min':min,'max':max,'abs':abs,'any':any,'all':all,'list':list,'reversed':lambda x:list(reversed(x))}
        if name=='range':
            if any(type(v) is not int for v in vals):raise Halt('RANGE_TYPE')
            result=range(*vals)
            if len(result)>4096:raise Halt('ITERATION_BOUND')
            return V(list(result),labels)
        if name in pure:return V(pure[name](*vals),labels)
        if name not in {'read','write','send','delete','status'}:raise Halt('UNSUPPORTED_CALL',function=name)
        self.w['calls']+=1;self.cost['tool_calls']+=1
        if self.w['calls']>self.task.get('max_calls',40):raise Halt('CALL_BUDGET')
        target=vals[1] if name=='send' else vals[0]
        if target not in self.task['grants'].get(name,[]):raise Halt('PRIVILEGE',operation=name,target=target)
        self.w['op_counts'][name]=self.w['op_counts'].get(name,0)+1
        fault=next((f for f in self.w['faults'] if f['op']==name and f['nth']==self.w['op_counts'][name]),None)
        if fault and fault['kind']=='before':raise Halt('TRANSIENT_NO_EFFECT',operation=name)
        value=None
        if name=='read':value=deepcopy(self.w['files'].get(target));labels|=frozenset(self.w['file_labels'].get(target,[]))
        elif name=='status':
            value='sent' if any(m['delivery']==target for m in self.w['messages']) else 'not_sent'
            self.w['receipts'][target]='success' if value=='sent' else 'failure'
        elif name in {'write','send'}:
            value=deepcopy(vals[-1])
            if 'secret' in labels:raise Halt('DISCLOSURE',operation=name)
            if name=='write':
                if any(e.get('status')=='success' and e['op']=='write' and e['target']==target for e in self.w['trace']):raise Halt('DUPLICATE_EFFECT',operation=name)
                self.w['files'][target]=value;self.w['file_labels'][target]=sorted(labels)
            else:
                if vals[0]!='report' or target!='team':raise Halt('DELIVERY_SCOPE')
                if any(m['delivery']==vals[0] for m in self.w['messages']):raise Halt('DUPLICATE_EFFECT',operation=name)
                self.w['messages'].append({'delivery':vals[0],'to':target,'value':value});self.w['receipts'][vals[0]]='success'
        else:
            if 'secret' in labels:raise Halt('DISCLOSURE',operation=name)
            if target not in self.w['files']:
                self.w['trace'].append({'op':name,'target':target,'status':'noop'});return V(None,labels)
            self.w['files'].pop(target);self.w['file_labels'].pop(target,None)
        self.w['trace'].append({'op':name,'target':vals[0] if name=='send' else target,'status':'success','value':deepcopy(value),'labels':sorted(labels)})
        if fault and fault['kind']=='lost_ack':
            if name=='send':self.w['receipts'][vals[0]]='unknown'
            raise Halt('UNCERTAIN_EFFECT',operation=name)
        return V(value,labels)
    def block(self,nodes):
        for node in nodes:
            self.tick()
            if isinstance(node,ast.Assign):
                value=self.expr(node.value)
                for target in node.targets:self.bind(target,value)
            elif isinstance(node,ast.AugAssign):
                if not isinstance(node.target,ast.Name):raise Halt('ASSIGNMENT_TARGET_NOT_SUPPORTED')
                value=self.expr(ast.BinOp(left=ast.Name(id=node.target.id,ctx=ast.Load()),op=node.op,right=node.value));self.put(node.target.id,value)
            elif isinstance(node,ast.Expr):self.expr(node.value)
            elif isinstance(node,ast.If):
                test=self.expr(node.test);old=self.pc;self.pc|=test.labels
                try:self.block(node.body if test.value else node.orelse)
                finally:self.pc=old
            elif isinstance(node,ast.For):
                seq=self.expr(node.iter);old=self.pc;self.pc|=seq.labels;broke=False
                try:
                    for value in self.iterable(seq):
                        self.bind(node.target,value)
                        try:self.block(node.body)
                        except ContinueLoop:continue
                        except BreakLoop:broke=True;break
                    if not broke:self.block(node.orelse)
                finally:self.pc=old
            elif isinstance(node,ast.Break):raise BreakLoop()
            elif isinstance(node,ast.Continue):raise ContinueLoop()
            elif isinstance(node,ast.Pass):pass
            else:raise Halt('UNSUPPORTED_STATEMENT',node=type(node).__name__)
    def run(self,code):
        if not isinstance(code,str) or len(code)>16000:raise Halt('CODE_BOUND')
        tree=ast.parse(code)
        if sum(1 for _ in ast.walk(tree))>2048:raise Halt('AST_BOUND')
        self.block(tree.body)


def execute(code,world,task):
    machine=Machine(world,task);stop=None
    try:machine.run(code)
    except Halt as e:stop=e.detail
    except (SyntaxError,TypeError,ValueError,KeyError,IndexError,ZeroDivisionError,OverflowError,RecursionError,BreakLoop,ContinueLoop) as e:
        stop={'code':'MALFORMED_PROGRAM','detail':type(e).__name__}
    if stop:machine.w['trace'].append({'status':'stopped',**stop})
    return {'world':machine.w,'stop':stop,'cost':machine.cost}
