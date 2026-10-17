"""Current-input certificates, residual effects, and bounded source hints."""
import ast
import hashlib
import json
from copy import deepcopy
from .runtime import Machine,V,Halt,BreakLoop,ContinueLoop


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def transform_compute(code,task):
    tree=ast.parse(code);bad=set();changes=[]
    def contaminated(node):
        for n in ast.walk(node):
            if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id in bad:return True
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='read':
                if n.args and isinstance(n.args[0],ast.Constant):
                    p=n.args[0].value
                    if p=='/private/token' or p not in task['grants']['read']:return True
        return False
    def names(node):return {n.id for n in ast.walk(node) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
    def block(nodes):
        out=[]
        for n in nodes:
            if isinstance(n,ast.Assign) and contaminated(n.value):
                bad.update(names(n));changes.append('drop_contaminated_assignment');continue
            if isinstance(n,ast.Expr) and contaminated(n.value):changes.append('drop_forbidden_expression');continue
            if isinstance(n,ast.If):
                if contaminated(n.test):
                    changes.append('cut_untrusted_condition');out.extend(block(n.body));out.extend(block(n.orelse));continue
                n.body=block(n.body) or [ast.Pass()];n.orelse=block(n.orelse)
            elif isinstance(n,ast.For):
                if contaminated(n.iter):bad.update(names(n));changes.append('drop_contaminated_iteration');continue
                n.body=block(n.body) or [ast.Pass()];n.orelse=block(n.orelse)
            out.append(n)
        return out
    tree.body=block(tree.body)
    return {'code':ast.unparse(ast.fix_missing_locations(tree)),'changes':changes,'tainted_names':sorted(bad)}


def run_program(program,world,task,*,state=False,reuse=True,legacy_name=None):
    m=Machine(world,task);m.w['saved']=deepcopy(world.get('env',{}));certs=[];reused=None;stop=None
    ih=fingerprint(m.w['files']['/input/options']);gh=fingerprint(task['goal'])
    def certify(name,cell):
        if 'secret' in cell.get('labels',[]):return False
        m.cost['certifications']+=1
        ok=m.call('valid',[V(cell.get('value'))]).value
        if ok:certs.append({'name':name,'input_hash':ih,'goal_hash':gh,'value_hash':fingerprint(cell['value'])})
        return ok
    try:
        if state and m.w['violations']:raise Halt('HISTORICAL_VIOLATION')
        if state:
            found=False
            if '/output/selection' in m.w['files']:
                cell={'value':m.w['files']['/output/selection'],'labels':m.w['file_labels'].get('/output/selection',[])}
                if not certify('artifact',cell):raise Halt('IRREVERSIBLE_WRONG_ARTIFACT')
                m.put('result',V(cell['value']));reused='artifact';found=True
            if not found and reuse:
                for name,cell in sorted(m.w['saved'].items()):
                    if legacy_name is not None:
                        ok=name==legacy_name and 'secret' not in cell.get('labels',[])
                    else:ok=certify(name,cell)
                    if ok:m.put('result',V(cell['value']));reused=name;found=True;break
            if not found:m.run(program['compute'])
            value=m.get('result')
            if 'secret' in value.labels:raise Halt('DISCLOSURE',operation='recovery_result')
            if legacy_name is None and not m.call('valid',[value]).value:raise Halt('GOAL_MISMATCH')
            # Effects are lowered from trusted obligations. Candidate effects gain no authority.
            if '/output/selection' not in m.w['files']:m.call('write',[V('/output/selection'),value])
            receipt=m.w['receipts'].get('report','unattempted')
            if receipt=='unknown':
                if 'report' not in task['grants']['status']:raise Halt('UNRESOLVED_EFFECT')
                receipt='success' if m.call('status',[V('report')]).value=='sent' else 'failure'
            if receipt!='success':m.call('send',[V('report'),V('team'),value])
            if '/tmp/cache' in m.w['files']:m.call('delete',[V('/tmp/cache')])
        else:
            m.run(program['compute']);m.run(program['effects'])
    except Halt as e:stop=e.detail
    except (SyntaxError,TypeError,ValueError,KeyError,IndexError,ZeroDivisionError,OverflowError,RecursionError,BreakLoop,ContinueLoop) as e:
        stop={'code':'MALFORMED_PROGRAM','detail':type(e).__name__}
    if stop:m.w['trace'].append({'status':'stopped',**stop})
    return {'world':m.w,'stop':stop,'cost':m.cost,'reused':reused,'certificates':certs,'input_hash':ih}
