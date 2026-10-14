"""Partial, non-executing Python abstract interpretation for grounded graphs.

Constants and explicit argument dependencies are tracked inside lexical scopes.
The output is candidate evidence, never authorization or a whole-program proof.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
import re

from .graph import PATTERNS, _resource

UNKNOWN = object()


@dataclass(frozen=True)
class Value:
    constant: object = UNKNOWN
    kind: str = 'unknown'
    producers: tuple[str, ...] = ()
    evidence: tuple = ()
    member: str = ''
    receiver: object = None


def _combine(values):
    producers = tuple(sorted({p for value in values for p in value.producers}))
    evidence = []
    for value in values:
        for item in value.evidence:
            if item not in evidence:
                evidence.append(item)
    return Value(producers=producers, evidence=tuple(evidence))


class _Python:
    def __init__(self, file, text, nodes, edges, unresolved):
        self.file, self.text = file, text
        self.nodes, self.edges, self.unresolved = nodes, edges, unresolved
        self.env = {}
        self.frontier = []
        self.scope = file + ':<module>'
        self.conditions = []
        self.entries = {}
        self.exits = {}
        self.module_rebindings = set()

    def span(self, node):
        return {'file': self.file, 'line_start': getattr(node, 'lineno', 1),
                'line_end': getattr(node, 'end_lineno', None) or getattr(node, 'lineno', 1)}

    def unknown(self, node, reason, **details):
        self.unresolved.append({**self.span(node), 'reason': reason, 'scope': self.scope, **details})

    def add(self, node, kind, operation, resource=UNKNOWN, inputs=(), **extra):
        raw = ast.get_source_segment(self.text, node) or type(node).__name__
        entry = {'id': f'n{len(self.nodes):05d}', 'kind': kind, 'operation': operation,
                 'resource': resource if isinstance(resource, str) else 'unknown',
                 'summary': raw[:350], 'provenance': self.span(node), 'scope': self.scope,
                 'control_context': list(self.conditions), 'authorization_source': False,
                 'privilege_relevant': kind == 'CODE_ACTION',
                 'candidate_status': 'unresolved' if resource is UNKNOWN and kind == 'CODE_ACTION' else
                                     'suspicious' if operation in {'secret.read', 'command.exec'} else 'task_ambiguous',
                 'analysis_kind': 'python_ast_partial', **extra}
        self.nodes.append(entry)
        for source in self.frontier:
            condition = next((c for c in self.conditions if c['predicate_id'] == source), None)
            self.edges.append({'source': source, 'target': entry['id'], 'type': 'CONTROL',
                               'semantics': 'branch_' + condition['branch'] if condition else 'local_statement_order'})
        for source in _combine(inputs).producers:
            self.edges.append({'source': source, 'target': entry['id'], 'type': 'DATA',
                               'semantics': 'may_value_dependency'})
        self.frontier = [entry['id']]
        return entry

    def action(self, node, operation, resource, inputs, **extra):
        known = isinstance(resource.constant, str)
        entry = self.add(node, 'CODE_ACTION', operation, resource.constant if known else UNKNOWN, inputs,
                         resource_status=('resolved_constant' if resource.producers else 'literal') if known else 'unknown',
                         resource_evidence=list(resource.evidence), **extra)
        if not known:
            self.unknown(node, 'unresolved_resource_expression', operation=operation)
        return Value(producers=(entry['id'],), evidence=(self.span(node),))

    def expression(self, node):
        if node is None:
            return Value()
        if isinstance(node, ast.Constant):
            return Value(node.value, 'literal', evidence=(self.span(node),))
        if isinstance(node, ast.Name):
            if node.id in self.env:
                return self.env[node.id]
            if node.id in {'open', 'eval', 'exec', 'compile', '__import__'}:
                return Value('builtins.' + node.id, 'symbol')
            return Value()
        if isinstance(node, ast.Attribute):
            receiver = self.expression(node.value)
            if receiver.kind in {'module', 'symbol'} and isinstance(receiver.constant, str):
                return replace(receiver, constant=receiver.constant + '.' + node.attr, kind='symbol')
            return Value(kind='method', producers=receiver.producers, evidence=receiver.evidence,
                         member=node.attr, receiver=receiver)
        if isinstance(node, ast.BinOp):
            left, right = self.expression(node.left), self.expression(node.right)
            merged = _combine([left, right])
            if isinstance(left.constant, str) and isinstance(right.constant, str):
                if isinstance(node.op, ast.Add) and left.kind != 'path' and right.kind != 'path':
                    return replace(merged, constant=left.constant + right.constant, kind='literal')
                if isinstance(node.op, ast.Div) and left.kind == 'path':
                    return replace(merged, constant=str(PurePosixPath(left.constant) / right.constant), kind='path')
            return merged
        if isinstance(node, ast.JoinedStr):
            values = []
            for item in node.values:
                if isinstance(item, ast.Constant):
                    values.append(self.expression(item))
                elif isinstance(item, ast.FormattedValue) and item.conversion == -1 and item.format_spec is None:
                    values.append(self.expression(item.value))
                else:
                    values.append(Value())
            merged = _combine(values)
            if all(type(v.constant) in (str, int, bool) for v in values):
                return replace(merged, constant=''.join(str(v.constant) for v in values), kind='literal')
            return merged
        if isinstance(node, ast.Call):
            return self.call(node)
        if isinstance(node, ast.Subscript):
            base, index = self.expression(node.value), self.expression(node.slice)
            if base.kind == 'symbol' and base.constant == 'os.environ':
                resource = replace(index, constant='env:' + index.constant) if isinstance(index.constant, str) else index
                return self.action(node, 'secret.read', resource, [base, index])
            return _combine([base, index])
        if isinstance(node, ast.Lambda):
            self.unknown(node, 'lambda_body_not_analyzed')
            return Value()
        if isinstance(node, ast.NamedExpr):
            value = self.expression(node.value)
            self.bind(node.target, value)
            return value
        if isinstance(node, ast.IfExp):
            test = self.expression(node.test)
            predicate = self.add(node.test, 'PREDICATE', 'conditional_expression', inputs=[test])
            original, conditions = dict(self.env), list(self.conditions)
            values, states, exits = [], [], []
            for label, expression in [('true', node.body), ('false', node.orelse)]:
                self.env, self.frontier = dict(original), [predicate['id']]
                self.conditions = [*conditions, {'predicate_id': predicate['id'], 'branch': label}]
                values.append(self.expression(expression))
                states.append(self.env)
                exits.extend(self.frontier)
            self.conditions = conditions
            self.env, self.frontier = self.merge(node, states), list(dict.fromkeys(exits))
            return self.merge(node, [{'result': v} for v in values])['result']
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            self.unknown(node, 'expression_control_flow_not_modeled')
            # Traverse expressions for possible calls, but do not infer a value.
            original = dict(self.env)
            bound = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            for name in bound:
                self.env[name] = Value()
            values = [self.expression(c) for c in ast.iter_child_nodes(node) if isinstance(c, ast.expr)]
            self.env = original
            return _combine(values)
        return _combine([self.expression(child) for child in ast.iter_child_nodes(node) if isinstance(child, ast.expr)])

    def call(self, node):
        function = self.expression(node.func)
        args = [self.expression(a) for a in node.args]
        kwargs = {k.arg: self.expression(k.value) for k in node.keywords}
        inputs = [function, *args, *kwargs.values()]
        merged = _combine(inputs)
        name = function.constant if function.kind in {'symbol', 'module'} else None
        first = args[0] if args else Value()
        receiver = function.receiver if function.kind == 'method' else None
        if name in {'pathlib.Path', 'pathlib.PurePosixPath'}:
            if len(args) == 1 and isinstance(first.constant, str) and not kwargs:
                return replace(first, kind='path')
            self.unknown(node, 'unsupported_path_constructor')
            return merged
        if name == 'os.path.join':
            self.unknown(node, 'platform_dependent_path_join')
            return merged
        if name in {'builtins.open', 'io.open'} or receiver is not None and receiver.kind == 'path' and function.member == 'open':
            resource = receiver if receiver is not None else (first if args else kwargs.get('file', Value()))
            mode_index = 0 if receiver is not None else 1
            mode = args[mode_index] if len(args) > mode_index else kwargs.get('mode', Value('r', 'literal'))
            if not isinstance(mode.constant, str) or not mode.constant or any(c not in 'rwaxbt+' for c in mode.constant):
                operation = 'unknown'
                extra = {'possible_operations': ['file.read', 'file.write'], 'candidate_status': 'unresolved'}
                self.unknown(node, 'dynamic_or_invalid_open_mode')
            else:
                operation = 'file.write' if any(c in mode.constant for c in 'wax+') else 'file.read'
                extra = {}
            result = self.action(node, operation, resource, inputs, **extra)
            return replace(result, constant=resource.constant, kind='handle')
        if receiver is not None and (receiver.kind == 'path' and function.member in {'read_text', 'read_bytes', 'write_text', 'write_bytes', 'unlink'}
                                     or receiver.kind == 'handle' and function.member in {'read', 'readline', 'readlines', 'write', 'writelines'}):
            operation = 'file.delete' if function.member == 'unlink' else 'file.write' if function.member.startswith('write') else 'file.read'
            return self.action(node, operation, receiver, inputs)
        operations = {
            'requests.get': 'network.get', 'httpx.get': 'network.get',
            'requests.post': 'network.post', 'httpx.post': 'network.post',
            'os.remove': 'file.delete', 'os.unlink': 'file.delete', 'shutil.rmtree': 'file.delete',
            'os.getenv': 'secret.read', 'os.environ.get': 'secret.read',
            'os.system': 'command.exec', 'os.popen': 'command.exec',
            'subprocess.run': 'command.exec', 'subprocess.Popen': 'command.exec',
            'subprocess.call': 'command.exec', 'subprocess.check_call': 'command.exec',
            'subprocess.check_output': 'command.exec',
            'builtins.exec': 'command.exec', 'builtins.eval': 'command.exec',
            'builtins.compile': 'command.exec', 'builtins.__import__': 'command.exec',
        }
        if name in operations:
            operation = operations[name]
            resource = first if args else kwargs.get('url', kwargs.get('path', kwargs.get('key', Value())))
            if operation == 'secret.read' and isinstance(resource.constant, str):
                resource = replace(resource, constant='env:' + resource.constant)
            if name.startswith('builtins.'):
                self.unknown(node, 'dynamic_execution')
            if operation == 'command.exec':
                self.unknown(node, 'command_semantics_not_interpreted')
            return self.action(node, operation, resource, inputs)
        if receiver is not None and function.member in {'read_text', 'read_bytes', 'write_text', 'write_bytes', 'unlink'}:
            self.unknown(node, 'receiver_type_unknown')
            operation = 'file.delete' if function.member == 'unlink' else 'file.write' if function.member.startswith('write') else 'file.read'
            return self.action(node, operation, Value(producers=receiver.producers), inputs,
                               candidate_status='unresolved', signature_only=True)
        self.unknown(node, 'unmodeled_call', callee=ast.unparse(node.func)[:160])
        # Passing a value into an unknown function is only a possible dependency;
        # purity, output equality, side effects and declassification are not inferred.
        return merged

    def bind(self, target, value):
        if isinstance(target, ast.Name):
            entry = self.add(target, 'DATA_OBJECT', 'bind', inputs=[value], binding=target.id,
                             value_status='constant' if value.constant is not UNKNOWN else 'unknown')
            self.env[target.id] = replace(value, producers=(entry['id'],),
                                           evidence=tuple([*value.evidence, self.span(target)]))
        elif isinstance(target, (ast.Tuple, ast.List)):
            self.unknown(target, 'destructuring_value_unknown')
            for item in target.elts:
                self.bind(item, replace(value, constant=UNKNOWN, kind='unknown'))
        else:
            self.unknown(target, 'attribute_or_subscript_mutation')
            root = target
            while isinstance(root, (ast.Attribute, ast.Subscript)):
                root = root.value
            if isinstance(root, ast.Name):
                self.env[root.id] = Value(producers=value.producers)

    def merge(self, node, states):
        merged = {}
        for name in set().union(*(set(s) for s in states)):
            values = [s.get(name, Value()) for s in states]
            first = values[0]
            same = first.constant is not UNKNOWN and all(type(v.constant) == type(first.constant) and v.constant == first.constant and v.kind == first.kind for v in values)
            combined = _combine(values)
            merged[name] = replace(first, producers=combined.producers, evidence=combined.evidence) if same else combined
            if not same and any(v.constant is not UNKNOWN for v in values):
                self.unknown(node, 'branch_merged_constant_unknown', binding=name)
        return merged

    def block(self, statements):
        for statement in statements:
            self.statement(statement)

    def statement(self, node):
        if isinstance(node, ast.Import):
            for alias in node.names:
                self.env[alias.asname or alias.name.split('.')[0]] = Value(alias.name if alias.asname else alias.name.split('.')[0], 'module')
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == '*' or node.level:
                    self.unknown(node, 'wildcard_or_relative_import_not_resolved')
                else:
                    self.env[alias.asname or alias.name] = Value((node.module or '') + '.' + alias.name, 'symbol')
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = self.expression(node.value)
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                self.bind(target, value)
        elif isinstance(node, ast.AugAssign):
            inputs = _combine([self.expression(node.target), self.expression(node.value)])
            self.bind(node.target, inputs)
            self.unknown(node, 'augmented_assignment_constant_unknown')
        elif isinstance(node, ast.Expr):
            self.expression(node.value)
        elif isinstance(node, ast.If):
            test = self.expression(node.test)
            predicate = self.add(node.test, 'PREDICATE', 'branch', inputs=[test])
            original, conditions = dict(self.env), list(self.conditions)
            states, exits = [], []
            for label, statements in [('true', node.body), ('false', node.orelse)]:
                self.env, self.frontier = dict(original), [predicate['id']]
                self.conditions = [*conditions, {'predicate_id': predicate['id'], 'branch': label}]
                self.block(statements)
                states.append(self.env)
                exits.extend(self.frontier)
            self.conditions = conditions
            self.env, self.frontier = self.merge(node, states), list(dict.fromkeys(exits))
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            condition = node.test if isinstance(node, ast.While) else node.iter
            inputs = self.expression(condition)
            predicate = self.add(condition, 'PREDICATE', 'loop', inputs=[inputs])
            self.unknown(node, 'loop_fixed_point_not_computed')
            before, conditions = dict(self.env), list(self.conditions)
            assigned = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            for name in assigned:
                self.env[name] = Value()
            self.conditions = [*conditions, {'predicate_id': predicate['id'], 'branch': 'loop_body'}]
            self.block(node.body)
            after = self.env
            exits = [predicate['id'], *self.frontier]
            self.conditions = conditions
            self.env = self.merge(node, [before, after])
            for name in assigned:
                self.env[name] = replace(self.env.get(name, Value()), constant=UNKNOWN, kind='unknown')
            self.frontier = list(dict.fromkeys(exits))
            self.block(node.orelse)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                value = self.expression(item.context_expr)
                if item.optional_vars is not None:
                    self.bind(item.optional_vars, value)
            self.block(node.body)
            self.unknown(node, 'context_manager_exit_effects_not_modeled')
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.function(node)
        elif isinstance(node, ast.ClassDef):
            self.unknown(node, 'class_construction_semantics_not_modeled')
            saved_env, saved_frontier, saved_scope = self.env, self.frontier, self.scope
            self.env = {k: v for k, v in saved_env.items() if v.kind in {'module', 'symbol'}}
            self.frontier, self.scope = [], saved_scope + '.' + node.name
            self.add(node, 'TOOL_ENTRY', 'class_body')
            self.block(node.body)
            self.env, self.frontier, self.scope = saved_env, saved_frontier, saved_scope
            self.env[node.name] = Value()
        elif isinstance(node, (ast.Return, ast.Raise)):
            value = self.expression(node.value if isinstance(node, ast.Return) else node.exc)
            self.add(node, 'END', 'return' if isinstance(node, ast.Return) else 'raise', inputs=[value])
            self.frontier = []
        elif isinstance(node, (ast.Break, ast.Continue)):
            self.add(node, 'END', 'loop_control')
            self.frontier = []
            self.unknown(node, 'loop_control_flow_partial')
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    # Keep an unknown binding so deleting a shadow cannot falsely
                    # restore the builtin/tool identity within this analysis.
                    self.env[target.id] = Value()
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            self.unknown(node, 'nonlocal_state_not_modeled')
            for name in node.names:
                self.env[name] = Value()
        elif isinstance(node, ast.Pass):
            return
        elif isinstance(node, ast.Assert):
            self.expression(node.test)
            self.unknown(node, 'assertion_exit_not_modeled')
        else:
            self.unknown(node, 'unsupported_statement', statement=type(node).__name__)
            # Analyze alternative statement lists independently, with all
            # mutable constants invalidated; never sequence exception branches.
            before, exits = dict(self.env), list(self.frontier)
            states, branches = [before], []
            for field in ('body', 'orelse', 'finalbody'):
                statements = getattr(node, field, [])
                if statements:
                    branches.append(statements)
            branches.extend(h.body for h in getattr(node, 'handlers', []))
            for statements in branches:
                self.env = {k: v if v.kind in {'module', 'symbol'} else Value(producers=v.producers) for k, v in before.items()}
                self.frontier = list(exits)
                self.block(statements)
                states.append(self.env)
            self.env, self.frontier = self.merge(node, states), exits

    def function(self, node):
        self.unknown(node, 'function_invocation_and_global_state_not_proven')
        saved = self.env, self.frontier, self.scope, self.conditions
        # Only imported symbol identities are inherited. Module constants can
        # change before invocation and therefore are not evaluated as globals.
        self.env = {k: v if v.kind in {'module', 'symbol'} and k not in self.module_rebindings else Value()
                    for k, v in saved[0].items()}
        for name in self.module_rebindings:
            self.env[name] = Value()
        local_names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        local_names.update(a.arg for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs])
        if node.args.vararg:
            local_names.add(node.args.vararg.arg)
        if node.args.kwarg:
            local_names.add(node.args.kwarg.arg)
        for name in local_names:
            self.env[name] = Value()
        self.scope, self.frontier, self.conditions = saved[2] + '.' + node.name, [], []
        self.add(node, 'TOOL_ENTRY', 'function_entry', invocation_proven=False)
        self.block(node.body)
        self.add(node, 'END', 'function_exit', invocation_proven=False)
        self.env, self.frontier, self.scope, self.conditions = saved
        self.env[node.name] = Value()

    def run(self):
        if not self.text.splitlines():
            self.unresolved.append({'file': self.file, 'reason': 'empty_python_source'})
            return None
        try:
            tree = ast.parse(self.text)
        except (SyntaxError, ValueError, RecursionError):
            self.unresolved.append({'file': self.file, 'reason': 'python_parse_error'})
            return None
        # A function may be invoked after any module-level rebinding. Do not
        # assume the imported/builtin identity seen at its definition persists.
        class Rebindings(ast.NodeVisitor):
            def visit_Name(visitor, node):
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    self.module_rebindings.add(node.id)

            def visit_FunctionDef(visitor, node):
                self.module_rebindings.add(node.name)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(visitor, node):
                self.module_rebindings.add(node.name)

        Rebindings().visit(tree)
        entry = self.add(tree, 'TOOL_ENTRY', 'module_entry')
        self.block(tree.body)
        end = self.add(tree.body[-1] if tree.body else tree, 'END', 'module_exit')
        return entry['id'], end['id']


def extract_graph_v2(skill_id, files):
    nodes, edges, unresolved = [], [], []
    module_ends, docs = {}, {}
    for file, text in sorted(files.items()):
        if file.endswith('.py'):
            result = _Python(file, text, nodes, edges, unresolved).run()
            if result:
                module_ends[file] = result
            continue
        if not file.endswith(('.md', '.sh', '.js', '.ts', '.ps1', '.mjs', '.cjs')):
            unresolved.append({'file': file, 'reason': 'unsupported_file_language'})
            continue
        previous = None
        for line_number, line in enumerate(text.splitlines(), 1):
            if not file.endswith('.md') and line.lstrip().startswith(('#', '//', '/*', '*')):
                continue
            operation = next((op for op, pattern in PATTERNS if re.search(pattern, line)), None)
            if operation is None:
                continue
            node = {'id': f'n{len(nodes):05d}', 'kind': 'INSTR_ACTION' if file.endswith('.md') else 'CODE_ACTION',
                    'operation': operation, 'resource': _resource(line), 'resource_status': 'lexical_literal' if _resource(line) != 'unknown' else 'unknown',
                    'summary': line[:350], 'provenance': {'file': file, 'line_start': line_number, 'line_end': line_number},
                    'scope': file, 'authorization_source': False, 'privilege_relevant': True,
                    'candidate_status': 'task_ambiguous' if file.endswith('.md') else 'unresolved',
                    'analysis_kind': 'untrusted_document_candidate' if file.endswith('.md') else 'lexical_only'}
            nodes.append(node)
            if previous:
                edges.append({'source': previous, 'target': node['id'], 'type': 'CONTROL', 'semantics': 'source_order_only'})
            previous = node['id']
            if file.endswith('.md'):
                docs.setdefault(file, []).append(node)
        if not file.endswith('.md'):
            unresolved.append({'file': file, 'reason': 'non_python_lexical_only'})
    for doc_nodes in docs.values():
        for i, node in enumerate(doc_nodes):
            text = node['summary']
            if not re.search(r'\b(?:run|execute|python3?|bash|node)\b', text, flags=re.I):
                continue
            for file, (entry, end) in module_ends.items():
                if re.search(r'(?<![\w./-])' + re.escape(file) + r'(?![\w./-])', text):
                    edges.append({'source': node['id'], 'target': entry, 'type': 'CALL', 'semantics': 'explicit_script_reference'})
                    if i + 1 < len(doc_nodes):
                        edges.append({'source': end, 'target': doc_nodes[i + 1]['id'], 'type': 'RETURN', 'semantics': 'syntactic_return_candidate'})
    return {'skill_id': skill_id, 'nodes': nodes, 'edges': edges, 'unresolved': unresolved,
            'graph_kind': 'partial_static_graph_v2', 'analysis_complete': False,
            'limitation': 'Candidate coverage only; no interprocedural execution proof, complete CFG, alias analysis, arbitrary language semantics, implicit flow, or authorization inference.'}
