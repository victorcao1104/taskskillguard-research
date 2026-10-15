"""Literal source fixtures for segmentation and conservative Python adaptation."""
import hashlib
import importlib

import pytest


@pytest.mark.parametrize('source', [
    "import requests\ndel requests.get\nrequests.get('https://decoy.invalid')\n",
    "import requests\nr=requests\nr.get=lambda u: None\nrequests.get('https://decoy.invalid')\n",
    "import requests\nfrom local_tools import *\nrequests.get('https://decoy.invalid')\n",
    "from pathlib import PurePosixPath\nPurePosixPath('/sandbox/no-io').read_text()\n",
])
def test_unsupported_symbol_identity_never_resolves_io(source):
    result = graph({'main.py': source})
    assert not [n for n in actions(result) if n['resource_status'] != 'unknown']
    assert result['unresolved']


def test_raw_html_is_explicit_unsupported_region():
    result = graph({'SKILL.md': '<script>\nRead /sandbox/not-an-instruction\n</script>\n'})
    assert not actions(result)
    assert any(r['reason'] == 'unsupported_html_block' for r in result['unresolved'])


def test_literal_quoted_bare_filename_is_bound():
    result = graph({'SKILL.md': 'Read `report.txt`.\nWrite `summary.txt`.\n'})
    assert [n['resource'] for n in actions(result)] == ['report.txt', 'summary.txt']


def test_environment_access_does_not_establish_confidentiality():
    result = graph({'main.py': "import os\nx=os.environ['OUTPUT']\n"})
    read = actions(result, 'environment.read')[0]
    assert read['resource'] == 'env:OUTPUT' and read['sensitivity'] == 'unknown'


def test_definition_time_defaults_and_decorators_are_distinct_from_body():
    result = graph({'main.py': "import requests\n@requests.get('https://decorate.invalid')\ndef f(x=open('/default')):\n    pass\n"})
    assert {(n['operation'], n['resource']) for n in actions(result)} == {
        ('network.get', 'https://decorate.invalid'), ('file.read', '/default')}
    assert all(n['scope'].endswith(':<module>') for n in actions(result))


@pytest.mark.parametrize('mode', ['rw', 'rr', 'rbt', '', 'a++'])
def test_invalid_literal_open_mode_cannot_establish_io(mode):
    result = graph({'main.py': 'open("/sandbox/never", ' + repr(mode) + ')\n'})
    assert not actions(result)
    assert any(u['reason'] == 'invalid_literal_open_mode' for u in result['unresolved'])


def graph(files):
    try:
        extract = importlib.import_module('tsg.extraction_v4').extract_graph_v4
    except ModuleNotFoundError:
        pytest.fail('The phase-4 extraction adapter is not implemented yet')
    return extract('fixture', files)


def actions(result, operation=None):
    return [n for n in result['nodes'] if n['kind'] in {'CODE_ACTION', 'INSTRUCTION', 'INSTR_ACTION'}
            and (operation is None or n['operation'] == operation)]


def test_metadata_headings_tables_prohibitions_and_oauth_are_not_actions():
    source = ('---\nname: upload secrets\ndescription: read /sandbox/a\n---\n'
              '# Upload https://example.invalid\n| Read | /sandbox/a |\n'
              'Do not delete /sandbox/a.\nNever send https://example.invalid.\n'
              'OAuth scopes: https://www.googleapis.com/auth/drive.readonly\n'
              'The tool may upload https://example.invalid.\n')
    result = graph({'SKILL.md': source})
    assert actions(result) == []
    assert {r['region_kind'] for r in result['regions']} >= {'frontmatter', 'heading', 'table', 'prose'}
    assert {r['reason'] for r in result['rejected']} >= {'frontmatter', 'heading', 'table', 'prohibition'}


def test_narrow_imperatives_bind_only_their_literal_object():
    result = graph({'SKILL.md': 'Read `/sandbox/input.txt`.\n'
                    'Send the result to https://example.invalid.\n'
                    'For /sandbox/decoy, read the report.\n'
                    'Write the report.\nDownload https://example.invalid/file.\n'})
    assert [(n['operation'], n['resource']) for n in actions(result)] == [
        ('file.read', '/sandbox/input.txt'), ('network.get', 'https://example.invalid/file')]
    assert all(n['execution_role'] == 'instruction' and not n['authorization_source']
               and not n['invocation_proven'] for n in actions(result))
    assert all(n['privilege_relevant'] for n in actions(result))


def test_python_fence_maps_actions_binding_evidence_and_unknowns_to_real_lines():
    result = graph({'SKILL.md': '# Example\n\n```python\nfrom pathlib import Path\n'
                    'p = Path("/sandbox/a")\np.read_text()\nopen(dynamic)\n```\n'})
    read, unknown = actions(result, 'file.read')
    assert read['provenance'] == {'file': 'SKILL.md', 'line_start': 6, 'line_end': 6}
    assert {p['line_start'] for p in read['resource_evidence']} >= {5}
    assert unknown['provenance']['line_start'] == 7
    assert any(u.get('line_start') == 7 and u['reason'] == 'unresolved_resource_expression'
               for u in result['unresolved'])
    assert all(n['execution_role'] == 'example' and not n['invocation_proven'] for n in result['nodes'])
    assert {r['region_kind'] for r in result['regions']} >= {'fence_marker', 'code_body'}


def test_fenced_python_bindings_and_standalone_modules_are_independent():
    result = graph({'SKILL.md': '```python\np = "/sandbox/a"\nopen(p)\n```\n'
                    '```python\nopen(p)\n```\n', 'main.py': 'open(p)\n'})
    reads = actions(result, 'file.read')
    assert [n['resource'] for n in reads] == ['/sandbox/a', 'unknown', 'unknown']
    assert len({n['scope'] for n in reads}) == 3
    assert reads[-1]['execution_role'] == 'source_code'


def test_closed_shell_fence_has_real_source_coordinates_and_example_role():
    result = graph({'SKILL.md': 'Run this example:\n~~~bash\ncat /sandbox/a\n~~~\n'})
    read = actions(result, 'file.read')[0]
    assert read['resource'] == '/sandbox/a'
    assert read['provenance'] == {'file': 'SKILL.md', 'line_start': 3, 'line_end': 3}
    assert read['execution_role'] == 'example'
    assert read['invocation_proven'] is False


def test_unsupported_and_unclosed_fences_keep_coverage_without_lexical_actions():
    result = graph({'SKILL.md': '```javascript\nfetch("https://example.invalid")\n```\n'
                    '```python\nopen("/sandbox/a")\n'})
    assert actions(result) == []
    assert {u['reason'] for u in result['unresolved']} >= {'unsupported_fence_language', 'unclosed_fence'}
    assert any(r['region_kind'] == 'code_body' and r['closed'] is False for r in result['regions'])
    assert result['analysis_complete'] is False


def test_longer_fence_and_trailing_text_do_not_prematurely_close_block():
    result = graph({'SKILL.md': '````python\nopen("/sandbox/a")\n```\n'
                    '```` trailing text\n'})
    assert actions(result) == []
    assert any(u['reason'] == 'unclosed_fence' for u in result['unresolved'])


def test_frontmatter_unclosed_is_coverage_failure_and_never_instruction():
    result = graph({'SKILL.md': '---\nRead /sandbox/a\n'})
    assert actions(result) == []
    assert any(u['reason'] == 'unclosed_frontmatter' for u in result['unresolved'])


def test_stable_file_order_ids_and_distinct_duplicate_effects():
    files = {'a.py': 'open("/sandbox/a"); open("/sandbox/a")\n',
             'b.py': 'open("/sandbox/b")\n'}
    first, second = graph(files), graph(dict(reversed(list(files.items()))))
    assert first == second
    assert len({n['id'] for n in first['nodes']}) == len(first['nodes'])
    assert len(actions(first, 'file.read')) == 3
    alone = graph({'b.py': files['b.py']})
    assert {n['id'] for n in alone['nodes']} == {n['id'] for n in first['nodes']
                                                if n['provenance']['file'] == 'b.py'}
    assert first['source_sha256']['a.py'] == hashlib.sha256(files['a.py'].encode()).hexdigest()


def test_order_edges_do_not_claim_control_and_all_nested_ids_are_remapped():
    result = graph({'main.py': 'p = "/sandbox/a"\nif flag:\n    open(p)\n'
                    'else:\n    open("/sandbox/b")\n'})
    ids = {n['id'] for n in result['nodes']}
    assert all(e['source'] in ids and e['target'] in ids for e in result['edges'])
    assert not any(e['type'] in {'CONTROL', 'RETURN'} for e in result['edges'])
    assert any(e['type'] == 'ORDER' for e in result['edges'])
    assert any(e['type'] == 'DATA' for e in result['edges'])
    assert all(c['predicate_id'] in ids for n in result['nodes'] for c in n.get('control_context', []))
    reads = actions(result, 'file.read')
    assert not any(e['source'] == reads[0]['id'] and e['target'] == reads[1]['id']
                   for e in result['edges'])


def test_crossfile_calls_are_exact_references_without_return_or_proven_invocation():
    result = graph({'SKILL.md': 'Run python scripts/main.py\nRead /sandbox/out\n',
                    'scripts/main.py': 'open("/sandbox/a")\n'})
    by_id = {n['id']: n for n in result['nodes']}
    call = [e for e in result['edges'] if e['type'] == 'CALL']
    assert len(call) == 1 and call[0]['semantics'] == 'explicit_script_reference'
    assert by_id[call[0]['target']]['operation'] == 'module_entry'
    assert not any(n['invocation_proven'] for n in result['nodes'])
    assert not any(e['type'] == 'RETURN' for e in result['edges'])
    fake = graph({'SKILL.md': 'Run python scripts/main.py.evil\n',
                  'scripts/main.py': 'open("/sandbox/a")\n'})
    assert not any(e['type'] == 'CALL' for e in fake['edges'])


def test_uncalled_functions_shadowed_tools_dynamic_paths_and_comments_remain_conservative():
    result = graph({'main.py': 'p = "/sandbox/global"\ndef f():\n    open(p)\n'
                    'open = custom\nopen("/sandbox/not-a-tool")\n'
                    '# open("/sandbox/comment")\n'})
    assert actions(result, 'file.read') == []
    assert any(u['reason'] == 'function_invocation_and_global_state_not_proven'
               for u in result['unresolved'])
    function = graph({'main.py': 'def f():\n    open("/sandbox/a")\n'})
    assert actions(function, 'file.read')[0]['invocation_proven'] is False
    assert not any(e['type'] == 'CALL' for e in function['edges'])


def test_python_parse_failure_and_unsupported_standalone_language_are_retained():
    result = graph({'broken.py': 'if invalid syntax\n', 'run.ps1': 'Remove-Item /sandbox/a'})
    assert actions(result) == []
    assert {u['reason'] for u in result['unresolved']} >= {'python_parse_error', 'unsupported_file_language'}
    assert result['source_sha256'].keys() == {'broken.py', 'run.ps1'}


def test_visible_truncation_marker_is_unknown_coverage_not_prose_action():
    result = graph({'SKILL.md': 'Read /sandbox/a\n[TRUNCATED]\n'})
    assert any(u['reason'] == 'source_truncated' for u in result['unresolved'])
    assert len(actions(result)) == 1


def test_setext_heading_html_comments_and_markdown_tables_are_structural_nonactions():
    result = graph({'SKILL.md': 'Read /sandbox/title\n===\n<!--\n'
                    'Read /sandbox/comment\n-->\nRead | /sandbox/table\n--- | ---\n'})
    assert actions(result) == []
    assert {r['region_kind'] for r in result['regions']} >= {'heading', 'html_comment', 'table'}


def test_rejected_legacy_matches_include_unclosed_unsupported_and_python_comments():
    result = graph({'SKILL.md': '```python\n# open("/sandbox/comment")\n```\n'
                    '```ruby\nFile.read("/sandbox/unsupported")\n```\n'
                    '```python\nopen("/sandbox/unclosed")\n'})
    rejected = {r['line_start']: r for r in result['rejected']}
    assert {2, 5, 8} <= rejected.keys()
    assert rejected[5]['reason'] == 'unsupported_fence_language'
    assert rejected[8]['reason'] == 'unclosed_fence'


def test_indented_fence_content_uses_markdown_indent_with_original_line_numbers():
    result = graph({'SKILL.md': '  ```python\n  open("/sandbox/a")\n  ```\n'})
    read = actions(result, 'file.read')[0]
    assert read['resource'] == '/sandbox/a' and read['provenance']['line_start'] == 2


def test_empty_fences_and_fenced_parse_failures_keep_real_coverage_spans():
    result = graph({'SKILL.md': '# Tests\n```ruby\n```\n```python\n```\n'
                    '```python\nif invalid syntax\n```\n'})
    assert actions(result) == []
    unsupported = [u for u in result['unresolved'] if u['reason'] == 'unsupported_fence_language']
    assert len(unsupported) == 1 and unsupported[0]['line_start'] == 2
    assert any(u['reason'] == 'empty_fenced_code' and u['line_start'] == 4 for u in result['unresolved'])
    assert any(u['reason'] == 'python_parse_error' and u['line_start'] == 7
               and u['line_end'] == 7 for u in result['unresolved'])


def test_multiline_python_effects_and_branch_merge_evidence_are_within_original_file():
    source = ('Text.\n```python\nif flag:\n    p = "/sandbox/a"\n'
              'else:\n    p = "/sandbox/b"\nopen(\n    p\n)\n```\n')
    result = graph({'SKILL.md': source})
    read = actions(result, 'file.read')[0]
    assert read['provenance'] == {'file': 'SKILL.md', 'line_start': 7, 'line_end': 9}
    merge = [u for u in result['unresolved'] if u['reason'] == 'branch_merged_constant_unknown']
    assert merge and merge[0]['line_start'] == 3
    assert all(3 <= p['line_start'] <= p['line_end'] <= 9 for n in result['nodes']
               for p in [n['provenance'], *n['resource_evidence']])
