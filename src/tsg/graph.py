"""Grounded partial instruction/AST graphs; deliberately not complete CFGs."""
from __future__ import annotations
import ast
import json
import re
from pathlib import Path

PATTERNS=[('secret.read',r'(?i)\b(secret|credential|api[_ -]?key|\.env|ssh[_ -]?key)\b'),
          ('network.post',r'(?i)\b(upload|send|post|transmit|sync|curl)\b'),
          ('network.get',r'(?i)\b(download|fetch|https?\.get)\b'),
          ('file.delete',r'(?i)\b(delete|unlink|remove|rmtree)\b'),
          ('file.write',r'(?i)\b(write|save|create|export)\b'),
          ('file.read',r'(?i)\b(read|open|load)\b'),
          ('command.exec',r'(?i)\b(python3?|bash|powershell|node|execute|subprocess)\b')]


def _resource(text):
    hits=re.findall(r'https://[^\s\)\]"\'`]+|/sandbox/[^\s\)\]"\'`]+|(?:scripts|src)/[\w./-]+',text)
    return hits[0].rstrip('.,;') if hits else 'unknown'


def extract_graph(skill_id,files):
    nodes=[];edges=[];unresolved=[];byfile={}
    def add(file,line,end,operation,text,kind='INSTR_ACTION',resource=None):
        node={'id':f'n{len(nodes):04d}','kind':kind,'operation':operation,'resource':resource or _resource(text),
              'summary':text[:350],'provenance':{'file':file,'line_start':line,'line_end':end},
              'candidate_status':'task_ambiguous' if operation not in {'secret.read','command.exec'} else 'suspicious',
              'authorization_source':False}
        nodes.append(node);byfile.setdefault(file,[]).append(node)
        return node
    for file,text in sorted(files.items()):
        lines=text.splitlines()
        if file.endswith('.py'):
            try:
                tree=ast.parse(text)
            except SyntaxError:
                unresolved.append({'file':file,'reason':'python_parse_error'});continue
            for call in sorted((n for n in ast.walk(tree) if isinstance(n,ast.Call)),key=lambda n:(n.lineno,n.col_offset)):
                fn=ast.unparse(call.func)
                raw=ast.get_source_segment(text,call) or fn
                operation=None
                if fn in {'eval','exec','compile','__import__'}:
                    unresolved.append({'file':file,'line':call.lineno,'reason':'dynamic_execution'})
                    operation='command.exec'
                elif any(s in fn for s in ('requests.post','httpx.post','urlopen','sendmail','send_message')):operation='network.post'
                elif any(s in fn for s in ('requests.get','httpx.get')):operation='network.get'
                elif any(s in fn for s in ('getenv','environ.get')):operation='secret.read'
                elif any(s in fn for s in ('subprocess.','os.system','os.popen')):operation='command.exec'
                elif any(s in fn for s in ('unlink','rmtree','os.remove')):operation='file.delete'
                elif any(s in fn for s in ('write_text','write_bytes')):operation='file.write'
                elif fn=='open':
                    mode=next((k.value.value for k in call.keywords if k.arg=='mode' and isinstance(k.value,ast.Constant)),None)
                    if len(call.args)>1 and isinstance(call.args[1],ast.Constant):mode=call.args[1].value
                    operation='file.write' if mode and any(s in str(mode) for s in 'wax+') else 'file.read'
                elif any(s in fn for s in ('read_text','read_bytes')):operation='file.read'
                if operation:
                    add(file,call.lineno,getattr(call,'end_lineno',call.lineno),operation,raw,'CODE_ACTION')
            if any(isinstance(n,(ast.If,ast.For,ast.While,ast.Try)) for n in ast.walk(tree)):
                unresolved.append({'file':file,'reason':'partial_control_flow_not_full_cfg'})
        elif file.endswith(('.md','.sh','.js','.ts','.ps1','.mjs','.cjs')):
            for i,line in enumerate(lines,1):
                for operation,pattern in PATTERNS:
                    if re.search(pattern,line):
                        add(file,i,i,operation,line,'INSTR_ACTION' if file.endswith('.md') else 'CODE_ACTION')
                        break
            if not file.endswith('.md'):
                unresolved.append({'file':file,'reason':'non_python_lexical_only'})
    # Text order edges are explicitly marked, never claimed to establish reachability.
    for file,ns in byfile.items():
        for a,b in zip(ns,ns[1:]):
            edges.append({'source':a['id'],'target':b['id'],'type':'CONTROL','semantics':'source_order_only'})
    for n in nodes:
        if n['kind']!='INSTR_ACTION':continue
        for file,code_nodes in byfile.items():
            if file.endswith('.py') and file in n['summary'] and code_nodes:
                edges.append({'source':n['id'],'target':code_nodes[0]['id'],'type':'CALL','semantics':'explicit_reference'})
                next_nodes=[m for m in byfile[n['provenance']['file']] if m['provenance']['line_start']>n['provenance']['line_end']]
                if next_nodes:
                    edges.append({'source':code_nodes[-1]['id'],'target':next_nodes[0]['id'],'type':'RETURN','semantics':'syntactic_return_approximation'})
    return {'skill_id':skill_id,'nodes':nodes,'edges':edges,'unresolved':unresolved,'graph_kind':'partial_static_graph',
            'limitation':'No interprocedural points-to, full CFG, shell semantics, or implicit-flow proof.'}


def validate_model_graph(graph,files):
    accepted=[];invalid=[];ids=set()
    operations={'file.read','file.write','file.delete','secret.read','network.get','network.post','email.send','command.exec','db.read','db.write','unknown'}
    if not isinstance(graph,dict) or not isinstance(graph.get('nodes'),list) or not isinstance(graph.get('edges',[]),list):
        raise ValueError('INVALID_GRAPH_SCHEMA')
    for n in graph.get('nodes',[]):
        if not isinstance(n,dict) or not isinstance(n.get('provenance'),dict):
            invalid.append({'node':n,'reason':'invalid_node_schema'});continue
        p=n.get('provenance',{})
        start,end=p.get('line_start'),p.get('line_end')
        valid=(isinstance(n.get('id'),str) and n['id'] not in ids and isinstance(p.get('file'),str) and p['file'] in files
               and type(start) is int and type(end) is int and 1<=start<=end<=len(files.get(p.get('file'),'').splitlines())
               and isinstance(n.get('operation'),str) and n['operation'] in operations and isinstance(n.get('resource'),str) and isinstance(n.get('summary'),str))
        if valid and n['resource']!='unknown':
            valid=n['resource'] in '\n'.join(files[p['file']].splitlines()[start-1:end])
        if valid:
            accepted.append(n);ids.add(n['id'])
        else:invalid.append({'node':n,'reason':'invalid_schema_span_or_ungrounded_literal'})
    edges=[e for e in graph.get('edges',[]) if isinstance(e,dict) and isinstance(e.get('source'),str) and isinstance(e.get('target'),str) and e['source'] in ids and e['target'] in ids and isinstance(e.get('type'),str) and e['type'] in {'CONTROL','DATA','CALL','RETURN'}]
    return {**graph,'nodes':accepted,'edges':edges},invalid


def read_bundle(row,max_chars=48000,max_files=24):
    root=Path(row['bundle_path']);paths=[Path(row['skill_md_path'])]
    # Files are read, never imported or executed. Bounded supporting evidence.
    paths += sorted((root/p for p in row['file_sha256'] if p.endswith(('.py','.sh','.js','.ts','.md','.ps1')) and root/p not in paths),key=str)
    files={};coverage={'truncated_files':[],'omitted_files':[],'redacted_patterns':0};remaining=max_chars
    for i,path in enumerate(paths):
        rel=path.relative_to(root).as_posix()
        if i>=max_files or remaining<=0:
            coverage['omitted_files'].append(rel);continue
        text=path.read_text(encoding='utf-8',errors='replace')
        # Redact recognizable credential-shaped strings before remote analysis.
        text,n=re.subn(r'\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,})\b','[REDACTED_CREDENTIAL_PATTERN]',text)
        coverage['redacted_patterns']+=n
        if len(text)>remaining:
            coverage['truncated_files'].append(rel)
        files[rel]=text[:remaining];remaining-=len(files[rel])
    return files,coverage


def numbered_files(files):
    return {name:'\n'.join(f'{i}: {line}' for i,line in enumerate(text.splitlines(),1)) for name,text in files.items()}
