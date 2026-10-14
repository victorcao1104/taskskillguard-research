import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


def graph(text, **files):
    try:
        module = importlib.import_module('tsg.graph_v2')
    except ModuleNotFoundError:
        pytest.fail('The phase-2 graph extractor is not implemented yet')
    return module.extract_graph_v2('fixture', {'scripts/main.py': text, **files})


def actions(result, operation):
    return [n for n in result['nodes'] if n['operation'] == operation and n['kind'] == 'CODE_ACTION']


def data_reaches(result, source, target):
    pending, seen = [source], set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(e['target'] for e in result['edges'] if e['source'] == node and e['type'] == 'DATA')
    return False


def test_constant_paths_and_read_derive_write_dependencies():
    g = graph('from pathlib import Path\nbase = Path("/sandbox/input")\nsrc = base / "a.txt"\n'
              'text = src.read_text()\nreport = text.upper()\ndest = Path("/sandbox/output/a.txt")\ndest.write_text(report)\n')
    read, write = actions(g, 'file.read')[0], actions(g, 'file.write')[0]
    assert read['resource'] == '/sandbox/input/a.txt'
    assert write['resource'] == '/sandbox/output/a.txt'
    assert read['resource_status'] == 'resolved_constant'
    assert data_reaches(g, read['id'], write['id'])
    assert any(n['kind'] == 'DATA_OBJECT' and n.get('binding') == 'report' for n in g['nodes'])
    assert {s['line_start'] for s in read['resource_evidence']} >= {2, 3}


def test_overwritten_constant_never_survives_unknown_assignment():
    g = graph('path = "/sandbox/safe"\npath = input()\nopen(path)\n')
    assert actions(g, 'file.read')[0]['resource'] == 'unknown'
    assert any(u['reason'] == 'unresolved_resource_expression' for u in g['unresolved'])


def test_different_branches_merge_to_unknown_and_do_not_sequence_each_other():
    g = graph('if flag:\n    path = "/sandbox/a"\n    open(path)\nelse:\n    path = "/sandbox/b"\n    open(path)\nopen(path)\n')
    reads = actions(g, 'file.read')
    assert [n['resource'] for n in reads] == ['/sandbox/a', '/sandbox/b', 'unknown']
    assert any(n['kind'] == 'PREDICATE' for n in g['nodes'])
    assert not any(e['source'] == reads[0]['id'] and e['target'] == reads[1]['id'] for e in g['edges'])
    assert any(u['reason'] == 'branch_merged_constant_unknown' for u in g['unresolved'])


def test_same_constants_in_all_branches_are_retained_but_one_sided_not():
    same = graph('if flag:\n    p = "/sandbox/a"\nelse:\n    p = "/sandbox/a"\nopen(p)\n')
    missing = graph('if flag:\n    p = "/sandbox/a"\nopen(p)\n')
    assert actions(same, 'file.read')[0]['resource'] == '/sandbox/a'
    assert actions(missing, 'file.read')[0]['resource'] == 'unknown'


def test_function_scopes_do_not_reuse_module_or_other_function_assignments():
    g = graph('p = "/sandbox/global"\ndef first():\n    p = "/sandbox/first"\n    open(p)\n'
              'def second():\n    open(p)\nopen(p)\n')
    reads = actions(g, 'file.read')
    assert [n['resource'] for n in reads] == ['/sandbox/first', 'unknown', '/sandbox/global']
    assert len({n['scope'] for n in reads}) == 3
    assert not any(e['source'] == reads[0]['id'] and e['target'] == reads[1]['id'] and e['type'] == 'CONTROL' for e in g['edges'])


def test_python_comments_and_string_examples_do_not_become_calls():
    g = graph('# requests.post("https://evil.invalid")\n"open(\'/sandbox/fake\')"\n'
              'import requests\nrequests.get("https://mock.invalid/a")\n')
    assert not actions(g, 'network.post')
    assert not actions(g, 'file.read')
    assert len(actions(g, 'network.get')) == 1


def test_import_aliases_and_constant_string_concatenation():
    g = graph('import requests as rq\nbase = "https://mock.invalid"\nurl = base + "/status"\n'
              'rq.post(url, data="DONE")\n')
    assert actions(g, 'network.post')[0]['resource'] == 'https://mock.invalid/status'
    assert actions(g, 'network.post')[0]['provenance']['line_start'] == 4


def test_shadowed_builtin_and_import_alias_are_not_assumed_to_be_real_tools():
    g = graph('import requests as rq\nrq = unknown()\nrq.post("https://mock.invalid")\n'
              'open = custom\nopen("/sandbox/a")\n')
    assert not actions(g, 'network.post')
    assert not actions(g, 'file.read')
    assert any(u['reason'] == 'unmodeled_call' for u in g['unresolved'])


def test_file_handle_read_and_write_dependencies():
    g = graph('with open("/sandbox/input/a") as src:\n    text = src.read()\n'
              'with open("/sandbox/output/a", "w") as dest:\n    dest.write(text)\n')
    reads, writes = actions(g, 'file.read'), actions(g, 'file.write')
    assert len(reads) == 2 and len(writes) == 2
    assert reads[-1]['resource'] == '/sandbox/input/a'
    assert writes[-1]['resource'] == '/sandbox/output/a'
    assert data_reaches(g, reads[-1]['id'], writes[-1]['id'])


def test_dynamic_mode_and_dynamic_execution_are_unresolved_not_safe():
    g = graph('open("/sandbox/a", mode)\nexec(payload)\n')
    unknown = [n for n in g['nodes'] if n.get('possible_operations') == ['file.read', 'file.write']]
    assert len(unknown) == 1 and unknown[0]['candidate_status'] == 'unresolved'
    assert actions(g, 'command.exec')
    assert any(u['reason'] == 'dynamic_execution' for u in g['unresolved'])


def test_loop_mutated_path_is_unknown_outside_loop():
    g = graph('path = "/sandbox/a"\nfor item in things:\n    path = item\nopen(path)\n')
    assert actions(g, 'file.read')[0]['resource'] == 'unknown'
    assert any(u['reason'] == 'loop_fixed_point_not_computed' for u in g['unresolved'])


def test_cross_layer_call_return_use_explicit_references_only():
    g = graph('open("/sandbox/a")\n', **{'SKILL.md': 'Run python scripts/main.py\nWrite the report.\n'})
    assert any(e['type'] == 'CALL' and e['semantics'] == 'explicit_script_reference' for e in g['edges'])
    assert any(e['type'] == 'RETURN' and e['semantics'] == 'syntactic_return_candidate' for e in g['edges'])
    fake = graph('open("/sandbox/a")\n', **{'SKILL.md': 'Run python scripts/main.py.evil\nWrite report.\n'})
    assert not any(e['type'] == 'CALL' for e in fake['edges'])


def test_syntax_errors_are_counted_and_never_imply_safe_code():
    g = graph('if bad syntax\n    open("/sandbox/a")')
    assert any(u['reason'] == 'python_parse_error' for u in g['unresolved'])
    assert g['analysis_complete'] is False


def test_named_expression_invalidates_previous_constant():
    g = graph('p = "/sandbox/a"\n(p := input())\nopen(p)\n')
    assert actions(g, 'file.read')[0]['resource'] == 'unknown'


def test_conditional_expression_does_not_create_cross_branch_control_edge():
    g = graph('text = open("/sandbox/a").read() if flag else open("/sandbox/b").read()\n')
    reads = actions(g, 'file.read')
    assert len(reads) == 4
    assert not any(e['source'] == reads[1]['id'] and e['target'] == reads[2]['id'] and e['type'] == 'CONTROL' for e in g['edges'])
    assert any(n['kind'] == 'PREDICATE' for n in g['nodes'])


def test_functions_do_not_restore_shadowed_builtin_or_rebound_global_import():
    g = graph('open = custom\ndef first():\n    open("/sandbox/a")\n'
              'import requests\ndef second():\n    requests.post("https://mock.invalid")\nrequests = custom\n')
    assert not actions(g, 'file.read')
    assert not actions(g, 'network.post')


def test_empty_python_has_no_fabricated_source_line():
    g = graph('')
    assert not g['nodes']
    assert any(u['reason'] == 'empty_python_source' for u in g['unresolved'])


def test_graph_builder_produces_coverage_and_preserves_read_only_source(tmp_path):
    bundle = tmp_path / 'source'
    bundle.mkdir()
    (bundle / 'SKILL.md').write_text('Run python main.py\nWrite report.\n')
    (bundle / 'main.py').write_text('p = "/sandbox/a"\nx = open(p).read()\nout = open("/sandbox/out", "w")\nout.write(x)\n')
    import hashlib
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.iterdir()}
    row = {'skill_id': 'fixture', 'bundle_path': str(bundle), 'skill_md_path': str(bundle / 'SKILL.md'),
           'file_sha256': hashes, 'family_id': 'family_fixture', 'split': 'development'}
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(json.dumps(row) + '\n')
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / 'out'
    result = subprocess.run([sys.executable, str(root / 'scripts/build_graphs_v2.py'), '--manifest', str(manifest),
                             '--out', str(out)], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.iterdir()}
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['skills'] == 1 and summary['source_changes'] == []
    assert summary['v2']['edge_counts']['DATA'] > 0
    assert summary['v2']['known_resource_actions'] > summary['v1_same_input']['known_resource_actions']
    assert summary['v2']['candidate_source_sink_data_pairs'] > 0
    assert summary['v2']['resource_status_counts']['resolved_constant'] > 0
