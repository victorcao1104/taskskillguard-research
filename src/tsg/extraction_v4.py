"""Segmented, non-executing evidence extraction; never an execution proof.

Python semantics are inherited from the immutable v2 interpreter. Each snippet
has a fresh environment. CONDITION edges preserve predicate provenance without
claiming dominance or value dependence; ORDER means source order only.
"""
from __future__ import annotations

from collections import Counter
import ast
import hashlib
from pathlib import PurePosixPath
import re

from .evidence_v4 import make_node
from .graph import PATTERNS
from .graph_v2 import _Python, Value


def _span(file, start, end):
    return {'file': file, 'line_start': start, 'line_end': end}


def segment_markdown(text, file):
    """Return disjoint physical-line regions, including both fence markers.

    This is deliberately a bounded Markdown grammar, not a CommonMark renderer.
    Empty code bodies have no fabricated source span. Unclosed regions retain
    ``closed=False`` and are never submitted to language interpretation.
    """
    lines, regions, index = text.splitlines(), [], 0

    def add(kind, first, last, **extra):
        if first <= last:
            regions.append({**_span(file, first + 1, last + 1), 'region_kind': kind, **extra})

    if lines and lines[0].lstrip('\ufeff') == '---':
        end = next((i for i in range(1, len(lines)) if lines[i] in {'---', '...'}), None)
        add('frontmatter', 0, end if end is not None else len(lines) - 1, closed=end is not None)
        index = end + 1 if end is not None else len(lines)
    while index < len(lines):
        line = lines[index]
        if re.match(r'^ {0,3}<!--', line):
            end = next((i for i in range(index, len(lines)) if '-->' in lines[i]), None)
            add('html_comment', index, end if end is not None else len(lines) - 1, closed=end is not None)
            index = end + 1 if end is not None else len(lines)
            continue
        html = re.match(r'^ {0,3}<([A-Za-z][\w-]*)(?:\s|>|/)', line)
        if html:
            closing = re.compile(r'</' + re.escape(html[1]) + r'\s*>', re.I)
            end = index if re.search(r'/\s*>\s*$', line) else next(
                (i for i in range(index, len(lines)) if closing.search(lines[i])), None)
            add('html_block', index, end if end is not None else len(lines) - 1, closed=end is not None)
            index = end + 1 if end is not None else len(lines)
            continue
        fence = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence and not (fence[1][0] == '`' and '`' in fence[2]):
            marker, info = fence[1], fence[2].strip()
            language = info.split()[0].lower() if info else ''
            close = re.compile(r'^ {0,3}' + re.escape(marker[0]) + '{' + str(len(marker)) + r',}\s*$')
            end = next((i for i in range(index + 1, len(lines)) if close.fullmatch(lines[i])), None)
            add('fence_marker', index, index, language=language, closed=end is not None,
                opening=True, empty_body=end == index + 1)
            add('code_body', index + 1, end - 1 if end is not None else len(lines) - 1,
                language=language, closed=end is not None, fence_line=index + 1,
                fence_indent=len(line) - len(line.lstrip(' ')))
            if end is not None:
                add('fence_marker', end, end, language=language, closed=True, opening=False)
            index = end + 1 if end is not None else len(lines)
            continue
        if (line.strip() and index + 1 < len(lines)
                and re.fullmatch(r' {0,3}(?:=+|-+)\s*', lines[index + 1])):
            add('heading', index, index + 1)
            index += 2
            continue
        if re.match(r'^ {0,3}#{1,6}(?:\s|$)', line):
            kind = 'heading'
        elif '|' in line:
            kind = 'table'
        elif line.startswith(('    ', '\t')):
            kind = 'indented_code'
        elif not line.strip():
            kind = 'blank'
        else:
            kind = 'prose'
        add(kind, index, index)
        index += 1
    return regions


def _map_details(value, offset, scope_prefix, ids=None):
    """Map nested evidence spans and predicate IDs, not only node provenance."""
    if isinstance(value, list):
        return [_map_details(item, offset, scope_prefix, ids) for item in value]
    if isinstance(value, tuple):
        return [_map_details(item, offset, scope_prefix, ids) for item in value]
    if isinstance(value, dict):
        result = {key: _map_details(item, offset, scope_prefix, ids) for key, item in value.items()}
        for key in ('line_start', 'line_end', 'line'):
            if type(result.get(key)) is int:
                result[key] += offset
        if isinstance(result.get('scope'), str):
            result['scope'] = result['scope'].replace(':<module>', scope_prefix + ':<module>', 1)
        if ids and result.get('predicate_id') in ids:
            result['predicate_id'] = ids[result['predicate_id']]
        return result
    return value


class _PythonV4(_Python):
    """Conservative patches around the frozen interpreter, never a sound proof."""
    def __init__(self, *args):
        super().__init__(*args)
        self.mutated_names, self.wildcard = set(), False
        try:
            tree = ast.parse(self.text)
        except (SyntaxError, ValueError, RecursionError):
            return
        aliases = []
        for item in ast.walk(tree):
            if isinstance(item, ast.ImportFrom) and any(a.name == '*' for a in item.names):
                self.wildcard = True
            if isinstance(item, (ast.Attribute, ast.Subscript)) and isinstance(item.ctx, (ast.Store, ast.Del)):
                root = item
                while isinstance(root, (ast.Attribute, ast.Subscript)):
                    root = root.value
                if isinstance(root, ast.Name):
                    self.mutated_names.add(root.id)
            if isinstance(item, ast.Assign) and isinstance(item.value, ast.Name):
                aliases.extend((t.id, item.value.id) for t in item.targets if isinstance(t, ast.Name))
        changed = True
        while changed:
            before = set(self.mutated_names)
            for a, b in aliases:
                if a in before or b in before:
                    self.mutated_names.update((a, b))
            changed = before != self.mutated_names
        if self.mutated_names or self.wildcard:
            self.unknown(tree, 'symbol_identity_invalidated_conservatively',
                         mutated_names=sorted(self.mutated_names), wildcard_import=self.wildcard)

    def expression(self, node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'open':
            mode = node.args[1] if len(node.args) > 1 else next(
                (kw.value for kw in node.keywords if kw.arg == 'mode'), None)
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
                text = mode.value
                valid = (sum(text.count(c) for c in 'rwxa') == 1 and
                         len(text) == len(set(text)) and set(text) <= set('rwxa+bt') and
                         not ('b' in text and 't' in text))
                if not valid:
                    for argument in [*node.args, *[kw.value for kw in node.keywords]]:
                        self.expression(argument)
                    self.unknown(node, 'invalid_literal_open_mode')
                    return Value()
        if isinstance(node, ast.Name) and (self.wildcard or node.id in self.mutated_names):
            self.unknown(node, 'mutated_or_wildcard_name_unproven')
            return Value()
        value = super().expression(node)
        if isinstance(node, (ast.Name, ast.Attribute)) and value.constant in (
                'pathlib.PurePath', 'pathlib.PurePosixPath', 'pathlib.PureWindowsPath'):
            self.unknown(node, 'pure_path_has_no_io_methods')
            return Value()
        return value

    def function(self, node):
        # Definition-time defaults and decorator expressions execute in the
        # enclosing scope. Body invocation remains unproved. Annotation timing
        # depends on Python version/future flags and is retained as uncertainty.
        for expression in [*node.decorator_list, *node.args.defaults,
                           *[d for d in node.args.kw_defaults if d is not None]]:
            self.expression(expression)
        if node.returns is not None or any(a.annotation is not None for a in
                [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]):
            self.unknown(node, 'annotation_evaluation_version_dependent')
        super().function(node)


def _python(text, file, *, line_offset=0, execution_role='source_code'):
    nodes, edges, unresolved = [], [], []
    _PythonV4(file, text, nodes, edges, unresolved).run()
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
                          execution_role=execution_role, analysis_kind='python_ast_partial_v4',
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


_OPERATIONS = {'read': 'file.read', 'open': 'file.read', 'load': 'file.read',
               'write': 'file.write', 'save': 'file.write', 'create': 'file.write',
               'delete': 'file.delete', 'remove': 'file.delete', 'unlink': 'file.delete',
               'download': 'network.get', 'fetch': 'network.get',
               'upload': 'network.post', 'post': 'network.post'}
_PROHIBITION = re.compile(r"\b(?:do\s+not|don['’]t|never|must\s+not|should\s+not)\b", re.I)
_OAUTH = re.compile(r'\b(?:oauth|scopes?)\b|https?://[^\s]+/auth/', re.I)
_TRUNCATION = re.compile(r'^\s*(?:\[TRUNCATED\]|\[\.\.\.\s*truncated.*\]|<!--\s*truncated.*-->)\s*$', re.I)


def _instruction(line, file, number):
    text = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)?', '', line)
    if _PROHIBITION.search(text):
        return None, 'prohibition'
    if _OAUTH.search(text):
        return None, 'oauth_identifier_or_scope'
    command = re.fullmatch(r'(?:run|execute)\s+(?:`?)(?:python3?|bash|sh)\s+'
                           r'((?:[\w.-]+/)*[\w.-]+\.(?:py|sh))`?[.!]?\s*', text, re.I)
    if command:
        operation, resource = 'command.exec', command[1]
    else:
        match = re.fullmatch(r'([A-Za-z]+)\s+(?:the\s+file\s+)?'
                             r'(?P<quote>[`"\']?)(?P<resource>[^\s`"\']+)(?P=quote)[.!]?\s*', text)
        if not match or match[1].lower() not in _OPERATIONS:
            return None, 'not_supported_imperative'
        operation = _OPERATIONS[match[1].lower()]
        resource = match['resource'].rstrip('.,;!')
        if operation.startswith('network.'):
            valid = re.fullmatch(r'https?://[^\s<>]+', resource)
        else:
            valid = re.fullmatch(r'(?:/|\./|\.\./|[\w.-]+/)[\w./-]+', resource)
            if match['quote'] and re.fullmatch(r'[\w.-]+\.[A-Za-z0-9]+', resource):
                valid = True
        if not valid or any(part in resource for part in ('$', '{', '}', '*', '?', '<', '>')):
            return None, 'no_bound_literal_resource'
    return make_node(file, number, number, operation, resource, line[:350],
                     execution_role='instruction', analysis_kind='narrow_imperative_literal',
                     resource_status='literal', evidence=[_span(file, number, number)],
                     kind='INSTRUCTION'), None


def extract_graph_v4(skill_id, files):
    """Extract candidate evidence from supplied text only; never read or run it.

    ``source_sha256`` hashes the exact supplied UTF-8 strings. Callers must retain
    external truncation/omission metadata: syntactically valid cuts cannot be
    discovered from strings alone.
    """
    graph = {'skill_id': skill_id, 'nodes': [], 'edges': [], 'unresolved': [], 'rejected': [],
             'regions': [], 'source_sha256': {}, 'analysis_complete': False,
             'graph_kind': 'segmented_partial_static_graph_v4',
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
                from .shell_v4 import analyze_shell
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
                    from .shell_v4 import analyze_shell
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
    return graph
