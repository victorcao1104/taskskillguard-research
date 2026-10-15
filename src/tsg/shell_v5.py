"""Explicit Phase-5 shell signatures, never source execution or a full parser.

The v4 lexer, expansion rules and existing signatures are reused unchanged.
The local dispatcher preserves their provenance without global monkeypatches.
Only a single terminal stdout > or >> redirect on echo/printf is added.
"""
from __future__ import annotations

import re

from .evidence_v4 import make_node
from .shell_v4 import (_lex, _expand, _Word, _Unsupported, _ASSIGNMENT,
                       _CONTROL, _SHELL_ENVIRONMENT, _curl, _files)


def _extension(command, args, expanded, emit, fail, unresolved, start, end, edge):
    head = args[0]
    if any(arg is None for arg in args):
        fail('unknown_extension_expansion', 'No partial effects for unknown argument expansion')
        return {}
    if head in {'echo', 'printf'}:
        operators = [i for i, word in enumerate(command) if word.operator]
        if not operators:
            # No privileged sink. Retain the bounded coverage record and do
            # not fabricate a file effect from ordinary terminal output.
            unresolved('stdout_only_no_file_effect', start, end, command=head)
            return {}
        if (len(operators) != 1 or operators[0] != len(command) - 2
                or args[-2] not in {'>', '>>'} or operators[0] < 2):
            fail('unsupported_extension_redirection', 'Only one terminal stdout > or >> redirect is supported')
            return {}
        index = operators[0]
        if command[index - 1].finish == command[index].begin and args[index - 1].isdigit():
            fail('unsupported_extension_redirection', 'File descriptor redirection is not supported')
            return {}
        payload = args[1:index]
        if head == 'echo':
            if payload[0].startswith('-') or any('\\' in word for word in payload):
                fail('unsupported_extension_option', 'echo flags and implementation-dependent escapes are unsupported')
                return {}
        else:
            format_string = payload[0]
            if format_string.startswith('-'):
                fail('unsupported_extension_option', 'printf options are unsupported')
                return {}
            scrubbed = re.sub(r'%%|%s|\\[nrt\\]', '', format_string)
            count = len(re.findall(r'%s', re.sub(r'%%', '', format_string)))
            if '%' in scrubbed or '\\' in scrubbed or count != len(payload) - 1:
                fail('unsupported_extension_format', 'printf supports only %s, %%, simple escapes and exact argument count')
                return {}
        if not args[-1] or args[-1] == 'unknown':
            fail('invalid_extension_target', 'Empty or reserved target is not a resolved resource')
            return {}
        emit('file.write', args[-1], role='stdout_redirect', target_deps=expanded[-1][1],
             node_extra={'extension_version': 5, 'write_mode': 'append' if args[-2] == '>>' else 'truncate'})
        return {}
    if any(word.operator for word in command):
        fail('unsupported_extension_redirection', 'This signature accepts no redirection')
        return {}
    if head == 'tee':
        positional, append, paths = False, False, []
        for index, arg in enumerate(args[1:], 1):
            if arg == '--' and not positional:
                positional = True
            elif arg in {'-a', '--append'} and not positional:
                append = True
            elif arg.startswith('-') and not positional:
                fail('unsupported_extension_option', 'Only tee append and -- options are supported')
                return {}
            elif not arg or arg == 'unknown':
                fail('invalid_extension_target', 'Empty or reserved target is not a resolved resource')
                return {}
            else:
                paths.append((arg, expanded[index][1]))
        if not paths:
            unresolved('stdout_only_no_file_effect', start, end, command=head)
            return {'passthrough': True}
        writes = [emit('file.write', path, role='tee_output', target_deps=deps,
                       node_extra={'extension_version': 5, 'write_mode': 'append' if append else 'truncate'})['id']
                  for path, deps in paths]
        return {'stdin_nodes': writes, 'passthrough': True}
    urls, output, output_deps, output_given, index, positional = [], None, (), False, 1, False
    while index < len(args):
        arg = args[index]
        if arg == '--' and not positional:
            positional = True
        elif arg in {'-O', '--output-document'} and not positional:
            if output_given or index + 1 >= len(args):
                fail('unsupported_extension_option', 'wget requires at most one output option with an argument')
                return {}
            index += 1
            output, output_deps, output_given = args[index], expanded[index][1], True
        elif arg.startswith('--output-document=') and not positional:
            if output_given:
                fail('unsupported_extension_option', 'Multiple wget output options are unsupported')
                return {}
            output, output_deps, output_given = arg.partition('=')[2], expanded[index][1], True
        elif arg.startswith('-') and not positional:
            fail('unsupported_extension_option', 'Only explicit wget output and -- options are supported')
            return {}
        else:
            urls.append((arg, expanded[index][1]))
        index += 1
    if len(urls) != 1 or not re.fullmatch(r'https?://[^\s/]+(?:/[^\s]*)?', urls[0][0]) or any(c in urls[0][0] for c in '{}[]'):
        fail('unsupported_extension_url', 'Exactly one HTTP(S) URL without glob syntax is required')
        return {}
    if output_given and (not output or output == 'unknown'):
        fail('invalid_extension_target', 'Empty or reserved output is unsupported')
        return {}
    network = emit('network.get', urls[0][0], role='url', target_deps=urls[0][1],
                   node_extra={'extension_version': 5})
    if output_given and output != '-':
        write = emit('file.write', output, role='response_output', target_deps=output_deps,
                     node_extra={'extension_version': 5})
        edge(network['id'], write['id'], 'DATA', 'wget response supplies explicit output file content')
    elif not output_given:
        unresolved('implicit_download_destination', start, end,
                   detail='Default download filename depends on URL, response and filesystem state')
    return {'stdout_nodes': [network['id']] if output == '-' else []}


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
    extension_identity_unproven = False
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
        if command_start and word.text in {'alias', 'unalias', 'source', '.', 'eval', 'enable', 'builtin'}:
            extension_identity_unproven = True
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
                             execution_role=execution_role, analysis_kind=('shell_static_v5' if (node_extra or {}).get('extension_version') == 5 else 'shell_static'),
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
        elif args and args[0] in {'wget', 'tee', 'echo', 'printf'} and command[0].text == args[0]:
            if extension_identity_unproven:
                fail('extension_command_identity_unproven', 'Shell command rebinding or dynamic source exists in this snippet')
            else:
                stream_info = _extension(command, args, expanded, emit, fail, unresolved, start, end, edge)
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

