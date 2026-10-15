"""Development tests with hand-specified effects; source strings never execute."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest


def graph(source, file='main.py'):
    try:
        extractor = importlib.import_module('tsg.extraction_v5').extract_graph_v5
    except ModuleNotFoundError:
        pytest.fail('Phase-5 extraction is not implemented')
    return extractor('development', {file: source})


def actions(result):
    return [n for n in result['nodes'] if n['privilege_relevant']]


def effects(result):
    return [(n['operation'], n['resource']) for n in actions(result)]


@pytest.mark.parametrize('call,want', [
    ('shutil.copyfile("/in", "/out")', [('file.read', '/in'), ('file.write', '/out')]),
    ('shutil.copy("/in", "/out")', [('file.read', '/in'), ('file.write', 'unknown')]),
    ('shutil.move("/in", "/out")', [('file.delete', '/in'), ('file.write', 'unknown')]),
    ('os.rename("/in", "/out")', [('file.delete', '/in'), ('file.write', '/out')]),
    ('shutil.rmtree("/tree")', [('file.delete', '/tree')]),
    ('os.remove("/gone")', [('file.delete', '/gone')]),
    ('os.unlink("/gone")', [('file.delete', '/gone')]),
    ('os.mkdir("/new")', [('file.write', '/new')]),
    ('os.makedirs("/new/dir")', [('file.write', '/new/dir')]),
    ('os.makedirs("/new/dir", exist_ok=True)', [('file.write', '/new/dir')]),
])
def test_explicit_python_signatures_and_namespace_effects(call, want):
    result = graph('import os\nimport shutil\n' + call + '\n')
    assert effects(result) == want
    assert all(not n['invocation_proven'] and not n['authorization_source'] for n in result['nodes'])
    assert result['analysis_complete'] is False


def test_copy_dependency_preserves_arguments_but_directory_target_stays_unknown():
    result = graph('import shutil\nsrc="/input"\ndst="/output"\nshutil.copy(src,dst)\n')
    read, write = actions(result)
    assert effects(result) == [('file.read', '/input'), ('file.write', 'unknown')]
    assert write['resource_status'] == 'unknown'
    assert any(u['reason'] == 'destination_may_be_directory' for u in result['unresolved'])
    assert any(e['source'] == read['id'] and e['target'] == write['id'] and e['type'] == 'DATA'
               for e in result['edges'])
    assert any(p['line_start'] == 2 for p in read['resource_evidence'])


@pytest.mark.parametrize('source', [
    'import shutil\nshutil=other\nshutil.copyfile("/in","/out")',
    'import shutil\nshutil.copyfile=other\nshutil.copyfile("/in","/out")',
    'import shutil\na=shutil\na.copyfile=other\nshutil.copyfile("/in","/out")',
    'import shutil\nimport shutil as s\ns.copyfile=other\nshutil.copyfile("/in","/out")',
    'import shutil\nsetattr(shutil,"copyfile",other)\nshutil.copyfile("/in","/out")',
    'import shutil\nfrom somewhere import *\nshutil.copyfile("/in","/out")',
    'import os\nos.unlink(path="/gone", dir_fd=fd)',
    'import os\nos.mkdir("/new", mode=0o700)',
    'import shutil\nshutil.copyfile("/in","/out", follow_symlinks=False)',
    'import shutil\nshutil.copyfile(*paths)',
    'import shutil\nshutil.copyfile("/in","/out", **opts)',
    'import os\nos.makedirs("/new", exist_ok=flag)',
    'import os\nos.makedirs("/new", exist_ok=1)',
    'import os\nos.remove(42)',
    'import os\nos.remove("")',
])
def test_unsupported_identity_or_signature_abstains(source):
    result = graph(source + '\n')
    assert effects(result) == []
    assert result['unresolved']


def test_dynamic_python_resource_remains_unknown_with_operation_evidence():
    result = graph('import os\nos.makedirs(path)\n')
    assert effects(result) == [('file.write', 'unknown')]
    assert any(u['reason'] == 'unresolved_resource_expression' for u in result['unresolved'])


@pytest.mark.parametrize('source,want', [
    ('import shutil as s\ns.copyfile("/in", "/out")', [('file.read', '/in'), ('file.write', '/out')]),
    ('from shutil import copyfile as duplicate\nduplicate(src="/in", dst="/out")', [('file.read', '/in'), ('file.write', '/out')]),
    ('import shutil\nf=shutil.copyfile\nf("/in", "/out")', [('file.read', '/in'), ('file.write', '/out')]),
    ('from shutil import copy as duplicate\nduplicate("/in", dst="/out")', [('file.read', '/in'), ('file.write', 'unknown')]),
    ('import shutil as s\ns.move(dst="/out", src="/in")', [('file.delete', '/in'), ('file.write', 'unknown')]),
    ('import os as system\nsystem.rename(src="/in", dst="/out")', [('file.delete', '/in'), ('file.write', '/out')]),
    ('import shutil\nshutil.rmtree(path="/tree")', [('file.delete', '/tree')]),
    ('from os import remove as delete\ndelete(path="/gone")', [('file.delete', '/gone')]),
    ('import os\nos.unlink(path="/gone")', [('file.delete', '/gone')]),
    ('import os\nos.mkdir(path="/new")', [('file.write', '/new')]),
    ('from os import makedirs\nmakedirs(name="/new", exist_ok=False)', [('file.write', '/new')]),
])
def test_proven_aliases_and_exact_keyword_roles_preserve_resource_binding(source, want):
    assert effects(graph(source + '\n')) == want


@pytest.mark.parametrize('source', [
    'import shutil as s\ns=custom\ns.copyfile("/in", "/out")',
    'from shutil import copyfile as cp\ncp=custom\ncp("/in", "/out")',
    'from shutil import copyfile as cp\ncp.__code__=custom\ncp("/in", "/out")',
    'import shutil as s\nf=s.copyfile\nf.__code__=custom\ns.copyfile("/in", "/out")',
    'from shutil import copyfile as cp\nsetattr(cp,"__code__",custom)\ncp("/in", "/out")',
    'import shutil as s\ndef f():\n s.copyfile("/in", "/out")\ns=custom',
    'from shutil import copyfile as cp\ndef f(cp):\n cp("/in", "/out")',
    'from shutil import copyfile as cp\nexec(program)\ncp("/in", "/out")',
    'import shutil\nshutil.copyfile("/in", src="/duplicate", dst="/out")',
    'import shutil\nshutil.copyfile(src="/in", dst="/out", surprise=True)',
    'import shutil\nshutil.copyfile(src="/in", src="/duplicate", dst="/out")',
    'import shutil\nshutil.copyfile(dst="/out")',
    'import os\nos.makedirs(path="/new", exist_ok=True)',
    'import os\nos.makedirs(name="/new", exist_ok=True, exist_ok=False)',
])
def test_alias_mutation_rebinding_and_invalid_keyword_mapping_abstain(source):
    result = graph(source + '\n')
    assert not [n for n in actions(result) if n['operation'].startswith('file.')]
    assert result['unresolved']


@pytest.mark.parametrize('argument', ['os', 'os.path', 'os.remove', 'open("/input")'])
def test_symbol_or_handle_identity_is_not_mistaken_for_a_literal_path(argument):
    result = graph('import os\nos.mkdir(' + argument + ')\n')
    assert not [n for n in actions(result) if n['operation'] == 'file.write']
    if argument.startswith('open'):
        assert effects(result) == [('file.read', '/input')]
    assert any(u['reason'] == 'invalid_extension_path_argument' for u in result['unresolved'])


@pytest.mark.parametrize('mutation', [
    'globals()["os"] = custom',
    'locals().update({"os": custom})',
    'exec(program)',
    'eval(program)',
])
def test_dynamic_namespace_mutation_invalidates_new_module_identity(mutation):
    result = graph('import os\n' + mutation + '\nos.mkdir("/unproven")\n')
    assert not [n for n in actions(result) if n['operation'] == 'file.write']
    assert any(u['reason'] == 'extension_symbol_identity_unproven' for u in result['unresolved'])


def test_multiline_fence_maps_effect_and_argument_provenance_without_proving_invocation():
    source = '# Example\n```python\nimport shutil\np="/in"\nshutil.copyfile(\n p,\n "/out"\n)\n```\n'
    result = graph(source, 'SKILL.md')
    assert effects(result) == [('file.read', '/in'), ('file.write', '/out')]
    assert all(n['provenance'] == {'file': 'SKILL.md', 'line_start': 5, 'line_end': 8}
               for n in actions(result))
    assert all(n['execution_role'] == 'example' and not n['invocation_proven'] for n in actions(result))
    assert any(p['line_start'] == 4 for p in actions(result)[0]['resource_evidence'])
    assert result['source_sha256']['SKILL.md'] == hashlib.sha256(source.encode()).hexdigest()


@pytest.mark.parametrize('source,want', [
    ('echo hello > /out', [('file.write', '/out')]),
    ('echo "a > b" >> "/with space"', [('file.write', '/with space')]),
    ("printf '%s\\n' hello > /out", [('file.write', '/out')]),
    ("printf '\\n' > /out", [('file.write', '/out')]),
    ('tee /one /two', [('file.write', '/one'), ('file.write', '/two')]),
    ('tee -a /one', [('file.write', '/one')]),
    ('wget -O /out https://download.invalid/a', [('network.get', 'https://download.invalid/a'), ('file.write', '/out')]),
    ('wget --output-document=/out https://download.invalid/a', [('network.get', 'https://download.invalid/a'), ('file.write', '/out')]),
    ('wget -O - https://download.invalid/a', [('network.get', 'https://download.invalid/a')]),
])
def test_narrow_shell_signatures(source, want):
    result = graph(source + '\n', 'run.sh')
    assert effects(result) == want
    assert all(n['provenance'] == {'file': 'run.sh', 'line_start': 1, 'line_end': 1}
               for n in actions(result))
    assert all(not n['invocation_proven'] for n in result['nodes'])


@pytest.mark.parametrize('source', [
    'echo -e hi > /out',
    'echo hi 2> /err',
    'echo hi > /out > /other',
    'echo hi > "$OUT"',
    'echo "$PAYLOAD" > /out',
    'echo hi > *.txt',
    'echo hi > /out && rm /gone',
    'echo "$(whoami)" > /out',
    "printf '%q' hello > /out",
    "printf '%s' > /out",
    'tee --unknown /out',
    'tee "$OUT"',
    'tee /one "$TWO"',
    'wget --config=settings -O /out https://download.invalid/a',
    'wget -O /out "$URL"',
    'wget -O /out https://one.invalid https://two.invalid',
    'wget -O /out https://host.invalid/{a,b}',
    'alias echo=other\necho hi > /out',
    'function echo() { :; }\necho hi > /out',
])
def test_shell_unsupported_options_expansion_or_structure_abstains(source):
    result = graph(source + '\n', 'run.sh')
    assert effects(result) == []
    assert result['unresolved']


def test_download_without_explicit_output_keeps_unknown_default_filename():
    result = graph('wget https://download.invalid/a\n', 'run.sh')
    assert effects(result) == [('network.get', 'https://download.invalid/a')]
    assert any(u['reason'] == 'implicit_download_destination' for u in result['unresolved'])


def test_tee_stream_data_dependency_and_append_evidence():
    result = graph('cat /in | tee -a /out\n', 'run.sh')
    read, write = actions(result)
    assert effects(result) == [('file.read', '/in'), ('file.write', '/out')]
    assert write['write_mode'] == 'append'
    assert any(e['source'] == read['id'] and e['target'] == write['id'] and e['type'] == 'DATA'
               for e in result['edges'])


def test_unaffected_v4_evidence_and_all_edges_remain_valid():
    from tsg.extraction_v4 import extract_graph_v4
    files = {'SKILL.md': 'Read /input\n```bash\ncurl https://host.invalid/a -o /out\n```\n',
             'main.py': 'from pathlib import Path\np=Path("/in")\nif flag:\n p.read_text()\n'}
    extractor = importlib.import_module('tsg.extraction_v5').extract_graph_v5
    before = extract_graph_v4('development', files)
    result = extractor('development', files)
    assert result['nodes'] == before['nodes']
    assert result['edges'] == before['edges']
    assert result['unresolved'] == before['unresolved']
    assert result['regions'] == before['regions']
    assert result['coverage']['analysis_complete'] is False
    ids = {n['id'] for n in result['nodes']}
    assert all(e['source'] in ids and e['target'] in ids for e in result['edges'])


def test_independent_scopes_duplicate_ids_and_crossfile_reference_are_preserved():
    source = '```python\nimport os\nos.mkdir("/out")\n```\n```python\nos.mkdir("/bad")\n```\n'
    assert effects(graph(source, 'SKILL.md')) == [('file.write', '/out')]
    duplicate = graph('import os\nos.mkdir("/out"); os.mkdir("/out")\n')
    assert len(actions(duplicate)) == 2
    assert len({n['id'] for n in duplicate['nodes']}) == len(duplicate['nodes'])


def test_census_counts_unsupported_heads_and_additions_without_accuracy_claims():
    try:
        from scripts.census_phase5 import census_rows
    except ModuleNotFoundError:
        pytest.fail('Phase-5 census is not implemented')
    rows = [{'skill_id': 'tiny', 'family_id': 'f', 'files': {
        'main.py': 'import os\nos.makedirs("/out", exist_ok=True)\nunknown()\n',
        'run.sh': 'echo hi > /out\nuvx tool\n'}}]
    observations, summary = census_rows(rows)
    assert summary['bundles'] == 1
    assert summary['v4_unsupported_python_heads'] == {'os.makedirs': 1, 'unknown': 1}
    assert summary['v4_unsupported_shell_heads']['uvx'] == 1
    assert summary['candidate_delta'] == 2
    assert summary['real_human_accuracy'] is None
    assert observations[0]['source_sha256']['run.sh'] == hashlib.sha256(rows[0]['files']['run.sh'].encode()).hexdigest()
