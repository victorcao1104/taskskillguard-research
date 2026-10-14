"""Offline scientific figures from completed, saved phase-2 observations only."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ('full', 'no_graph', 'no_replay', 'no_trust', 'no_taint', 'no_guard', 'no_smt', 'no_triangulate', 'no_lease')


def read(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def ready_pipeline_rows(analysis, *, include_unknown=False):
    if analysis.get('track_count_completion', {}).get('pipeline') is not True:
        return []
    return [r for r in analysis.get('runtime', [])
            if r.get('track') == 'P_Q_pipeline_ablation' and r.get('split') == 'held_out_test'
            and (r.get('n_valid_runs', 0) > 0 or include_unknown)]


def os_plot_rows(analysis):
    """The analyzer already pools low/high; never pool the aggregate again."""
    if analysis.get('track_count_completion', {}).get('os_e2e') is not True:
        return []
    return [r for r in analysis.get('os_e2e', {}).get('runtime', []) if r.get('context') == 'all_contexts']


def goal_count(row):
    """Support older analyzer snapshots without silently rounding arbitrary rates."""
    if 'n_goal_success' in row:
        return row['n_goal_success']
    value = row.get('goal_success_rate')
    if value is None:
        return None
    count = value * row['n_valid_runs']
    if abs(count - round(count)) > 1e-7:
        raise ValueError('Goal rate cannot be reconciled with an integer numerator')
    return round(count)


def generate(root=ROOT):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'pdf.fonttype': 42, 'savefig.bbox': 'tight'})
    directory = root / 'results/phase2/figures'
    directory.mkdir(parents=True, exist_ok=True)
    sources = ['results/phase2/graphs_v2/summary.json', 'results/phase2/lifecycle/summary.json',
               'results/phase2/pipeline_analysis/summary.json']
    graph, lifecycle, analysis = [read(root / p, {} if 'lifecycle' not in p else []) for p in sources]
    produced, skipped = [], {}

    def save(fig, name):
        for extension in ('png', 'pdf'):
            path = directory / f'{name}.{extension}'
            fig.savefig(path, dpi=180, metadata={'Creator': 'TaskSkillGuard saved-observation plotting'})
            produced.append({'path': path.relative_to(root).as_posix(),
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        plt.close(fig)

    if graph.get('skills') and graph.get('v2'):
        fig, axes = plt.subplots(1, 3, figsize=(11.6, 4.3), layout='constrained')
        entries = [graph['v1_same_input'], graph['v2']]
        for ax, title, numerator, denominator in [
            (axes[0], 'Known action resources', 'known_resource_actions', 'candidate_actions'),
            (axes[1], 'Known code-action resources', 'code_known_resource_actions', 'code_candidate_actions')]:
            vals = [100 * r[numerator] / r[denominator] for r in entries]
            bars = ax.bar(['v1', 'v2'], vals, color=['#9ea9b5', '#177e89'])
            ax.set_ylim(0, 100); ax.set_ylabel('Candidate coverage (%)'); ax.set_title(title)
            ax.bar_label(bars, [f'{r[numerator]}/{r[denominator]}\n{v:.1f}%' for r, v in zip(entries, vals)], padding=4)
        vals = [r['edge_counts'].get('DATA', 0) for r in entries]
        bars = axes[2].bar(['v1', 'v2'], vals, color=['#9ea9b5', '#177e89'])
        axes[2].bar_label(bars, padding=3); axes[2].set_ylim(0, max(vals) * 1.2 + 1)
        axes[2].set_title('Candidate DATA edges'); axes[2].set_ylabel('Count')
        fig.suptitle(f"Same bounded input: {graph['skills']} skills, {graph['files_analyzed']} files\nCoverage is not semantic or authorization accuracy", fontsize=12)
        save(fig, 'graph_coverage')
    else:
        skipped['graph_coverage'] = 'No saved graph observations'

    if lifecycle and all(r.get('n', 0) > 0 for r in lifecycle):
        configs = ('static_scope', 'monotonic_shrink', 'shrink_and_lease', 'lease_only')
        targets = ('expiry_only', 'quota_only')
        keyed = {(r['target'], r['configuration']): r for r in lifecycle}
        if all((t, c) in keyed for t in targets for c in configs):
            fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.7), layout='constrained')
            for ax, metric, title in zip(axes, ('late_executions', 'task_completions'), ('Late execution (lower is better)', 'Task completion (higher is better)')):
                for i, target in enumerate(targets):
                    rs = [keyed[target, c] for c in configs]
                    bars = ax.bar(np.arange(4) + (i - .5) * .36, [100 * r[metric] / r['n'] for r in rs], .36,
                                  label=target.replace('_', ' '), color=('#177e89', '#e09f3e')[i])
                    ax.bar_label(bars, [f"{r[metric]}/{r['n']}" for r in rs], padding=3, fontsize=8)
                ax.set_xticks(range(4), ['Static', 'Shrink', 'Shrink + lease', 'Lease'], rotation=15)
                ax.set_ylim(0, 118); ax.set_ylabel('Runs (%)'); ax.set_title(title)
            axes[0].legend(loc='upper center', fontsize=8)
            fig.suptitle(f"Independent expiry / quota probes: {sum(r['n'] for r in lifecycle)} saved runs", fontsize=12)
            save(fig, 'lifecycle')
    else:
        skipped['lifecycle'] = 'No complete saved lifecycle observations'

    pipeline = ready_pipeline_rows(analysis, include_unknown=True)
    models = sorted({r['model'] for r in pipeline})
    keyed = {(r['model'], r['variant']): r for r in pipeline}
    if models and all((m, v) in keyed for m in models for v in VARIANTS):
        fig, axes = plt.subplots(len(models), 2, figsize=(12.5, 4.0 * len(models)), squeeze=False, layout='constrained')
        for i, model in enumerate(models):
            rows = [keyed[model, v] for v in VARIANTS]
            for j, metric, numerator, denominator, label in [
                (0, 'unauthorized_execution_rate', 'n_unauthorized_execution', 'n_attack_opportunities', 'Unauthorized execution'),
                (1, 'goal_success_rate', 'n_goal_success', 'n_valid_runs', 'Task completion')]:
                ax = axes[i, j]
                measured = [(k, r) for k, r in enumerate(rows) if r.get(metric) is not None and r[denominator] > 0]
                bars = ax.barh([k for k, _ in measured], [100 * r[metric] for _, r in measured],
                               color=['#177e89' if k == 0 else '#9ea9b5' for k, _ in measured])
                ax.set_yticks(range(9), [v.replace('_', ' ') for v in VARIANTS]); ax.invert_yaxis()
                ax.bar_label(bars, [f"{r[numerator]}/{r[denominator]}" for _, r in measured], padding=3, fontsize=8)
                for k, r in enumerate(rows):
                    if r.get(metric) is None or r[denominator] == 0:
                        ax.text(3, k, f"NA ({r['n_unresolved_runs']} unresolved)", va='center', fontsize=8, color='#8b3a3a')
                ax.set_ylim(8.8, -.8)
                ax.set_xlim(0, 120); ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xlabel('Runs (%)'); ax.set_title(f'{model}: {label}')
        fig.suptitle('Held-out P/Q pipeline ablations in capability VM\nTwo families; decided-run denominators shown; unresolved cells are not zero', fontsize=12)
        save(fig, 'pipeline_ablations')
    else:
        skipped['pipeline_ablations'] = 'Pipeline incomplete or missing measured cells; not zero-filled'

    os_rows = os_plot_rows(analysis)
    if analysis.get('track_count_completion', {}).get('os_e2e') is True and os_rows and all(r['n_valid_runs'] > 0 for r in os_rows):
        groups = defaultdict(lambda: {'n': 0, 'goal': 0, 'attack': 0, 'unauthorized': 0})
        for r in os_rows:
            key = (r['origin'], r.get('model') or 'oracle', r['guard_enabled'])
            v = groups[key]; v['n'] += r['n_valid_runs']; v['goal'] += goal_count(r)
            v['attack'] += r['n_attack_opportunities']; v['unauthorized'] += r['n_unauthorized_execution']
        entries = sorted(groups.items())
        labels = [f"{m}\n{origin.replace('LLM_generated_', '')} / {'guard' if guard else 'unguarded'}" for (origin, m, guard), _ in entries]
        fig, axes = plt.subplots(1, 2, figsize=(12, max(5.8, len(entries) * .62)), layout='constrained')
        for ax, num, den, title in [(axes[0], 'unauthorized', 'attack', 'Unauthorized execution'), (axes[1], 'goal', 'n', 'Task completion')]:
            if any(v[den] == 0 for _, v in entries):
                raise ValueError('Cannot plot OS rate with zero denominator')
            bars = ax.barh(range(len(entries)), [100 * v[num] / v[den] for _, v in entries],
                           color=['#177e89' if key[2] else '#9ea9b5' for key, _ in entries])
            ax.set_yticks(range(len(entries)), labels); ax.invert_yaxis(); ax.set_xlim(0, 120); ax.set_xticks([0, 25, 50, 75, 100])
            ax.bar_label(bars, [f"{v[num]}/{v[den]}" for _, v in entries], padding=3, fontsize=8)
            ax.set_title(title); ax.set_xlabel('Runs (%)')
        fig.suptitle('Actual OS tool-adapter runs; six fixture families\nTask-text oracle v2; both contexts pooled descriptively', fontsize=12)
        save(fig, 'os_security_utility')
    else:
        skipped['os_security_utility'] = 'OS model track incomplete or missing measured cells; not zero-filled'

    manifest = {'source_sha256': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sources if (root / p).exists()},
                'figures': produced, 'skipped': skipped, 'model_calls': 0,
                'interpretation': 'Saved observations only; repeats are not independent skill families.'}
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(generate(args.root), indent=2))
