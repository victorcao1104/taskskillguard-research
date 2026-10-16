"""Static publication figures from immutable Phase 10 analysis source values."""
import argparse
from io import BytesIO
import json
from pathlib import Path

from phase10_common import ROOT, jb, immutable, sha
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

COLORS = ('#2768a6', '#d17732', '#2a9076', '#9953a0', '#66758d', '#a8912c', '#b9555b', '#429ab2')
CELLS = ('full_diag', 'batch_diag', 'next_diag', 'next_exec', 'next_graph', 'next_padding')
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.spines.top': False,
    'axes.spines.right': False, 'pdf.fonttype': 42, 'savefig.facecolor': 'white'})


def save_figure(fig, output, name):
    try:
        for extension in ('png', 'pdf'):
            handle = BytesIO()
            metadata = {'Software': 'Phase10 offline analysis'} if extension == 'png' else {
                'CreationDate': None, 'ModDate': None, 'Creator': 'Phase10 offline analysis'}
            fig.savefig(handle, format=extension, dpi=180, metadata=metadata)
            immutable(Path(output)/(name+'.'+extension), handle.getvalue())
    finally:
        plt.close(fig)


def validity_figure(summary):
    rows = summary['streams']
    models = sorted({r['model'] for r in rows})
    fig, panels = plt.subplots(1, len(models), figsize=(12, 4.7), squeeze=False, sharey=True)
    for ax, model in zip(panels[0], models):
        rs = [next(r for r in rows if r['model'] == model and r['cell'] == cell) for cell in CELLS]
        for j, (field, name) in enumerate((('first_decision_validity', 'First decision'),
                                          ('stream_validity', 'Whole stream'), ('decision_validity', 'Attempted decisions'))):
            ax.bar(np.arange(6)+(j-1)*.25, [100*(r[field] or 0) for r in rs], width=.23, label=name, color=COLORS[j])
        ax.set_xticks(range(6), [c.replace('_', '\n') for c in CELLS])
        ax.set_ylim(0, 105)
        ax.set_title(model)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    panels[0, 0].set_ylabel('Protocol validity (%)')
    panels[0, -1].legend(frameon=False, fontsize=8, loc='lower right')
    fig.suptitle('Protocol validity has three different denominators')
    fig.text(.5, .025, 'First/whole: 24 streams per cell. Attempted decisions: adaptive count; feedback frequency and output burden differ.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .075, 1, .94])
    return fig


def query_figure(summary):
    rows = [r for r in summary['queries'] if r['split'] == 'heldout' and r['stop_mode'] == 'fixed']
    models = sorted({r['pipeline'].split(':')[0] for r in rows if ':' in r['pipeline']})
    fig, panels = plt.subplots(2, len(models), figsize=(12, 7.5), squeeze=False, sharey=True)
    for col, model in enumerate(models):
        pipes = [model+':'+c for c in CELLS]+['heuristic', 'random']
        for color, pipe in zip(COLORS, pipes):
            rs = sorted([r for r in rows if r['pipeline'] == pipe], key=lambda r: r['budget'])
            panels[0, col].plot([r['budget'] for r in rs], [100*r['family_proven_fraction'] for r in rs],
                                marker='o', color=color, label=pipe.split(':')[-1])
            panels[1, col].plot([r['budget'] for r in rs], [100*r['authorization_complete']/r['cases'] for r in rs],
                                marker='o', color=color)
        panels[0, col].set_title(model)
        for ax in panels[:, col]:
            ax.set_xticks((1, 2, 4, 8))
            ax.set_ylim(-2, 104)
            ax.grid(alpha=.2)
        panels[1, col].set_xlabel('Paid atomic query budget')
    panels[0, 0].set_ylabel('Family mean diagnostic proof (%)')
    panels[1, 0].set_ylabel('Complete original authorization evidence (%)')
    panels[0, -1].legend(frameon=False, fontsize=8, ncol=2, loc='lower right')
    fig.suptitle('Diagnostic proofs and execution authorization require different evidence')
    fig.text(.5, .018, 'Fixed prefixes; all invalid/exhausted streams retained. Proven intrinsic unknown is resolved; budget unknown stays unresolved.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .05, 1, .95])
    return fig


def interface_figure(summary):
    wanted = ('v10_goal-v10_authorization', 'v10_goal-v9', 'v10_authorization-v9',
              'goal_obs2-0', 'goal_obs2-1', 'goal_obs1-0', 'v10_goal-v10_no_preflight',
              'v10_authorization-v10_no_preflight')
    labels = ('Goal − authorization (obs2)', 'Goal − v9 (obs2)', 'Authorization − v9 (obs2)',
              'Goal obs2 − obs0', 'Goal obs2 − obs1', 'Goal obs1 − obs0',
              'Goal − preflight off', 'Authorization − preflight off')
    fig, panels = plt.subplots(1, 2, figsize=(12, 5.5), sharey=True)
    for ax, split in zip(panels, ('heldout', 'regression')):
        for i, name in enumerate(wanted):
            rows = [r for r in summary['runtime_contrasts'] if r['track'] == 'interface' and r['split'] == split
                    and r['fault'] == 'pooled' and r['contrast'] == name and r['metric'] == 'completion' and r['population'] == 'all']
            if not rows:
                continue
            r = rows[0]
            estimate = 100*r['estimate']
            lo, hi = [100*x for x in r['interval95']]
            ax.errorbar(estimate, i, xerr=[[max(0, estimate-lo)], [max(0, hi-estimate)]], fmt='o', color=COLORS[i], capsize=4)
        ax.set_yticks(range(len(labels)), labels)
        ax.axvline(0, color='#555555', linestyle='--', linewidth=1)
        ax.grid(axis='x', alpha=.2)
        ax.set_xlabel('Family mean completion difference (percentage points)')
        ax.set_title('New 12 families' if split == 'heldout' else 'Prior-case regression')
    panels[0].invert_yaxis()
    fig.suptitle('Goal observations, observation budget, and diagnostic preflight control')
    fig.text(.5, .018, 'Matched worlds/faults; family bootstrap 10,000 resamples, seed10101; exploratory unadjusted intervals. Quota16, planner512.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .065, 1, .94])
    return fig


def stopping_figure(summary):
    rows = [r for r in summary['stopping_checks'] if r['query_budget'] == 8 and r['planning_budget'] == 512]
    pipes = sorted({r['pipeline'] for r in rows})
    fig, panels = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    vals = []
    losses = []
    for p in pipes:
        rs = [r for r in rows if r['pipeline'] == p]
        vals.append(sum(r['saved_queries_at_unchanged_completion'] for r in rs)/sum(r['paired_conditions'] for r in rs))
        losses.append(sum(r['completion_losses'] for r in rs))
    panels[0].bar(range(len(pipes)), vals, color=[COLORS[i%8] for i in range(len(pipes))])
    panels[0].set_ylabel('Saved interpreter calls\nper execution condition')
    panels[0].set_title('Actual saved queries where completion is unchanged')
    panels[1].bar(range(len(pipes)), losses, color='#b9555b')
    panels[1].set_ylabel('Completion losses (conditions)')
    panels[1].set_title('Authorization-stop losses versus fixed query acquisition')
    panels[1].set_xticks(range(len(pipes)), [p.replace('gpt-', '').replace(':', '\n') for p in pipes], rotation=35, ha='right', fontsize=8)
    for ax in panels:
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle('Authorization stopping: realized work and end-to-end completion')
    fig.text(.5, .018, 'Budget8, planner512; matched worlds and two faults. Acquisition evidence repeats across execution scenarios. All campaign API spending remains charged.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .07, 1, .94])
    return fig


def recovery_figure(summary):
    rows = summary['recovery']
    faults = ('none', 'transient_before', 'known_after', 'mixed_known_then_ambiguous',
              'late_ambiguous', 'first_emit_ambiguous', 'second_write_ambiguous')
    names = ('None', 'Before', 'Known\nafter', 'Mixed', 'Late', 'First\nemit', 'Second\nwrite')
    profiles = ('default', 'uniform', 'write_heavy')
    metrics = ('completion', 'charged_calls', 'mutation_risk_score')
    fig, panels = plt.subplots(3, 3, figsize=(13, 10))
    for row, profile in enumerate(profiles):
        for col, metric in enumerate(metrics):
            ax = panels[row, col]
            for pi, policy in enumerate(('priority', 'calls', 'risk')):
                rs = [next(r for r in rows if r['policy'] == policy and r['fault'] == fault and r['risk_profile'] == profile) for fault in faults]
                ys = [100*r['family_completion'] if metric == 'completion' else r[metric]['mean'] for r in rs]
                ax.plot(range(7), ys, marker='o', color=COLORS[pi], label=policy)
            ax.set_xticks(range(7), names, fontsize=8)
            ax.grid(alpha=.2)
            if metric == 'completion':
                ax.set_ylim(-2, 104)
            if row == 0:
                ax.set_title(('Family completion (%)', 'Mean charged calls', 'Mean declared mutation risk')[col])
            if col == 0:
                ax.set_ylabel(profile)
    panels[0, -1].legend(frameon=False)
    fig.suptitle('Recovery policies across seven faults and three declared risk profiles')
    fig.text(.5, .018, 'All 48 new worlds per condition, including failures; planner512, observation2, quota16. Synthetic risk scores differ in meaning across profile rows.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .055, 1, .95])
    return fig


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--summary', type=Path, default=ROOT/'results/phase10/analysis/summary.json')
    p.add_argument('--output', type=Path, default=ROOT/'results/phase10/figures')
    a = p.parse_args(argv)
    raw = a.summary.read_bytes()
    summary = json.loads(raw)
    renders = (('protocol_validity', validity_figure), ('query_evidence', query_figure),
               ('observation_completion', interface_figure), ('actual_stopping', stopping_figure),
               ('recovery_sensitivity', recovery_figure))
    for name, render in renders:
        save_figure(render(summary), a.output, name)
    immutable(a.output/'source_values.json', jb({'source': str(a.summary.relative_to(ROOT)) if a.summary.is_relative_to(ROOT) else str(a.summary),
        'source_sha256': sha(raw), 'figures': [name for name, _ in renders],
        'tables': {k: summary[k] for k in ('streams', 'queries', 'runtime_contrasts', 'stopping_checks', 'recovery')}}))
    print(json.dumps({'figures': len(renders), 'output': str(a.output)}), flush=True)


if __name__ == '__main__':
    main()
