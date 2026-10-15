"""Hand-specified shell effects; snippets are analyzed, never executed."""
import pytest


def analyze(text, **kwargs):
    from tsg.shell_v4 import analyze_shell
    return analyze_shell(text, 'scripts/example.sh', **kwargs)


def effects(result):
    return [(n['operation'], n['resource']) for n in result['nodes']
            if n['kind'] == 'CODE_ACTION']


def test_curl_get_uses_url_argument_not_header_or_output():
    result = analyze('curl -sS --header "Referer: https://decoy.invalid" --url https://api.invalid/a -o result.json')
    assert effects(result) == [('network.get', 'https://api.invalid/a'), ('file.write', 'result.json')]
    assert not result['unresolved']


def test_multiline_post_data_and_source_mapping():
    result = analyze('curl --url https://api.invalid/a \\\n  --data \'{"message": "one\ntwo"}\'\n', line_offset=20, execution_role='example')
    assert effects(result) == [('network.post', 'https://api.invalid/a')]
    node = result['nodes'][0]
    assert node['provenance']['line_start'] == 21
    assert node['provenance']['line_end'] == 23
    assert node['execution_role'] == 'example'
    assert node['invocation_proven'] is False
    assert node['authorization_source'] is False


def test_post_input_and_output_are_distinct_effects_with_distinct_ids():
    result = analyze('curl -X POST --data-binary @payload.json https://api.invalid/upload --output response.json')
    assert effects(result) == [('network.post', 'https://api.invalid/upload'), ('file.read', 'payload.json'), ('file.write', 'response.json')]
    assert len({n['id'] for n in result['nodes']}) == 3


def test_request_get_and_get_flag_override_data_default():
    assert effects(analyze('curl -X GET -d x=1 https://api.invalid/a')) == [('network.get', 'https://api.invalid/a')]
    assert effects(analyze('curl --get --data x=1 --url=https://api.invalid/a')) == [('network.get', 'https://api.invalid/a')]


def test_assignment_rebinding_and_single_quotes_preserve_shell_meaning():
    result = analyze('URL=https://a.invalid\ncurl "$URL"\nURL=https://b.invalid\ncurl "${URL}"\nrm \'$URL\'')
    assert effects(result) == [('network.get', 'https://a.invalid'), ('network.get', 'https://b.invalid'), ('file.delete', '$URL')]
    assert any(e['type'] == 'DATA' for e in result['edges'])


def test_unset_variable_is_unresolved_and_never_resolved_as_literal():
    result = analyze('curl "$URL"')
    assert effects(result) == [('network.get', 'unknown')]
    assert result['nodes'][0]['resource_status'] == 'unknown'
    assert any(u['reason'] == 'dynamic_target' for u in result['unresolved'])


def test_pipe_is_stream_dependency_and_source_order_is_not_control():
    result = analyze('curl https://api.invalid/install | sh\nrm temporary')
    assert effects(result) == [('network.get', 'https://api.invalid/install'), ('command.exec', 'stdin'), ('file.delete', 'temporary')]
    ids = [n['id'] for n in result['nodes']]
    assert any(e['source'] == ids[0] and e['target'] == ids[1] and e['type'] == 'DATA' for e in result['edges'])
    assert any(e['type'] == 'ORDER' for e in result['edges'])
    assert all(e['type'] in {'DATA', 'ORDER'} for e in result['edges'])


@pytest.mark.parametrize('source, reason', [
    ('curl --config settings https://api.invalid', 'unsupported_option'),
    ('curl "$(cat url)"', 'command_substitution'),
    ('curl `cat url`', 'command_substitution'),
    ('cat <<EOF\ntext\nEOF', 'heredoc'),
    ('if true; then curl https://api.invalid; fi', 'unsupported_control'),
    ('curl https://api.invalid && rm x', 'unsupported_control'),
])
def test_unsupported_semantics_abstain_with_reason(source, reason):
    result = analyze(source)
    assert not effects(result)
    assert any(u['reason'] == reason for u in result['unresolved'])


def test_unsupported_mutation_invalidates_previous_constant():
    result = analyze('URL=https://a.invalid\nread URL\ncurl "$URL"')
    assert effects(result) == [('network.get', 'unknown')]
    assert any(u['reason'] == 'unsupported_command' for u in result['unresolved'])


def test_files_and_interpreter_signatures_preserve_multiple_effects():
    result = analyze('cat input.txt; cp source.txt dest.txt; mv old.txt new.txt; rm -f gone.txt; mkdir -p out; python tool.py')
    assert effects(result) == [('file.read', 'input.txt'), ('file.read', 'source.txt'), ('file.write', 'dest.txt'),
                               ('file.read', 'old.txt'), ('file.write', 'new.txt'), ('file.delete', 'old.txt'),
                               ('file.delete', 'gone.txt'), ('file.write', 'out'), ('command.exec', 'tool.py')]


def test_comments_empty_input_and_literal_data_have_no_file_effect():
    assert not analyze('# curl https://decoy.invalid\n')['nodes']
    assert effects(analyze('curl --data-raw @literal https://api.invalid')) == [('network.post', 'https://api.invalid')]
    assert not analyze('')['nodes']


def test_unquoted_expansion_and_glob_do_not_claim_exact_path():
    result = analyze('P="two words"\nrm $P\ncat *.txt')
    assert effects(result) == [('file.delete', 'unknown'), ('file.read', 'unknown')]
    assert sum(u['reason'] == 'dynamic_target' for u in result['unresolved']) == 2


def test_bad_quotes_report_syntax_without_crash():
    result = analyze('curl "https://api.invalid')
    assert not result['nodes']
    assert any(u['reason'] == 'unsupported_syntax' for u in result['unresolved'])


def test_dynamic_request_method_cannot_become_resolved_get():
    result = analyze('curl --request "$METHOD" https://api.invalid')
    assert not effects(result)
    assert any(u['reason'] == 'dynamic_method' for u in result['unresolved'])


def test_repeated_same_line_commands_keep_distinct_source_ids():
    result = analyze('curl https://api.invalid; curl https://api.invalid')
    assert len(result['nodes']) == 2
    assert len({n['id'] for n in result['nodes']}) == 2


def test_keyword_in_operand_position_is_data():
    assert effects(analyze('cat if; curl --data then https://api.invalid')) == [
        ('file.read', 'if'), ('network.post', 'https://api.invalid')]


def test_resource_evidence_is_source_located_list():
    result = analyze('curl https://api.invalid', line_offset=8)
    evidence = result['nodes'][0]['resource_evidence']
    assert isinstance(evidence, list)
    assert evidence[0]['file'] == 'scripts/example.sh'
    assert evidence[0]['line_start'] == evidence[0]['line_end'] == 9
    assert evidence[0]['argument_role'] == 'url'


def test_quoted_assignment_command_does_not_bind_variable():
    result = analyze('"URL=https://api.invalid"\ncurl "$URL"')
    assert effects(result) == [('network.get', 'unknown')]
    assert any(u['reason'] == 'unsupported_command' for u in result['unresolved'])


def test_empty_assignment_can_be_used_as_payload_without_crash():
    result = analyze('BODY=""\ncurl --data "$BODY" https://api.invalid')
    assert effects(result) == [('network.post', 'https://api.invalid')]


def test_crlf_line_continuation_maps_source_lines():
    result = analyze('curl \\\r\n  --url https://api.invalid\r\n')
    assert effects(result) == [('network.get', 'https://api.invalid')]
    assert result['nodes'][0]['provenance']['line_end'] == 2


def test_request_file_and_response_file_edges_have_actual_data_roles():
    result = analyze('curl --data @request.json -o response.json https://api.invalid')
    network, read, write = [n['id'] for n in result['nodes']]
    assert any(e['source'] == read and e['target'] == network and e['type'] == 'DATA' for e in result['edges'])
    assert any(e['source'] == network and e['target'] == write and e['type'] == 'DATA' for e in result['edges'])


def test_special_shell_environment_cannot_preserve_false_unquoted_binding():
    result = analyze('URL=https://api.invalid\nIFS=:\ncurl $URL')
    assert not effects(result)
    assert any(u['reason'] == 'unsupported_shell_environment' for u in result['unresolved'])


def test_resolved_variable_evidence_includes_definition_location():
    result = analyze('URL=https://api.invalid\ncurl "$URL"')
    network = [n for n in result['nodes'] if n['operation'] == 'network.get'][0]
    assert any(e['line_start'] == 1 and 'https://api.invalid' in e['source'] for e in network['resource_evidence'])


@pytest.mark.parametrize('source', ['; curl https://api.invalid', 'curl https://api.invalid; ; rm x'])
def test_invalid_separator_grammar_does_not_invent_effects(source):
    result = analyze(source)
    assert not effects(result)
    assert any(u['reason'] == 'unsupported_syntax' for u in result['unresolved'])


def test_unknown_header_and_payload_are_explicit_coverage_failures():
    result = analyze('curl -H "$HEADER" -d "$BODY" https://api.invalid')
    assert effects(result) == [('network.post', 'https://api.invalid')]
    assert {u['reason'] for u in result['unresolved']} >= {'dynamic_header', 'dynamic_payload'}


def test_copied_source_produces_destination_data():
    result = analyze('cp source.txt destination.txt')
    source, destination = [n['id'] for n in result['nodes']]
    assert any(e['source'] == source and e['target'] == destination and e['type'] == 'DATA' for e in result['edges'])


@pytest.mark.parametrize('option', ['-X=GET', '-o=out.txt', '-H=@headers.txt'])
def test_short_option_equals_is_not_misread_as_long_option_syntax(option):
    result = analyze(f'curl {option} https://api.invalid')
    assert not effects(result)
    assert any(u['reason'] == 'unsupported_option' for u in result['unresolved'])


def test_curl_saved_to_file_does_not_supply_body_to_pipeline():
    result = analyze('curl -o saved.sh https://api.invalid | sh')
    shell = [n['id'] for n in result['nodes'] if n['operation'] == 'command.exec'][0]
    assert not any(e['type'] == 'DATA' and e['target'] == shell for e in result['edges'])


def test_curl_without_stdin_argument_does_not_consume_pipeline():
    result = analyze('cat secret.txt | curl https://api.invalid')
    assert not any(e['type'] == 'DATA' for e in result['edges'])


def test_curl_stdin_payload_consumes_input_pipeline():
    result = analyze('cat request.json | curl --data-binary @- https://api.invalid')
    read, network = [n['id'] for n in result['nodes']]
    assert any(e['type'] == 'DATA' and e['source'] == read and e['target'] == network for e in result['edges'])


def test_cat_stdin_passthrough_retains_real_pipeline_source():
    result = analyze('curl https://api.invalid | cat | sh')
    network, shell = [n['id'] for n in result['nodes']]
    assert any(e['type'] == 'DATA' and e['source'] == network and e['target'] == shell for e in result['edges'])


def test_interpreter_identity_is_separate_from_program_source():
    result = analyze('curl https://api.invalid | bash\npython task.py')
    programs = [n for n in result['nodes'] if n['operation'] == 'command.exec']
    assert [(n['resource'], n['interpreter'], n['input_source']) for n in programs] == [
        ('stdin', 'bash', 'stdin'), ('task.py', 'python', 'script_file')]


@pytest.mark.parametrize('source', ['rm "$UNKNOWN" kept.txt', 'cp "$UNKNOWN" output.txt',
                                   'curl "$UNKNOWN" -o output.txt'])
def test_unknown_untyped_argument_cannot_turn_later_words_into_certain_effects(source):
    result = analyze(source)
    assert not effects(result)
    assert any(u['reason'] == 'dynamic_argument_structure' for u in result['unresolved'])


def test_explicit_dynamic_url_option_preserves_typed_response_output():
    result = analyze('curl --url "$UNKNOWN" -o output.txt')
    assert effects(result) == [('network.get', 'unknown'), ('file.write', 'output.txt')]
def test_literal_target_resolution_does_not_inherit_payload_binding():
    from tsg.shell_v4 import analyze_shell
    graph = analyze_shell('BODY=hello\ncurl -d "$BODY" https://literal.invalid/path\n', 'main.sh')
    post = next(n for n in graph['nodes'] if n['operation'] == 'network.post')
    assert post['resource_status'] == 'literal'
    assert {e['line_start'] for e in post['resource_evidence']} == {2}
    assert any(e['target'] == post['id'] and e['type'] == 'DATA' for e in graph['edges'])


def test_bound_delete_and_directory_targets_retain_binding_evidence():
    from tsg.shell_v4 import analyze_shell
    graph = analyze_shell('TARGET=old.txt\nrm "$TARGET"\nmkdir "$TARGET"\n', 'main.sh')
    effects = [n for n in graph['nodes'] if n['privilege_relevant']]
    assert len(effects) == 2
    assert all(n['resource_status'] == 'resolved_constant' for n in effects)
    assert all(any(e['line_start'] == 1 for e in n['resource_evidence']) for n in effects)

