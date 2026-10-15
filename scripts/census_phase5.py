"""Offline approved180 coverage census. This script never executes corpus code."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tsg.extraction_v4 import extract_graph_v4, segment_markdown
from tsg.extraction_v5 import extract_graph_v5
from tsg.shell_v4 import _lex, _Unsupported


def _raw_heads(files):
    """Count syntax heads in closed supported regions, including unsupported commands.

    A lexical head is not proof of a command/callee identity or valid grammar.
    Python parse failures and shell lexical failures are explicit denominators.
    """
    python, shell, gaps = Counter(), Counter(), Counter()
    for file, text in sorted(files.items()):
        suffix = Path(file).suffix.lower()
        regions = (segment_markdown(text, file) if suffix == '.md' else
                   [{'region_kind': 'source_code', 'language': suffix[1:], 'line_start': 1,
                     'line_end': len(text.splitlines()), 'closed': True}])
        for region in regions:
            if region['region_kind'] not in {'source_code', 'code_body'} or not region.get('closed', True):
                continue
            indent = region.get('fence_indent', 0)
            code = '\n'.join(line[min(indent, len(line) - len(line.lstrip(' '))):]
                             for line in text.splitlines()[region['line_start'] - 1:region['line_end']])
            language = region['language']
            if language in {'py', 'python', 'python3'}:
                try:
                    tree = ast.parse(code)
                except (SyntaxError, ValueError, RecursionError):
                    gaps['python_parse_failure'] += 1
                    continue
                python.update(ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call))
            elif language in {'sh', 'bash', 'shell'}:
                try:
                    words = _lex(code)
                except _Unsupported:
                    gaps['shell_lex_failure'] += 1
                    continue
                first = True
                for word in words:
                    if word.operator and word.text in {'\n', ';', '|', '&&', '||', '&'}:
                        first = True
                    elif first:
                        shell[word.text] += 1
                        first = False
    return python, shell, gaps


def _effect_key(node):
    return json.dumps({k: node[k] for k in ('operation', 'resource', 'provenance', 'execution_role')}, sort_keys=True)


def census_rows(rows, baseline_directory=None):
    """Return observations and descriptive coverage, with no accuracy denominator."""
    observations = []
    unsupported_python, unsupported_shell = Counter(), Counter()
    python_heads, shell_heads, syntax_gaps = Counter(), Counter(), Counter()
    before_total = after_total = 0
    for row in rows:
        if baseline_directory is None:
            before = extract_graph_v4(row['skill_id'], row['files'])
        else:
            before = json.loads((baseline_directory / (row['skill_id'] + '.json')).read_text(encoding='utf-8'))
        after = extract_graph_v5(row['skill_id'], row['files'])
        if before['source_sha256'] != after['source_sha256']:
            raise ValueError('BASELINE_SOURCE_MISMATCH: ' + row['skill_id'])
        for unknown in before['unresolved']:
            if unknown['reason'] == 'unmodeled_call':
                unsupported_python[unknown.get('callee', '<missing>')] += 1
            if unknown['reason'] == 'unsupported_command':
                detail = unknown.get('detail', '')
                head = detail.removeprefix('No command signature for ') if detail.startswith('No command signature for ') else '<dynamic_or_other>'
                unsupported_shell[head] += 1
        py, sh, gaps = _raw_heads(row['files'])
        python_heads.update(py)
        shell_heads.update(sh)
        syntax_gaps.update(gaps)
        old = [n for n in before['nodes'] if n['privilege_relevant']]
        new = [n for n in after['nodes'] if n['privilege_relevant']]
        old_keys, new_keys = Counter(map(_effect_key, old)), Counter(map(_effect_key, new))
        before_total += len(old)
        after_total += len(new)
        observations.append({'skill_id': row['skill_id'], 'family_id': row.get('family_id'),
                             'source_sha256': after['source_sha256'],
                             'source_coverage': row.get('coverage'),
                             'v4_candidates': len(old), 'v5_candidates': len(new),
                             'candidate_delta': len(new) - len(old),
                             'added_candidates': [json.loads(key) for key, count in (new_keys - old_keys).items() for _ in range(count)],
                             'removed_candidates': [json.loads(key) for key, count in (old_keys - new_keys).items() for _ in range(count)],
                             'v5_extension_actions': after['coverage']['extension_actions'],
                             'v5_unknown_reasons': after['coverage']['unknown_reasons']})
    summary = {'bundles': len(observations), 'v4_candidates': before_total, 'v5_candidates': after_total,
               'candidate_delta': after_total - before_total,
               'bundles_with_added_candidates': sum(bool(row['added_candidates']) for row in observations),
               'bundles_with_removed_candidates': sum(bool(row['removed_candidates']) for row in observations),
               'added_candidate_total': sum(len(row['added_candidates']) for row in observations),
               'removed_candidate_total': sum(len(row['removed_candidates']) for row in observations),
               'v4_unsupported_python_heads': dict(unsupported_python.most_common()),
               'v4_unsupported_shell_heads': dict(unsupported_shell.most_common()),
               'segmented_python_call_heads': dict(python_heads.most_common()),
               'segmented_shell_command_heads': dict(shell_heads.most_common()),
               'syntax_count_gaps': dict(syntax_gaps),
               'real_human_accuracy': None, 'corpus_code_executed': False,
               'claim': 'Candidate growth is a coverage proxy, not precision, recall, accuracy, execution or authorization.'}
    return observations, summary


def _immutable(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError('Immutable result exists: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'results/phase5/extraction_development/census')
    args = parser.parse_args()
    source = ROOT / 'data/phase3/real_prepared.jsonl'
    data = source.read_bytes()
    rows = [json.loads(line) for line in data.decode('utf-8').splitlines()]
    if len(rows) != 180 or len({row['skill_id'] for row in rows}) != 180:
        raise ValueError('APPROVED180_DENOMINATOR_MISMATCH')
    observations, summary = census_rows(rows, ROOT / 'results/phase4/real/graphs')
    summary['input_sha256'] = hashlib.sha256(data).hexdigest()
    summary['source_sha256'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                               ('src/tsg/extraction_v5.py', 'src/tsg/shell_v5.py', 'scripts/census_phase5.py',
                                'src/tsg/extraction_v4.py', 'src/tsg/shell_v4.py', 'src/tsg/graph_v2.py', 'src/tsg/evidence_v4.py')}
    _immutable(args.out / 'observations.jsonl', ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in observations).encode())
    _immutable(args.out / 'summary.json', (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())
    print(json.dumps({k: summary[k] for k in ('bundles', 'v4_candidates', 'v5_candidates', 'candidate_delta',
                                             'added_candidate_total', 'removed_candidate_total', 'real_human_accuracy')}))


if __name__ == '__main__':
    main()
