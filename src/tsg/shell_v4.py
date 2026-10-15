"""Bounded, non-executing POSIX-like shell evidence extraction.

Grammar: quoted words, backslash escapes/continuations, literal/simple-variable
assignments, newlines/semicolons, pipelines, and explicit command signatures.
Supported commands: curl (one HTTP(S) URL, GET/POST, request/data/header/output
options), cat, cp/mv (two operands), rm, mkdir, and literal interpreter script
calls. This is evidence of source semantics, never proof of invocation.
For command.exec, resource denotes the program source (script path or stdin);
interpreter and input_source are recorded separately to avoid conflating them.

Unknown options/commands do not receive guessed effects. Control operators,
substitutions and heredocs make the entire snippet unsupported. Redirection,
shell functions, environment prefixes, arbitrary CLI behavior, curl config and
remote redirects are outside this grammar. No environment or source is run.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .evidence_v4 import make_node


@dataclass
class _Word:
    parts: list[tuple[str, str]]
    start: int
    end: int
    begin: int
    finish: int
    operator: bool = False

    @property
    def text(self):
        return ''.join(s for s, _ in self.parts)


class _Unsupported(ValueError):
    def __init__(self, reason, line, detail):
        self.reason, self.line, self.detail = reason, line, detail


def _lex(text):
    words, parts = [], []
    i, line, begin, start = 0, 1, None, 1
    quote = None

    def add(s, mode):
        nonlocal begin, start
        if begin is None:
            begin, start = i, line
        parts.append((s, mode))

    def flush():
        nonlocal begin, parts
        if begin is not None:
            words.append(_Word(parts, start, line, begin, i))
            begin, parts = None, []

    while i < len(text):
        c = text[i]
        if quote == "'":
            if c == "'":
                quote = None
            else:
                add(c, 'literal')
            line += c == '\n'
            i += 1
            continue
        if c == '`' or (c == '$' and text[i:i + 2] == '$('):
            raise _Unsupported('command_substitution', line, 'No command/arithmetic substitution evaluation')
        if c == '\\':
            if i + 1 >= len(text):
                raise _Unsupported('unsupported_syntax', line, 'Trailing backslash')
            nxt = text[i + 1]
            if text[i + 1:i + 3] == '\r\n':
                line += 1
                i += 3
                continue
            if nxt == '\n':
                line += 1
                i += 2
                continue
            if quote == '"' and nxt not in '$`"\\':
                add(c, 'double')
                i += 1
                continue
            add(nxt, 'literal')
            i += 2
            continue
        if quote == '"':
            if c == '"':
                quote = None
            else:
                add(c, 'double')
            line += c == '\n'
            i += 1
            continue
        if c in "'\"":
            add('', 'literal')
            quote = c
            i += 1
            continue
        if c == '#' and begin is None:
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        if c in ' \t\r':
            flush()
            i += 1
            continue
        if c in '\n;|&<>()':
            flush()
            op = c
            if text[i:i + 2] in {'&&', '||', '<<', '>>', ';;'}:
                op = text[i:i + 2]
            words.append(_Word([(op, 'literal')], line, line, i, i + len(op), True))
            i += len(op)
            line += c == '\n'
            continue
        add(c, 'unquoted')
        i += 1
    if quote:
        raise _Unsupported('unsupported_syntax', line, 'Unclosed shell quote')
    flush()
    # Coalesce adjacent pieces of a quote mode so simple variables can be read.
    for word in words:
        merged = []
        for value, mode in word.parts:
            if merged and merged[-1][1] == mode:
                merged[-1] = (merged[-1][0] + value, mode)
            else:
                merged.append((value, mode))
        word.parts = merged
    return words


_VARIABLE = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})')
_ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')
_CONTROL = {'if', 'then', 'else', 'elif', 'fi', 'for', 'while', 'until', 'do', 'done', 'case', 'esac', 'function', 'select', '{', '}', '!'}
_SHELL_ENVIRONMENT = {'IFS', 'PATH', 'CDPATH', 'ENV', 'BASH_ENV', 'SHELLOPTS', 'BASHOPTS', 'GLOBIGNORE'}


def _expand(word, env, *, assignment=False):
    values, producers = [], []
    for value, mode in word.parts:
        if mode == 'literal':
            values.append(value)
            continue
        if mode == 'unquoted' and any(c in value for c in '*?[]{}~'):
            # ${NAME} braces belong to parameter syntax, not filename expansion.
            scrubbed = _VARIABLE.sub('', value)
            if any(c in scrubbed for c in '*?[]{}~'):
                return None, producers
        last, fragments = 0, []
        for match in _VARIABLE.finditer(value):
            if '$' in value[last:match.start()]:
                return None, producers
            fragments.append(value[last:match.start()])
            name = match.group(1).strip('{}')
            bound, producer = env.get(name, (None, None))
            if producer:
                producers.append(producer)
            if bound is None:
                return None, producers
            if mode == 'unquoted' and not assignment and (not bound or re.search(r'[\s*?\[\]]', bound)):
                return None, producers
            fragments.append(bound)
            last = match.end()
        if '$' in value[last:]:
            return None, producers
        fragments.append(value[last:])
        values.append(''.join(fragments))
    return ''.join(values), list(dict.fromkeys(producers))


def analyze_shell(text, file, *, line_offset=0, execution_role='source_code'):
    """Return provenance-bearing nodes, DATA/ORDER edges and uncertainty ledgers."""
    result = {'nodes': [], 'edges': [], 'unresolved': [], 'rejected': []}
    if not isinstance(line_offset, int) or line_offset < 0:
        raise ValueError('line_offset must be a nonnegative integer')

    def unresolved(reason, start, end=None, **detail):
        result['unresolved'].append({'file': file, 'line_start': start + line_offset,
                                     'line_end': (end or start) + line_offset,
                                     'reason': reason, **detail})

    try:
        words = _lex(text)
    except _Unsupported as exc:
        unresolved(exc.reason, exc.line, detail=exc.detail)
        return result
    command_start = True
    for word in words:
        assignment = (_ASSIGNMENT.match(word.parts[0][0])
                      if word.parts and word.parts[0][1] == 'unquoted' else None)
        if command_start and assignment and assignment.group(0)[:-1] in _SHELL_ENVIRONMENT:
            unresolved('unsupported_shell_environment', word.start,
                       detail='Special shell environment mutation changes supported expansion/command assumptions')
            return result
        if word.operator and word.text == '<<':
            unresolved('heredoc', word.start, detail='Heredoc bodies are outside the supported grammar')
            return result
        if ((word.operator and word.text not in {'\n', ';', '|', '<', '>', '>>'})
                or (command_start and not word.operator and word.text in _CONTROL
                    and all(mode == 'unquoted' for _, mode in word.parts))):
            unresolved('unsupported_control', word.start, detail='Control scope and mutations are unproved')
            return result
        command_start = word.operator and word.text in {'\n', ';', '|'}

    env, previous, pipe_from = {}, [], []
    pipeline_connected = False
    commands, current = [], []
    for word in words:
        if word.operator and word.text in {'\n', ';', '|'}:
            if current:
                commands.append((current, word.text))
                current = []
            elif word.text in {'|', ';'}:
                unresolved('unsupported_syntax', word.start, detail='Empty command before operator')
                return result
        else:
            current.append(word)
    if current:
        commands.append((current, None))
    elif commands and commands[-1][1] == '|':
        unresolved('unsupported_syntax', commands[-1][0][-1].end, detail='Missing pipeline consumer')
        return result

    by_id = {}

    def edge(source, target, kind, semantics):
        if source != target:
            item = {'source': source, 'target': target, 'type': kind, 'semantics': semantics}
            if item not in result['edges']:
                result['edges'].append(item)

    for command, separator in commands:
        start, end = command[0].start, command[-1].end
        raw = text[command[0].begin:command[-1].finish]
        command_nodes = []
        stream_info = {}
        expanded = [_expand(w, env) for w in command]
        args = [v for v, _ in expanded]
        deps = list(dict.fromkeys(p for _, ps in expanded for p in ps))

        def emit(operation, resource, *, role='target', kind='CODE_ACTION', evidence_extra=None, node_extra=None, target_deps=()):
            if resource in {'', 'unknown'}:
                unresolved('invalid_or_reserved_target', start, end, operation=operation)
                resource = None
            status = ('resolved_constant' if target_deps else 'literal') if resource is not None else 'unknown'
            evidence = [{'file': file, 'line_start': start + line_offset,
                         'line_end': end + line_offset, 'source': raw,
                         'argument_role': role, **(evidence_extra or {})}]
            for producer in target_deps:
                for span in by_id[producer]['resource_evidence']:
                    if span not in evidence:
                        evidence.append(dict(span))
            # Pair source character position with local effect index injectively;
            # two identical commands on one line must still have distinct IDs.
            local_index = len(command_nodes)
            position = command[0].begin
            paired_index = (position + local_index) * (position + local_index + 1) // 2 + local_index
            node = make_node(file, start + line_offset, end + line_offset,
                             operation, resource if resource is not None else 'unknown',
                             f'{operation}: {resource if resource is not None else "unresolved"}',
                             execution_role=execution_role, analysis_kind='shell_static',
                             resource_status=status, evidence=evidence,
                             effect_index=paired_index, kind=kind, **(node_extra or {}))
            result['nodes'].append(node)
            by_id[node['id']] = node
            command_nodes.append(node['id'])
            for producer in deps:
                edge(producer, node['id'], 'DATA', 'simple variable value used by this command')
            if resource is None:
                unresolved('dynamic_target', start, end, operation=operation, node_id=node['id'])
            return node

        def fail(reason, detail):
            unresolved(reason, start, end, detail=detail, source=raw)
            env.clear()

        match = (_ASSIGNMENT.match(command[0].parts[0][0])
                 if command[0].parts and command[0].parts[0][1] == 'unquoted' else None)
        if match:
            if len(command) != 1 or pipeline_connected or separator == '|':
                fail('unsupported_syntax', 'Only standalone single-variable assignments are supported')
            else:
                name = match.group(0)[:-1]
                # Strip NAME= while preserving quoting and expansion modes of value.
                skip, value_parts = len(name) + 1, []
                for part, mode in command[0].parts:
                    cut = min(skip, len(part))
                    skip -= cut
                    value_parts.append((part[cut:], mode))
                value_word = _Word(value_parts, start, end, command[0].begin, command[0].finish)
                value, value_deps = _expand(value_word, env, assignment=True)
                deps = value_deps
                binding = emit('value.bind', name, role='assignment', kind='DATA_OBJECT',
                               evidence_extra={'variable': name, 'bound_value': value})
                env[name] = (value, binding['id'])
                if value is None:
                    unresolved('dynamic_binding', start, end, variable=name)
        elif any(w.operator for w in command):
            fail('unsupported_syntax', 'Redirection is outside the explicit command signatures')
        elif not args or args[0] is None or command[0].text != args[0]:
            fail('unsupported_command', 'Dynamic command name')
        elif args[0] == 'curl':
            stream_info = _curl(args[1:], emit, fail, unresolved, start, end, edge, [ps for _, ps in expanded[1:]]) or {}
        elif args[0] in {'cat', 'cp', 'mv', 'rm', 'mkdir'}:
            stream_info = _files(args[0], args[1:], emit, fail, edge, [ps for _, ps in expanded[1:]]) or {}
        elif args[0] in {'sh', 'bash', 'python', 'python3', 'node', 'ruby', 'perl'}:
            operands = args[1:]
            if operands and operands[0] is not None and operands[0].startswith('-'):
                fail('unsupported_option', 'Interpreter flags and inline programs are unsupported')
            elif operands:
                emit('command.exec', operands[0], role='script',
                     target_deps=expanded[1][1],
                     node_extra={'interpreter': args[0], 'input_source': 'script_file'})
                # Script mutations of caller shell are not assumed; invocation unproved.
            elif pipeline_connected or args[0] in {'sh', 'bash'}:
                script = emit('command.exec', 'stdin', role='script_stream',
                              node_extra={'interpreter': args[0], 'input_source': 'stdin'})
                stream_info = {'stdin_nodes': [script['id']]}
                if not pipeline_connected:
                    unresolved('unproved_invocation', start, end, detail='Interpreter stdin is not supplied')
            else:
                fail('unsupported_command', 'Interactive interpreter semantics unsupported')
        else:
            fail('unsupported_command', f'No command signature for {args[0]}')
        for target in command_nodes:
            for source in previous:
                edge(source, target, 'ORDER', 'source command order only; not control dominance')
        for target in stream_info.get('stdin_nodes', []):
            for source in pipe_from:
                edge(source, target, 'DATA', 'supported stdout-to-stdin content dependency; invocation unproved')
        previous = command_nodes or previous
        stdout_nodes = list(stream_info.get('stdout_nodes', []))
        if stream_info.get('passthrough'):
            stdout_nodes.extend(pipe_from)
        pipe_from = list(dict.fromkeys(stdout_nodes)) if separator == '|' else []
        pipeline_connected = separator == '|'
    return result


def _curl(args, emit, fail, unresolved, start, end, edge, arg_deps):
    urls, inputs, outputs, payloads, headers = [], [], [], [], []
    method, method_given, get, i, positional = None, False, False, 0, False
    consumes_stdin, output_given, output_stdout = False, False, False
    dynamic_positional = False
    argument_options = {'--url', '-X', '--request', '-o', '--output', '-d', '--data',
                        '--data-raw', '--data-binary', '-H', '--header'}
    while i < len(args):
        arg = args[i]
        if arg is None:
            # A dynamic token could change option structure, so do not invent a URL.
            if positional or not urls:
                urls.append((None, arg_deps[i]))
                dynamic_positional |= not positional
                i += 1
                continue
            fail('unsupported_syntax', 'Dynamic untyped curl argument')
            return
        if arg == '--' and not positional:
            positional, i = True, i + 1
            continue
        if positional or not arg.startswith('-'):
            urls.append((arg, arg_deps[i]))
            i += 1
            continue
        if arg in {'--silent', '--show-error', '--fail', '--fail-with-body'} or re.fullmatch(r'-[sSf]+', arg):
            i += 1
            continue
        if arg in {'-G', '--get'}:
            get, i = True, i + 1
            continue
        option, equals, value = arg.partition('=')
        if option not in argument_options or (equals and not option.startswith('--')):
            fail('unsupported_option', f'Unsupported curl option: {arg}')
            return
        if not equals:
            i += 1
            if i >= len(args):
                fail('unsupported_syntax', f'Missing argument for {option}')
                return
            value = args[i]
        if option == '--url':
            urls.append((value, arg_deps[i]))
        elif option in {'-X', '--request'}:
            method, method_given = value, True
        elif option in {'-o', '--output'}:
            if output_given:
                fail('unsupported_option', 'Multiple output options are outside the one-transfer grammar')
                return
            output_given, output_stdout = True, value == '-'
            if value != '-':
                outputs.append((value, arg_deps[i]))
        elif option in {'-H', '--header'}:
            headers.append(value)
            consumes_stdin |= value == '@-'
            if value and value.startswith('@') and value != '@-':
                inputs.append((value[1:], arg_deps[i]))
        else:
            payloads.append(value)
            consumes_stdin |= option != '--data-raw' and value == '@-'
            if option != '--data-raw' and value and value.startswith('@') and value != '@-':
                inputs.append((value[1:], arg_deps[i]))
        i += 1
    if len(urls) != 1:
        fail('unsupported_syntax', 'curl requires exactly one URL in this grammar')
        return
    if dynamic_positional and (inputs or outputs):
        fail('dynamic_argument_structure', 'Unknown positional argument may be a curl option; file effects are unproved')
        return
    if method_given and method is None:
        fail('dynamic_method', 'curl request method binding is unresolved')
        return
    chosen_method = method if method_given else ('GET' if get or not payloads else 'POST')
    if chosen_method not in {'GET', 'POST'}:
        fail('unsupported_option', 'Only literal GET/POST curl request methods are supported')
        return
    target, target_deps = urls[0]
    if target is not None and (not re.match(r'^https?://[^\s/]+', target) or any(c in target for c in '{}[]')):
        fail('unsupported_syntax', 'Only literal HTTP(S) URLs without curl URL globbing are supported')
        return
    network = emit('network.' + chosen_method.lower(), target, role='url',
                   target_deps=target_deps,
                   evidence_extra={'method': chosen_method, 'payloads': payloads, 'headers': headers})
    for value, value_deps in inputs:
        read = emit('file.read', value, role='request_input', target_deps=value_deps)
        edge(read['id'], network['id'], 'DATA', 'file content supplies curl request data/header')
    for value, value_deps in outputs:
        write = emit('file.write', value, role='response_output', target_deps=value_deps)
        edge(network['id'], write['id'], 'DATA', 'curl response supplies output file content')
    if any(value is None for value in payloads):
        unresolved('dynamic_payload', start, end, detail='curl payload binding is unresolved')
    if any(value is None for value in headers):
        unresolved('dynamic_header', start, end, detail='curl header binding is unresolved')
    return {'stdin_nodes': [network['id']] if consumes_stdin else [],
            'stdout_nodes': [network['id']] if not output_given or output_stdout else []}


def _files(command, args, emit, fail, edge, arg_deps):
    allowed = {'cat': {'-n', '-b', '-s'}, 'cp': set(), 'mv': set(),
               'rm': {'-f', '-r', '-R', '-rf', '-fr', '--force', '--recursive'},
               'mkdir': {'-p', '--parents'}}[command]
    operands, positional, dynamic_untyped = [], False, False
    operand_deps = []
    for index, arg in enumerate(args):
        if arg == '--' and not positional:
            positional = True
        elif not positional and arg is not None and arg.startswith('-') and arg != '-':
            if arg not in allowed:
                fail('unsupported_option', f'Unsupported {command} option: {arg}')
                return
        else:
            operands.append(arg)
            operand_deps.append(arg_deps[index])
            dynamic_untyped |= arg is None and not positional
    if dynamic_untyped and len(operands) > 1:
        fail('dynamic_argument_structure', 'Unknown positional argument may be an option; later operand roles are unproved')
        return
    if command in {'cp', 'mv'}:
        if len(operands) != 2:
            fail('unsupported_syntax', f'{command} requires exactly two operands')
            return
        read = emit('file.read', operands[0], role='source', target_deps=operand_deps[0])
        write = emit('file.write', operands[1], role='destination', target_deps=operand_deps[1])
        edge(read['id'], write['id'], 'DATA', 'source file content supplies copy/move destination')
        if command == 'mv':
            emit('file.delete', operands[0], role='source', target_deps=operand_deps[0])
    elif command == 'cat':
        reads = []
        for value, value_deps in zip(operands, operand_deps):
            if value != '-':
                reads.append(emit('file.read', value, role='input', target_deps=value_deps)['id'])
        return {'stdout_nodes': reads, 'passthrough': not operands or '-' in operands}
    elif not operands:
        fail('unsupported_syntax', f'{command} requires a target')
    else:
        for value, value_deps in zip(operands, operand_deps):
            emit('file.delete' if command == 'rm' else 'file.write', value, role='target', target_deps=value_deps)
