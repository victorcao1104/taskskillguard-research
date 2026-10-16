"""Deterministic scientific PNG/PDF figures from the saved Phase 9 summary."""
import argparse
from io import BytesIO
import json
from pathlib import Path

from phase9_common import ROOT, jb, immutable, sha
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

COLORS = ('#2563a6', '#b45a27', '#24866d', '#9a549f', '#697483', '#b49b32')
AXES = ('authorization', 'current_route_required', 'catalog_required')
AXIS_NAMES = ('Authorization', 'Current route', 'Catalog')
BUDGETS = (2, 4, 8, 'full')
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.spines.top': False,
                     'axes.spines.right': False, 'pdf.fonttype': 42, 'savefig.facecolor': 'white'})


def save_figure(fig, output, name):
    """No time metadata; byte comparison protects already published figures."""
    encoded = {}
    try:
        for extension in ('png', 'pdf'):
            data = BytesIO()
            metadata = {'Software': 'Phase 9 offline analysis'} if extension == 'png' else {
                'CreationDate': None, 'ModDate': None, 'Creator': 'Phase 9 offline analysis'}
            fig.savefig(data, format=extension, dpi=180, metadata=metadata)
            encoded[name+'.'+extension] = data.getvalue()
        for filename, data in encoded.items():
            path = Path(output)/filename
            if path.exists() and path.read_bytes() != data:
                raise ValueError('IMMUTABLE_MISMATCH:' + str(path))
        for filename, data in encoded.items():
            immutable(Path(output)/filename, data)
    finally:
        plt.close(fig)


def factorial_figure(summary):
    rows = [r for r in summary['factorial'] if r['split'] == 'heldout']
    models = sorted({r['model'] for r in rows})
    fig, panels = plt.subplots(1, len(models), figsize=(11, 4.8), squeeze=False, sharey=True)
    names = [v+'/'+str(r) for v in ('A00', 'A01', 'A10', 'A11') for r in (0, 1)]
    for ax, model in zip(panels[0], models):
        matrix = [[100*next(r['family_balanced_accuracy'] for r in rows if r['model'] == model
                          and r['axis'] == axis and r['view'] == label.split('/')[0]
                          and r['reducer'] == int(label[-1])) for label in names] for axis in AXES]
        im = ax.imshow(matrix, vmin=0, vmax=100, cmap='Blues', aspect='auto')
        for y, values in enumerate(matrix):
            for x, value in enumerate(values):
                ax.text(x, y, f'{value:.0f}', ha='center', va='center', color='white' if value > 58 else '#182638')
        ax.set_xticks(range(8), names, rotation=45, ha='right')
        ax.set_yticks(range(3), AXIS_NAMES)
        ax.set_title(model)
    fig.subplots_adjust(bottom=.24, top=.80, right=.89, wspace=.15)
    fig.colorbar(im, cax=fig.add_axes([.91, .29, .015, .43]), label='Family mean typed accuracy (%)')
    fig.suptitle('Factorial typed correctness on 12 new authored families', y=.96)
    fig.text(.5, .055, 'Axy: x = global fact deduplication; y = exact tool facts. /0 = model labels; /1 = same-response reducer.\nInvalid responses remain incorrect. Both variants contribute within each family.', ha='center', fontsize=8)
    return fig


def query_figure(summary):
    rows = [r for r in summary['queries'] if r['split'] == 'heldout']
    pipelines = sorted({r['pipeline'] for r in rows})
    fig, panels = plt.subplots(1, 2, figsize=(11, 4.6))
    for color, pipeline in zip(COLORS, pipelines):
        rs = [next(r for r in rows if r['pipeline'] == pipeline and r['budget'] == budget) for budget in BUDGETS]
        label = pipeline.replace('gpt-', '').replace(':', ' ')
        panels[0].plot(range(4), [100*r['family_balanced_proven_fraction'] for r in rs], marker='o', color=color, label=label)
        panels[1].plot([r['interpreter_steps']/r['cases'] for r in rs],
                       [100*r['family_balanced_proven_fraction'] for r in rs], marker='o', color=color, label=label)
    panels[0].set_xticks(range(4), ['2', '4', '8', 'Full'])
    panels[0].set_xlabel('Interpreter invocation budget')
    panels[1].set_xlabel('Mean entered interpreter steps per case')
    for ax in panels:
        ax.set_ylim(-2, 104)
        ax.set_ylabel('Family mean proven typed decisions (%)')
        ax.grid(alpha=.2)
    panels[1].legend(frameon=False, fontsize=8)
    fig.suptitle('Query allocation: budget and interpreter work are separate costs')
    fig.text(.5, .015, 'Primary rankings only. Proven intrinsic unknown counts as resolved; budget abstention does not. Full consumes the complete catalog.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .05, 1, .94])
    return fig


def interface_figure(summary):
    wanted = ('conditional-aggregate', 'preflight_on-off:aggregate', 'preflight_on-off:conditional', 'observations2-0', 'observations2-1')
    rows = [next(r for r in summary['runtime_contrasts'] if r['track'] == 'interface' and r['split'] == 'heldout'
                 and r['fault'] == 'pooled' and r['contrast'] == c and r['metric'] == 'completion' and r['population'] == 'all') for c in wanted]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for i, row in enumerate(rows):
        estimate = 100*row['estimate']
        lo, hi = [100*v for v in row['interval95']]
        ax.errorbar(estimate, i, xerr=[[estimate-lo], [hi-estimate]], fmt='o', color=COLORS[i], capsize=4)
    ax.set_yticks(range(len(rows)), ['Conditional − aggregate gate', 'Preflight on − off (aggregate)',
                                    'Preflight on − off (conditional)', '2 − 0 observations', '2 − 1 observations'])
    ax.invert_yaxis()
    ax.axvline(0, color='#555555', linestyle='--', linewidth=1)
    ax.set_xlabel('Paired macro-family completion difference (percentage points)')
    ax.grid(axis='x', alpha=.2)
    ax.set_title('Gate, preflight and observation contrasts on new families')
    fig.text(.5, .025, 'Four fault strata pooled as dependent conditions. 10,000 family bootstrap resamples; seed 9009. Exploratory, unadjusted 95% intervals.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .08, 1, 1])
    return fig


def recovery_figure(summary):
    rows = [r for r in summary['recovery'] if r['split'] == 'heldout' and r['planning_budget'] == 512 and r['cache'] is True]
    faults = ('none', 'transient_before', 'known_after', 'ambiguous_after', 'double_transient_before', 'mixed_known_then_ambiguous', 'late_ambiguous')
    names = ('None', 'Before', 'Known\nafter', 'Ambiguous\nafter', 'Double\nbefore', 'Mixed', 'Late\nambiguous')
    fig, panels = plt.subplots(2, 2, figsize=(12, 7))
    for pi, policy in enumerate(('priority', 'calls', 'risk')):
        selected = [next(r for r in rows if r['policy'] == policy and r['fault'] == f) for f in faults]
        for ax, metric in zip(panels.flat, ('completion', 'charged_calls', 'planning_units', 'mutation_risk_score')):
            values = [100*r['success_rate'] if metric == 'completion' else r[metric]['mean'] for r in selected]
            ax.bar(np.arange(len(faults))+(pi-1)*.25, values, width=.23, color=COLORS[pi], label=policy)
            ax.set_xticks(range(len(faults)), names, fontsize=8)
            ax.grid(axis='y', alpha=.2)
            ax.set_axisbelow(True)
    for ax, title in zip(panels.flat, ('Completed worlds (%)', 'Mean charged calls', 'Mean planning units', 'Mean mutation risk surrogate')):
        ax.set_title(title)
    panels[0, 0].set_ylim(0, 105)
    panels[0, 1].legend(frameon=False)
    fig.suptitle('Recovery tradeoffs under equal planning budget 512, cache enabled')
    fig.text(.5, .015, 'All 46 new worlds per fault, including failures. Risk weights and planning units are synthetic; call costs alone do not measure total work.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .045, 1, .95])
    return fig


def integration_figure(summary):
    rows = [r for r in summary['integrated'] if r['split'] == 'heldout']
    pipelines = sorted({r['pipeline'] for r in rows})
    fig, panels = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, budget in zip(panels, (8, 'full')):
        vals = []
        for pipeline in pipelines:
            rs = [r for r in rows if r['pipeline'] == pipeline and r['query_budget'] == budget]
            vals.append(100*sum(r['successes'] for r in rs)/sum(r['conditions'] for r in rs))
        ax.bar(range(len(vals)), vals, color=COLORS[:len(vals)])
        ax.set_xticks(range(len(vals)), [p.replace('gpt-', '').replace(':', '\n') for p in pipelines], rotation=25, ha='right', fontsize=8)
        ax.set_title('Query budget '+str(budget))
        ax.set_ylim(0, 105)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    panels[0].set_ylabel('Completed world/fault conditions (%)')
    fig.suptitle('Paid query evidence passed to the same runtime controller')
    fig.text(.5, .015, 'Four faults, 46 new worlds per pipeline/budget. Missing original-query evidence stays missing; audit simulations are checked to be zero.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .08, 1, .94])
    return fig


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, default=ROOT/'results/phase9/analysis/summary.json')
    parser.add_argument('--output', type=Path, default=ROOT/'results/phase9/figures')
    args = parser.parse_args(argv)
    raw = args.summary.read_bytes()
    summary = json.loads(raw)
    figures = (('factorial_accuracy', factorial_figure), ('query_efficiency', query_figure),
               ('interface_contrasts', interface_figure), ('recovery_tradeoffs', recovery_figure),
               ('query_to_execution', integration_figure))
    for name, render in figures:
        save_figure(render(summary), args.output, name)
    immutable(args.output/'source_values.json', jb({'source': 'results/phase9/analysis/summary.json',
              'source_sha256': sha(raw), 'figures': [name for name, _ in figures],
              'tables': {k: summary[k] for k in ('factorial', 'queries', 'recovery', 'integrated')},
              'interface_completion_contrasts': [r for r in summary['runtime_contrasts'] if r['track'] == 'interface'
                  and r['split'] == 'heldout' and r['metric'] == 'completion' and r['fault'] == 'pooled']}))
    print(json.dumps({'figures': len(figures), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
