"""Posthoc exploratory separation of physical goal and acknowledged completion.

No acquisition or execution. Original frozen endpoints and analysis bytes remain
unchanged. Physical goal is independently checked from recorded final state.
"""
from collections import Counter
import json
from pathlib import Path
import statistics

from analyze_phase11 import (ROOT, aggregate, contrast, csv_bytes, groups, metadata,
                             ordered, strata, unique, DRAWS, SEED)
from phase11_common import immutable, jb, rb, sha, read_rows

PRIMARY_FAULTS = ('ambiguous_after', 'terminal_noncommit')
METRICS = ('physical_goal', 'authorized_goal', 'physical_minus_authorized', 'execution_present',
           'null_execution', 'fault_triggered', 'saved_goal_disagreement')
LIMITATIONS = [
    'Posthoc exploratory measurement clarification, introduced after outcome review; not a prespecified endpoint or confirmatory analysis.',
    'physical_goal is the exact goal predicate evaluated independently on saved final files/emits; authorized_goal is the separately recorded error-free acknowledged completion endpoint.',
    'A strict-stop ambiguous execution can already satisfy the physical goal while lacking trusted acknowledgment. Its authorized_goal failure must not be described as physical task failure.',
    'Final state may meet the goal despite an error or uncertain commit. Physical state success alone never licenses controller continuation or proves safe acknowledgment.',
    'All missing-certificate/null executions remain zero in unconditional physical/authorized outcome denominators; no later selections or state are invented.',
    'Worlds, variants and fault conditions are dependent. Means first average within structural family, then weight families equally; combined contains main/challenge only.',
    'Triggered-only contrasts condition on recorded fault activation and omit untriggered/missing execution rows; all-row contrasts are also reported.',
    'Ten thousand paired-family resamples with seed11101 give descriptive intervals only; no significance, population generalization or universal operational benefit claim.',
    'Physical state checks assume recorded files/emits are complete and truthful; they do not authenticate logs or establish backend atomicity, durability, fencing or real-world safety.'
]


def physical_goal(case, result):
    """Check the exact saved-state contract without using either outcome flag."""
    if result is None:
        return False
    files, emits = result.get('files'), result.get('emits')
    if not isinstance(files, dict) or not isinstance(emits, list):
        raise ValueError('RECORDED_FINAL_STATE_REQUIRED')
    counts = Counter((e['resource'], e['value']) for e in emits)
    goal = case['goal']
    return (all(p in files and files[p] == v for p, v in goal.get('files', {}).items())
            and all(p not in files for p in goal.get('absent', []))
            and all(counts[e['resource'], e['value']] == e['count'] for e in goal.get('emits', [])))


def score_rows(cases, rows):
    cases = {c['case_id']: c for c in cases}
    output = []
    for row in rows:
        result = row.get('result')
        physical = int(physical_goal(cases[row['case_id']], result))
        authorized = int((result or {}).get('authorized_goal') is True)
        output.append({**metadata(cases[row['case_id']]),
                       **{k: row[k] for k in ('world_index', 'fault', 'policy', 'status_budget')},
                       'physical_goal': physical, 'authorized_goal': authorized,
                       'physical_minus_authorized': physical-authorized,
                       'execution_present': int(result is not None), 'null_execution': int(result is None),
                       'fault_triggered': int((result or {}).get('fault_diagnostics', {}).get('fault_triggered') is True),
                       'saved_goal_disagreement': int(result is not None and result.get('goal') != bool(physical))})
    return output


def summarize(cases, rows):
    """Pure tables with raw counts and per-family values/denominators embedded."""
    unique(rows, ('case_id', 'world_index', 'fault', 'policy', 'status_budget'), 'PHYSICAL_GOAL_RECOVERY')
    detail = score_rows(cases, rows)
    fields = ('fault', 'policy', 'status_budget')
    conditions = aggregate(detail, fields, METRICS)
    condition_groups = {tuple(key[k] for k in ('cohort', *fields)): rs
                        for key, rs in groups(strata(detail), ('cohort', *fields))}
    for row in conditions:
        rs = condition_groups[tuple(row[k] for k in ('cohort', *fields))]
        row['family_values'] = [
            {'family': key['family'], 'value': statistics.fmean(r[row['metric']] for r in fr),
             'rows': len(fr), 'non_null_executions': sum(r['execution_present'] for r in fr),
             'physical_goal_positive_rows': sum(r['physical_goal'] for r in fr),
             'authorized_goal_positive_rows': sum(r['authorized_goal'] for r in fr)}
            for key, fr in groups(rs, ('family',))]
    primary = [r for r in detail if r['fault'] in PRIMARY_FAULTS and r['status_budget'] == 1]
    contrasts = []
    for denominator in ('all_rows', 'triggered'):
        selected = primary if denominator == 'all_rows' else [r for r in primary if r['fault_triggered']]
        effects, estimates = contrast(selected, 'terminal_status_minus_strict_stop',
                                      lambda r: r['policy'] == 'terminal_status',
                                      lambda r: r['policy'] == 'strict_stop',
                                      ('fault', 'status_budget'), ('physical_goal', 'authorized_goal'),
                                      denominator=denominator)
        paired_groups = {tuple(key[k] for k in ('cohort', 'fault', 'status_budget')): rs
                         for key, rs in groups(strata(selected), ('cohort', 'fault', 'status_budget'))}
        for row in estimates:
            rs = paired_groups[tuple(row[k] for k in ('cohort', 'fault', 'status_budget'))]
            left = [r for r in rs if r['policy'] == 'terminal_status']
            right = [r for r in rs if r['policy'] == 'strict_stop']
            row.update(raw_left_rows=len(left), raw_right_rows=len(right),
                       raw_left_positive_rows=sum(r[row['metric']] for r in left),
                       raw_right_positive_rows=sum(r[row['metric']] for r in right),
                       raw_left_null_rows=sum(r['null_execution'] for r in left),
                       raw_right_null_rows=sum(r['null_execution'] for r in right))
            family_values = []
            for effect in effects:
                if all(effect[k] == row[k] for k in ('cohort', 'fault', 'status_budget', 'metric', 'denominator')):
                    fl = [r for r in left if r['family'] == effect['family']]
                    fr = [r for r in right if r['family'] == effect['family']]
                    family_values.append({'family': effect['family'], 'difference': effect['difference'],
                                          'pairs': effect['pairs'],
                                          'left_mean': statistics.fmean(r[row['metric']] for r in fl),
                                          'right_mean': statistics.fmean(r[row['metric']] for r in fr),
                                          'left_positive_rows': sum(r[row['metric']] for r in fl),
                                          'right_positive_rows': sum(r[row['metric']] for r in fr)})
            row['family_values'] = family_values
            contrasts.append(row)
    summary = {'schema_version': 1, 'classification': 'posthoc exploratory physical-goal clarification',
               'limits': LIMITATIONS, 'bootstrap_draws': DRAWS, 'bootstrap_seed': SEED,
               'rows': len(detail), 'null_execution_rows': sum(r['null_execution'] for r in detail),
               'physical_goal_rows': sum(r['physical_goal'] for r in detail),
               'authorized_goal_rows': sum(r['authorized_goal'] for r in detail),
               'saved_goal_disagreement_rows': sum(r['saved_goal_disagreement'] for r in detail),
               'condition_rows': len(conditions), 'contrast_rows': len(contrasts),
               'detail_sha256': sha(rb(ordered(detail))),
               'primary_combined_all_rows': [r for r in contrasts if r['cohort'] == 'combined' and r['denominator'] == 'all_rows']}
    return {'summary': summary, 'conditions': ordered(conditions), 'contrasts': ordered(contrasts)}


def analyze(root=ROOT, publish=False):
    root = Path(root)
    cases = [r for name in ('heldout', 'challenge') for r in read_rows(root/f'data/phase11/{name}.jsonl')]
    # Local reader supports verifier copies without changing shared ROOT globals.
    directory = root/'results/phase11/recovery'
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    rows = [r for i in range(1, manifest['chunks']+1) for r in read_rows(directory/f'{i:04}.jsonl')]
    if len(rows) != manifest['rows'] or sha(rb(rows)) != manifest['sha256']:
        raise ValueError('RECOVERY_CHUNK_HASH_MISMATCH')
    result = summarize(cases, rows)
    result['summary']['source_sha256'] = sha(Path(__file__).read_bytes())
    result['summary']['inputs'] = {name: sha((root/name).read_bytes()) for name in
                                  ('data/phase11/heldout.jsonl', 'data/phase11/challenge.jsonl',
                                   'results/phase11/recovery/manifest.json')}
    if publish:
        destination = root/'results/phase11/physical_goal'
        outputs = {'summary.json': jb(result['summary'])}
        for name in ('conditions', 'contrasts'):
            outputs[name+'.jsonl'] = rb(result[name]); outputs[name+'.csv'] = csv_bytes(result[name])
        for name, data in outputs.items():
            if (destination/name).exists() and (destination/name).read_bytes() != data:
                raise ValueError('IMMUTABLE_PHYSICAL_GOAL_MISMATCH:'+name)
        for name, data in sorted(outputs.items()):
            immutable(destination/name, data)
    return result


def audit(root=ROOT, publish=False):
    return analyze(root=root, publish=publish)


if __name__ == '__main__':
    result = analyze(publish=True)
    print(json.dumps({k: v for k, v in result['summary'].items()
                      if k not in ('primary_combined_all_rows', 'limits')}, sort_keys=True), flush=True)
