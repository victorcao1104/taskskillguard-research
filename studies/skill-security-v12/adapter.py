"""Bounded source adapter. No source code or package instruction is executed."""
import ast
import hashlib
from pathlib import Path, PurePosixPath
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from tsg.runtime_v6 import _validate
from tsg.extraction_v4 import segment_markdown

class Unsupported(ValueError): pass

def need(ok,reason):
    if not ok: raise Unsupported(reason)

def compile_bundle(files):
    need(isinstance(files,dict) and isinstance(files.get('SKILL.md'),str),'missing_skill')
    text=files['SKILL.md']
    regions=segment_markdown(text,'SKILL.md');lines=text.splitlines()
    need(not any(r.get('closed') is False for r in regions),'unclosed_markdown_region')
    blocks=['\n'.join(lines[r['line_start']-1:r['line_end']]) for r in regions
            if r['region_kind']=='code_body' and r.get('language') in ('sh','shell','bash')]
    need(len(blocks)==1,'ambiguous_or_missing_invocation')
    match=re.fullmatch(r'\s*python (scripts/[A-Za-z0-9_./-]+\.py)\s*',blocks[0])
    need(match is not None,'unsupported_invocation')
    file=match.group(1)
    path=PurePosixPath(file)
    need(not path.is_absolute() and '..' not in path.parts and str(path)==file,'unsafe_entry_path')
    need(file in files and isinstance(files[file],str),'missing_entry')
    result=compile_script(files[file],file)
    result['entry']=file
    result['bundle_sha256']={k:hashlib.sha256(v.encode()).hexdigest() for k,v in sorted(files.items())}
    return result

def compile_script(source,file):
    need(len(source.encode())<=24000,'source_limit')
    try: tree=ast.parse(source)
    except (SyntaxError,ValueError) as exc: raise Unsupported('syntax_error') from exc
    statements=[n for n in ast.walk(tree) if isinstance(n,ast.stmt)]
    need(len({n.lineno for n in statements})==len(statements),'multiple_statements_per_line')
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    need(len(functions)==sum(isinstance(n,ast.FunctionDef) for n in tree.body),'duplicate_function')
    last_definition=max((n.lineno for n in functions.values()),default=0)
    for n in tree.body:
        if not isinstance(n,ast.FunctionDef) and n.lineno<last_definition:
            need(not any(isinstance(c,ast.Call) and isinstance(c.func,ast.Name) and c.func.id in functions
                         for c in ast.walk(n)),'call_before_definitions')
    need(not (set(functions)&{'Path','emit','range'}),'reserved_function')
    need(not any((isinstance(n,ast.Name) and n.id.startswith('__tsg_')) or (isinstance(n,ast.FunctionDef) and n.name.startswith('__tsg_')) for n in ast.walk(tree)),'reserved_internal_name')
    loopvars={n.target.id for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.target,ast.Name)}
    need(not any(isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id in loopvars for n in ast.walk(tree)),'loop_index_use')
    reserved={'Path','emit','range'}|set(functions)
    imported=set()
    nonimport=False
    for n in tree.body:
        if isinstance(n,ast.ImportFrom):
            need(not nonimport and n.level==0 and len(n.names)==1 and n.names[0].asname is None,'unsupported_import')
            need((n.module,n.names[0].name) in {('pathlib','Path'),('mock_tools','emit')},'unsupported_import')
            imported.add(n.names[0].name)
        else: nonimport=True
    for n in ast.walk(tree):
        if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store): need(n.id not in reserved,'reserved_reassignment')
    provenance={}
    filehash=hashlib.sha256(source.encode()).hexdigest()
    lines=source.splitlines()
    local_names={}
    for name,n in functions.items():
        need(not n.args.args and not n.args.posonlyargs and not n.args.kwonlyargs and n.args.vararg is None
             and n.args.kwarg is None and not n.decorator_list and n.returns is None,'unsupported_function')
        need(not any(isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) for s in n.body for x in ast.walk(s)),'nested_function')
        local_names[name]={x.id for s in n.body for x in ast.walk(s) if isinstance(x,ast.Name) and isinstance(x.ctx,ast.Store)}

    def name_of(name,owner): return f'__tsg_{len(owner)}_{owner}_{len(name)}_{name}' if owner and name in local_names[owner] else name
    def expr(n,owner,bound):
        if isinstance(n,ast.Constant) and type(n.value) in (str,int,bool): return n.value
        if isinstance(n,ast.Name):
            need(n.id not in reserved,'reserved_value')
            need(not owner or n.id not in local_names[owner] or n.id in bound,'unbound_helper_local')
            return {'var':name_of(n.id,owner)}
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Add):
            # Only string expressions are used by this subset. Runtime rejects nonstring addition.
            return {'concat':[expr(n.left,owner,bound),expr(n.right,owner,bound)]}
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='upper' and not n.args and not n.keywords:
            return {'upper':expr(n.func.value,owner,bound)}
        raise Unsupported('unsupported_expression')
    def effect(n,owner,bound,sid,out=None):
        if not isinstance(n,ast.Call) or n.keywords: return None
        op=None; resource=None; value=None
        if isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Call):
            p=n.func.value
            if isinstance(p.func,ast.Name) and p.func.id=='Path' and 'Path' in imported and len(p.args)==1 and not p.keywords:
                method=n.func.attr
                if method in ('read_text','write_text','unlink'):
                    need(len(n.args)==(1 if method=='write_text' else 0),'method_arguments')
                    op={'read_text':'read','write_text':'write','unlink':'delete'}[method]
                    resource=expr(p.args[0],owner,bound)
                    if op=='write': value=expr(n.args[0],owner,bound)
        elif isinstance(n.func,ast.Name) and n.func.id=='emit' and 'emit' in imported:
            need(len(n.args)==2,'emit_arguments');op='emit';resource=expr(n.args[0],owner,bound);value=expr(n.args[1],owner,bound)
        if op is None: return None
        need(out is None or op=='read','only_read_return_assignment')
        # Effect identity follows the call, including a multiline assignment.
        sid=f'{file}:{n.lineno}'
        row={'id':sid,'kind':'effect','op':op,'resource':resource}
        if value is not None:row['value']=value
        if out is not None:row['out']=out
        line=int(sid.rsplit(':',1)[1]);provenance[sid]={'file':file,'line':line,'end_line':getattr(n,'end_lineno',line),'sha256':filehash,'text':lines[line-1]}
        return row
    def block(nodes,owner=None,bound=None):
        bound=set(bound or []);result=[]
        for n in nodes:
            sid=f'{file}:{n.lineno}'
            if isinstance(n,ast.ImportFrom):
                need(owner is None and n in tree.body,'nested_import');continue
            if isinstance(n,ast.FunctionDef):
                need(owner is None and n in tree.body,'nested_function');continue
            if isinstance(n,ast.Assign):
                need(len(n.targets)==1 and isinstance(n.targets[0],ast.Name),'assignment_target')
                target=n.targets[0].id
                item=effect(n.value,owner,bound,sid,name_of(target,owner))
                if item is None:item={'id':sid,'kind':'let','name':name_of(target,owner),'value':expr(n.value,owner,bound)}
                result.append(item);bound.add(target)
            elif isinstance(n,ast.Expr):
                item=effect(n.value,owner,bound,sid)
                if item is None:
                    c=n.value
                    need(isinstance(c,ast.Call) and isinstance(c.func,ast.Name) and c.func.id in functions and not c.args and not c.keywords,'unsupported_statement')
                    item={'id':sid,'kind':'call','fn':c.func.id}
                result.append(item)
            elif isinstance(n,ast.If):
                t=n.test;need(isinstance(t,ast.Compare) and len(t.ops)==1 and isinstance(t.ops[0],ast.Eq),'if_condition')
                left,lb=block(n.body,owner,bound);right,rb=block(n.orelse,owner,bound)
                result.append({'id':sid,'kind':'if','eq':[expr(t.left,owner,bound),expr(t.comparators[0],owner,bound)],'then':left,'else':right});bound|=lb&rb
            elif isinstance(n,ast.For):
                c=n.iter
                need(isinstance(n.target,ast.Name) and not n.orelse and isinstance(c,ast.Call) and isinstance(c.func,ast.Name) and c.func.id=='range'
                     and len(c.args)==1 and isinstance(c.args[0],ast.Constant) and type(c.args[0].value) is int and 0<=c.args[0].value<=3 and not c.keywords,'for_range')
                need(not any(isinstance(x,ast.Name) and isinstance(x.ctx,ast.Load) and x.id==n.target.id for s in n.body for x in ast.walk(s)),'loop_index_use')
                body,_=block(n.body,owner,bound)
                result.append({'id':sid,'kind':'repeat','count':c.args[0].value,'body':body})
            else:raise Unsupported('unsupported_statement')
        return result,bound
    top,_=block(tree.body)
    program={'version':1,'steps':top,'functions':{name:block(n.body,name)[0] for name,n in functions.items()}}
    try:program=_validate(program)
    except ValueError as exc:raise Unsupported('invalid_finite_program:'+str(exc)) from exc
    return {'program':program,'provenance':provenance,'source_sha256':filehash,'file':file}
