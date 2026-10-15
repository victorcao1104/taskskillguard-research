"""Phase-5 explicit filesystem signatures over immutable v4 segmentation.

No supplied source is executed. Identity, reachability, existing destination
type, success, and authorization are never proven by these candidate records.
The adapter/orchestration below preserves v4 mapping without patching its globals.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import replace
import hashlib
from pathlib import PurePosixPath
import re

from .evidence_v4 import make_node
from .extraction_v4 import (_PythonV4, _map_details, _span, _instruction,
                            _TRUNCATION, segment_markdown)
from .graph import PATTERNS
from .graph_v2 import Value, UNKNOWN, _combine


_SIGNATURES = {
    'shutil.copyfile': (2, 'copy'), 'shutil.copy': (2, 'copy_directory_possible'),
    'shutil.move': (2, 'move_directory_possible'), 'os.rename': (2, 'rename'),
    'shutil.rmtree': (1, 'delete_tree'), 'os.remove': (1, 'delete'),
    'os.unlink': (1, 'delete'), 'os.mkdir': (1, 'mkdir'),
    'os.makedirs': (1, 'makedirs'),
}


class _PythonV5(_PythonV4):
    """A strict signature layer; all other semantics stay in the v4 subclass."""

    def __init__(self, *args):
        super().__init__(*args)
        self.invalid_extension_modules = set()
        try:
            tree = ast.parse(self.text)
        except (SyntaxError, ValueError, RecursionError):
            return
        aliases = {'os': {'os'}, 'shutil': {'shutil'}}
        assignments = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {'os', 'shutil'}:
                        aliases.setdefault(alias.asname or alias.name, set()).add(alias.name)
            if isinstance(node, ast.ImportFrom) and not node.level and node.module in {'os', 'shutil'}:
                for alias in node.names:
                    if alias.name != '*':
                        aliases.setdefault(alias.asname or alias.name, set()).add(node.module + '.' + alias.name)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                assignments.extend((t.id, node.value) for t in targets if isinstance(t, ast.Name))

        def references(node):
            if isinstance(node, ast.Name):
                return aliases.get(node.id, set())
            if isinstance(node, ast.Attribute):
                return {base + '.' + node.attr for base in references(node.value)}
            return set()

        # Union all possible syntactic alias roots solely for invalidation.
        # Positive identity always comes from the inherited flow environment.
        for _ in range(len(assignments) + 1):
            for left, right in assignments:
                aliases.setdefault(left, set()).update(references(right))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'globals', 'locals', 'exec', 'eval'}:
                # Namespace escape and dynamic evaluation make later imported
                # identities unproved, even when a particular mutation is not
                # syntactically visible. This intentionally over-abstains.
                self.invalid_extension_modules.update({'os', 'shutil'})
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in {'os', 'shutil'}:
                self.invalid_extension_modules.add(node.id)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'setattr', 'delattr'}:
                if node.args:
                    self.invalid_extension_modules.update(name.split('.')[0] for name in references(node.args[0]))
        self.invalid_extension_modules.update(symbol.split('.')[0] for name in self.mutated_names
                                              for symbol in aliases.get(name, set()))

    def call(self, node):
        # Inspect the syntax first. Evaluating inherited call() twice would
        # duplicate nested argument effects, so delegate before interpretation.
        syntactic = ast.unparse(node.func)
        direct = syntactic in _SIGNATURES
        function_hint = None
        if isinstance(node.func, ast.Name):
            function_hint = self.env.get(node.func.id)
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            root_value = self.env.get(node.func.value.id)
            if root_value and root_value.kind in {'module', 'symbol'} and isinstance(root_value.constant, str):
                function_hint = replace(root_value, constant=root_value.constant + '.' + node.func.attr)
        hinted_name = function_hint.constant if function_hint and isinstance(function_hint.constant, str) else None
        if not direct and hinted_name not in _SIGNATURES:
            return super().call(node)
        function = self.expression(node.func)
        args = [self.expression(a) for a in node.args]
        keywords = [self.expression(k.value) for k in node.keywords]
        inputs = [function, *args, *keywords]
        merged = _combine(inputs)
        canonical = function.constant if function.kind == 'symbol' and isinstance(function.constant, str) else None
        if (canonical not in _SIGNATURES or canonical.split('.')[0] in self.invalid_extension_modules
                or self.wildcard):
            self.unknown(node, 'extension_symbol_identity_unproven', callee=syntactic)
            return merged
        arity, kind = _SIGNATURES[canonical]
        roles = ['src', 'dst'] if arity == 2 else ['name' if canonical == 'os.makedirs' else 'path']
        bound = dict(zip(roles, args))
        invalid = len(args) > arity or any(isinstance(a, ast.Starred) for a in node.args)
        seen_keywords = set()
        for keyword, value in zip(node.keywords, keywords):
            if keyword.arg in seen_keywords:
                invalid = True
            seen_keywords.add(keyword.arg)
            if keyword.arg in roles:
                if keyword.arg in bound:
                    invalid = True
                bound[keyword.arg] = value
            elif not (canonical == 'os.makedirs' and keyword.arg == 'exist_ok' and
                      isinstance(keyword.value, ast.Constant) and type(keyword.value.value) is bool):
                invalid = True
        if invalid or any(role not in bound for role in roles):
            self.unknown(node, 'unsupported_extension_signature', callee=syntactic)
            return merged
        args = [bound[role] for role in roles]
        if any(a.kind in {'module', 'symbol', 'handle'} or a.constant is not UNKNOWN and
               (a.kind not in {'literal', 'path'} or not isinstance(a.constant, str)
                or not a.constant or a.constant == 'unknown') for a in args):
            self.unknown(node, 'invalid_extension_path_argument', callee=syntactic)
            return merged

        def effect(operation, resource, role, extra_inputs=()):
            return self.action(node, operation, resource, [*inputs, *extra_inputs],
                               signature=canonical, argument_role=role, extension_version=5,
                               path_semantics='supplied_path_expression_not_canonical_filesystem_identity')

        if kind.startswith('copy'):
            source = effect('file.read', args[0], 'source')
            destination = args[1]
            if kind.endswith('directory_possible'):
                self.unknown(node, 'destination_may_be_directory', callee=syntactic,
                             supplied_destination=destination.constant if isinstance(destination.constant, str) else None)
                destination = replace(destination, constant=UNKNOWN)
            effect('file.write', destination, 'destination', (source,))
        elif kind in {'rename', 'move_directory_possible'}:
            effect('file.delete', args[0], 'source_namespace')
            destination = args[1]
            if kind == 'move_directory_possible':
                self.unknown(node, 'destination_may_be_directory', callee=syntactic,
                             supplied_destination=destination.constant if isinstance(destination.constant, str) else None)
                destination = replace(destination, constant=UNKNOWN)
            effect('file.write', destination, 'destination_namespace')
        else:
            effect('file.delete' if kind.startswith('delete') else 'file.write', args[0],
                   'tree_root' if kind == 'delete_tree' else 'directory' if kind in {'mkdir', 'makedirs'} else 'target')
        # Some calls return a pathname, others None; this bounded layer does
        # not propagate any return value into later resource bindings.
        return Value()


def _python(text, file, *, line_offset=0, execution_role='source_code'):
    nodes, edges, unresolved = [], [], []
    _PythonV5(file, text, nodes, edges, unresolved).run()
    for record in unresolved:
        if 'line_start' not in record and text.splitlines():
            record.update(_span(file, 1, len(text.splitlines())))
    mapped, identifiers, occurrences = [], {}, Counter()
    scope_prefix = f':snippet@{line_offset + 1}' if execution_role == 'example' else ''
    for original in nodes:
        node = _map_details(original, line_offset, scope_prefix)
        provenance = node.pop('provenance')
        old_id = node.pop('id')
        evidence = node.pop('resource_evidence', [])
        key = (provenance['line_start'], provenance['line_end'])
        index = occurrences[key]
        occurrences[key] += 1
        # Frozen entries carry analysis/authorization flags that v4 normalizes.
        node.pop('analysis_kind', None)
        node.pop('invocation_proven', None)
        node.pop('authorization_source', None)
        node.pop('privilege_relevant', None)
        kind, operation, resource, summary = (node.pop(k) for k in ('kind', 'operation', 'resource', 'summary'))
        if operation == 'secret.read' and resource.startswith('env:'):
            operation, node['sensitivity'] = 'environment.read', 'unknown'
        status = node.pop('resource_status', 'unknown')
        entry = make_node(file, provenance['line_start'], provenance['line_end'], operation, resource, summary,
                          execution_role=execution_role, analysis_kind=('python_ast_partial_v5' if node.get('extension_version') == 5 else 'python_ast_partial_v4'),
                          resource_status=status, evidence=evidence, effect_index=index, kind=kind, **node)
        identifiers[old_id] = entry['id']
        mapped.append(entry)
    for node in mapped:
        for condition in node.get('control_context', []):
            condition['predicate_id'] = identifiers[condition['predicate_id']]
    mapped_edges = []
    for edge in edges:
        edge = {**edge, 'source': identifiers[edge['source']], 'target': identifiers[edge['target']]}
        if edge['type'] == 'CONTROL':
            if edge['semantics'] == 'local_statement_order':
                edge['type'] = 'ORDER'
            else:
                edge = {**edge, 'type': 'CONDITION', 'branch': edge['semantics'],
                        'semantics': 'predicate_condition_evidence'}
        mapped_edges.append(edge)
    return {'nodes': mapped, 'edges': mapped_edges,
            'unresolved': _map_details(unresolved, line_offset, scope_prefix, identifiers), 'rejected': []}


def extract_graph_v5(skill_id, files):
    """Extract candidate evidence from supplied text only; never read or run it.

    ``source_sha256`` hashes the exact supplied UTF-8 strings. Callers must retain
    external truncation/omission metadata: syntactically valid cuts cannot be
    discovered from strings alone.
    """
    graph = {'skill_id': skill_id, 'nodes': [], 'edges': [], 'unresolved': [], 'rejected': [],
             'regions': [], 'source_sha256': {}, 'analysis_complete': False,
             'graph_kind': 'segmented_partial_static_graph_v5',
             'limitation': 'Bounded candidate evidence; invocation, task scope, arbitrary language semantics, '
                           'source completeness and authorization are not proven. CONDITION edges are '
                           'predicate provenance, ORDER is source order, CALL is a literal reference.'}
    entries = {}

    def merge(result):
        for key in ('nodes', 'edges', 'unresolved', 'rejected'):
            graph[key].extend(result[key])

    for file, text in sorted(files.items()):
        graph['source_sha256'][file] = hashlib.sha256(text.encode('utf-8')).hexdigest()
        lines, suffix = text.splitlines(), PurePosixPath(file).suffix.lower()
        for number, line in enumerate(lines, 1):
            if _TRUNCATION.fullmatch(line):
                graph['unresolved'].append({**_span(file, number, number), 'reason': 'source_truncated'})
        if suffix in {'.py', '.sh', '.bash'}:
            if lines:
                graph['regions'].append({**_span(file, 1, len(lines)), 'region_kind': 'source_code',
                                         'language': suffix[1:]})
            if suffix == '.py':
                result = _python(text, file)
                entries[file] = next((n['id'] for n in result['nodes'] if n['operation'] == 'module_entry'), None)
            else:
                from .shell_v5 import analyze_shell
                result = analyze_shell(text, file)
            merge(result)
            continue
        if suffix != '.md':
            graph['unresolved'].append({'file': file, 'reason': 'unsupported_file_language'})
            continue
        regions = segment_markdown(text, file)
        graph['regions'].extend(regions)
        previous = None
        for region in regions:
            kind, first, last = region['region_kind'], region['line_start'], region['line_end']
            if kind == 'frontmatter' and not region['closed']:
                graph['unresolved'].append({**_span(file, first, last), 'reason': 'unclosed_frontmatter'})
            if kind == 'html_comment' and not region['closed']:
                graph['unresolved'].append({**_span(file, first, last), 'reason': 'unclosed_html_comment'})
            if kind == 'html_block':
                graph['unresolved'].append({**_span(file, first, last), 'reason': 'unsupported_html_block'})
            if kind == 'fence_marker' and not region['closed']:
                graph['unresolved'].append({**_span(file, first, last), 'reason': 'unclosed_fence'})
            if kind == 'fence_marker' and region.get('opening') and region.get('empty_body'):
                language = region['language']
                reason = ('empty_fenced_code' if language in {'python', 'py', 'python3', 'bash', 'sh', 'shell'}
                          else 'unsupported_fence_language')
                graph['unresolved'].append({**_span(file, first, last), 'reason': reason, 'language': language})
            if kind == 'code_body':
                if not region['closed']:
                    continue
                language = region['language']
                indent = region['fence_indent']
                code = '\n'.join(line[min(indent, len(line) - len(line.lstrip(' '))):]
                                 for line in lines[first - 1:last])
                if language in {'python', 'py', 'python3'}:
                    merge(_python(code, file, line_offset=first - 1, execution_role='example'))
                elif language in {'bash', 'sh', 'shell'}:
                    from .shell_v5 import analyze_shell
                    merge(analyze_shell(code, file, line_offset=first - 1, execution_role='example'))
                else:
                    graph['unresolved'].append({**_span(file, first, last),
                                                'reason': 'unsupported_fence_language', 'language': language})
                continue
            if kind == 'indented_code':
                graph['unresolved'].append({**_span(file, first, last), 'reason': 'unsupported_indented_code'})
            for number in range(first, last + 1):
                line = lines[number - 1]
                operation = next((op for op, pattern in PATTERNS if re.search(pattern, line)), None)
                node, reason = _instruction(line, file, number) if kind == 'prose' else (None, kind)
                if node:
                    graph['nodes'].append(node)
                    if previous:
                        graph['edges'].append({'source': previous, 'target': node['id'], 'type': 'ORDER',
                                               'semantics': 'source_order_only'})
                    previous = node['id']
                elif operation:
                    graph['rejected'].append({**_span(file, number, number), 'operation': operation,
                                               'summary': line[:350], 'reason': reason,
                                               'analysis_kind': 'rejected_legacy_lexical_match'})
        # Account for legacy matches inside code too, including comments and
        # unsupported/unclosed bodies. They are not promoted into actions.
        accounted = {r['line_start'] for r in graph['rejected'] if r['file'] == file}
        action_lines = {number for node in graph['nodes'] if node['provenance']['file'] == file
                        and node['privilege_relevant']
                        for number in range(node['provenance']['line_start'], node['provenance']['line_end'] + 1)}
        for region in regions:
            for number in range(region['line_start'], region['line_end'] + 1):
                if number in accounted or number in action_lines:
                    continue
                line = lines[number - 1]
                operation = next((op for op, pattern in PATTERNS if re.search(pattern, line)), None)
                if not operation:
                    continue
                reason = region['region_kind']
                if reason == 'code_body':
                    reason = ('unclosed_fence' if not region['closed'] else
                              'unsupported_fence_language' if region['language'] not in
                              {'python', 'py', 'python3', 'bash', 'sh', 'shell'} else 'no_supported_code_action')
                graph['rejected'].append({**_span(file, number, number), 'operation': operation,
                                           'summary': line[:350], 'reason': reason,
                                           'analysis_kind': 'rejected_legacy_lexical_match'})
    for node in graph['nodes']:
        if node['operation'] == 'command.exec' and node['resource'] in entries and entries[node['resource']]:
            graph['edges'].append({'source': node['id'], 'target': entries[node['resource']], 'type': 'CALL',
                                   'semantics': 'explicit_script_reference'})
    graph['coverage'] = {'analysis_complete': False, 'extension_version': 5,
                         'candidate_actions': sum(n['privilege_relevant'] for n in graph['nodes']),
                         'extension_actions': sum(n.get('extension_version') == 5 for n in graph['nodes']),
                         'unknown_reasons': dict(sorted(Counter(u['reason'] for u in graph['unresolved']).items())),
                         'claim': 'bounded candidate coverage only; not accuracy or execution proof'}
    return graph
