"""Publication figures from complete immutable Phase 11 analysis, offline only."""
from io import BytesIO
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from phase11_common import ROOT, read_rows, immutable, jb, sha
from analyze_phase11 import csv_bytes

COLORS = ('#286091', '#b76526', '#36866c', '#805b91')
COHORTS = ('main', 'challenge', 'combined')
LABELS = {'main': 'Main: 24 families', 'challenge': 'Challenge: 12 families', 'combined': 'Combined: 36 families'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.titleweight': 'normal',
                     'savefig.facecolor': 'white', 'pdf.fonttype': 42, 'svg.hashsalt': 'phase11-fixed'})


def select(rows, **filters):
    return [r for r in rows if all(r.get(k) == v for k, v in filters.items())]


def decoration(ax, ylabel=None, percent=False):
    ax.set_axisbelow(True); ax.grid(axis='y', alpha=.18)
    if ylabel:
        ax.set_ylabel(ylabel)
    if percent:
        ax.set_ylim(0, 1.04)
        ax.set_yticks([0, .25, .5, .75, 1], ['0', '25', '50', '75', '100'])
    else:
        ax.set_ylim(bottom=0)


def intervals(ax, rows, xs, color, marker='o', label=None, connect=False):
    known = [(x, r) for x, r in zip(xs, rows) if r and r['estimate'] is not None]
    if not known:
        return
    x, rs = zip(*known)
    y = [r['estimate'] for r in rs]
    # Percentile intervals need not enclose a finite-sample mean. Draw the
    # interval directly rather than clipping it into misleading errorbars.
    ax.vlines(x, [r['interval95'][0] for r in rs], [r['interval95'][1] for r in rs], color=color, alpha=.6, linewidth=1)
    ax.plot(x, y, marker=marker, color=color, linestyle='-' if connect else '', linewidth=1.2, markersize=4, label=label)


def deterministic(tables):
    rows = select(tables['policy_conditions'], scaling_shape=None)
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 6.2), squeeze=False)
    used = []
    for col, cohort in enumerate(COHORTS):
        for line, (policy, stop) in enumerate([('original_first', True), ('route_cover', True), ('observe_cover', True), ('random', True), ('observe_cover', False)]):
            color = COLORS[line] if line < 4 else '#555555'
            for ri, metric in enumerate(('completion', 'query_count')):
                rs = [next(iter(select(rows, cohort=cohort, policy=policy, stop=stop, budget=b, metric=metric)), None) for b in (2, 4, 8, 12, 'full')]
                used.extend(r for r in rs if r)
                intervals(axes[ri, col], rs, range(5), color, marker='s' if not stop else 'o',
                          label=policy.replace('_', ' ')+(' fixed' if not stop else ''), connect=True)
        axes[0, col].set_title(LABELS[cohort])
        for ri in (0, 1):
            axes[ri, col].set_xticks(range(5), ['2', '4', '8', '12', 'full'])
            decoration(axes[ri, col], ('Certified completion (%)' if ri == 0 else 'Acquired queries') if col == 0 else None, ri == 0)
        axes[1, col].set_xlabel('Query budget (full = case catalog)')
    axes[0, -1].legend(frameon=False, fontsize=7, loc='lower right')
    fig.suptitle('Deterministic acquisition: family means and descriptive intervals')
    fig.tight_layout(rect=[0, .02, 1, .95])
    return fig, used


def model_comparison(tables):
    rows = select(tables['model_comparator_conditions'], baseline='observe_cover', budget=12)
    models = sorted({r['model'] for r in rows})
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 6), squeeze=False)
    used = []
    for col, cohort in enumerate(COHORTS):
        for i, model in enumerate(models):
            for j, side in enumerate(('model', 'heuristic')):
                x = i*3+j
                for ri, metric in enumerate(('completion', 'query_count')):
                    rs = select(rows, cohort=cohort, model=model, side=side, metric=metric)
                    used.extend(rs)
                    intervals(axes[ri, col], rs, [x], COLORS[j])
        ticks = [i*3+j for i in range(len(models)) for j in (0, 1)]
        names = [model.replace('gpt-', '')+'\n'+('source online' if j == 0 else 'observe cover') for model in models for j in (0, 1)]
        for ri in (0, 1):
            axes[ri, col].set_xticks(ticks, names, fontsize=7)
            decoration(axes[ri, col], ('Certified completion (%)' if ri == 0 else 'Acquired queries') if col == 0 else None, ri == 0)
        axes[0, col].set_title(LABELS[cohort])
    fig.suptitle('Source online versus predeclared heuristic: same case, actual world, budget 12')
    fig.text(.5, .01, 'All invalid and budget-censored streams retained; completion may use a verified paid-prefix certificate despite a later protocol failure.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .05, 1, .94])
    return fig, used


def recovery(tables):
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 6.2), squeeze=False)
    used = []
    for col, cohort in enumerate(COHORTS):
        for ri, denominator in enumerate(('all_rows', 'triggered')):
            table = tables['recovery_conditions' if ri == 0 else 'recovery_triggered_conditions']
            for j, policy in enumerate(('strict_stop', 'terminal_status', 'same_id_dedup')):
                rs = [next(iter(select(table, cohort=cohort, fault=f, policy=policy, status_budget=1, metric='completion')), None)
                      for f in ('ambiguous_after', 'terminal_noncommit')]
                used.extend({**r, 'denominator': denominator} for r in rs if r)
                intervals(axes[ri, col], rs, [x+(j-1)*.18 for x in range(2)], COLORS[j], label=policy.replace('_', ' '))
            axes[ri, col].set_xticks(range(2), ['Ambiguous\ncommitted', 'Terminal\nnoncommit'])
            decoration(axes[ri, col], ('All rows\nCompletion (%)' if ri == 0 else 'Triggered faults\nCompletion (%)') if col == 0 else None, True)
        axes[0, col].set_title(LABELS[cohort])
    axes[0, -1].legend(frameon=False, fontsize=7, loc='lower right')
    fig.suptitle('Bounded reconciliation at status budget 1')
    fig.text(.5, .01, 'Same-ID dedup requires a stronger atomic durable backend. All-row denominators retain missing certificates and untriggered faults.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .05, 1, .94])
    return fig, used


def actual_costs(tables):
    rows = select(tables['stream_conditions'], view='source')
    models = sorted({r['model'] for r in rows})
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 6), squeeze=False)
    used = []
    for col, cohort in enumerate(COHORTS):
        for i, model in enumerate(models):
            for j, stop in enumerate((True, False)):
                for ri, metric in enumerate(('api_cost_upper_usd', 'api_elapsed_seconds_sum')):
                    rs = select(rows, cohort=cohort, model=model, stop=stop, metric=metric)
                    used.extend(rs)
                    intervals(axes[ri, col], rs, [i*3+j], COLORS[j])
        names = [m.replace('gpt-', '')+'\n'+('online' if j == 0 else 'fresh fixed') for m in models for j in (0, 1)]
        for ri in (0, 1):
            axes[ri, col].set_xticks([i*3+j for i in range(len(models)) for j in (0, 1)], names, fontsize=7)
            decoration(axes[ri, col], ('Upper cost per stream (USD)' if ri == 0 else 'Elapsed sum per stream (s)') if col == 0 else None)
        axes[0, col].set_title(LABELS[cohort])
    fig.suptitle('Empirical source online / fresh fixed acquisition cost')
    fig.text(.5, .01, 'Conservative token-rate estimates, not invoices. Elapsed sums are not parallel campaign wall time; fresh selectors can differ.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .05, 1, .94])
    return fig, used


def family_effects(tables):
    definitions = [('source_online_minus_matched_heuristic', 'Source online − observe cover'),
                   ('graph_minus_source', 'Graph online − source online'),
                   ('graph_minus_padding', 'Graph online − padding online')]
    models = sorted({r['model'] for r in tables['contrasts'] if 'model' in r})
    fig, axes = plt.subplots(1, len(models), figsize=(11.5, 4.4), squeeze=False, sharey=True)
    used = []
    for ax, model in zip(axes[0], models):
        for i, (name, _) in enumerate(definitions):
            filters = dict(cohort='combined', model=model, contrast=name, metric='completion', budget=12)
            if name == 'source_online_minus_matched_heuristic':
                filters['baseline'] = 'observe_cover'
            points = select(tables['family_effects'], **filters)
            estimates = select(tables['contrasts'], **filters)
            used.extend({**p, 'record_type': 'family_effect'} for p in points)
            used.extend({**p, 'record_type': 'bootstrap_summary'} for p in estimates)
            for k, p in enumerate(sorted(points, key=lambda r: r['family'])):
                jitter = ((k % 9)-4)*.035
                ax.plot(p['difference']*100, i+jitter, '.', color=COLORS[i], alpha=.45, markersize=5)
            for r in estimates:
                ax.hlines(i, r['interval95'][0]*100, r['interval95'][1]*100, color='black', linewidth=2)
                ax.plot(r['estimate']*100, i, 'D', color='black', markersize=4)
        ax.axvline(0, color='#777777', linestyle=':', linewidth=1)
        ax.set_xlim(-105, 105); ax.set_xticks([-100, -50, 0, 50, 100])
        ax.set_yticks(range(len(definitions)), [label for _, label in definitions])
        ax.set_title(model); ax.set_xlabel('Completion difference (percentage points)')
        ax.grid(axis='x', alpha=.18)
    fig.suptitle('Paired family effects at budget 12: combined 36-family finite benchmark')
    fig.text(.5, .01, 'Dots: each family; diamonds and lines: family mean and descriptive 10,000-resample interval. No significance tests.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .06, 1, .94])
    return fig, used


def scaling(tables):
    rows = select(tables['policy_detail'], cohort='scaling', budget='full', stop=False, policy='observe_cover')
    metrics = ('query_count', 'interpreter_steps', 'certificate_pair_checks')
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.8), squeeze=False)
    used = []
    for ax, metric in zip(axes[0], metrics):
        for j, routes in enumerate(sorted({r['route_count'] for r in rows})):
            values = []
            for worlds in sorted({r['world_count'] for r in rows}):
                rs = select(rows, route_count=routes, world_count=worlds)
                if rs:
                    mean = sum(r[metric] for r in rs)/len(rs)
                    values.append((worlds, mean))
                    used.append({'metric': metric, 'route_count': routes, 'world_count': worlds, 'world_rows': len(rs), 'mean': mean})
            ax.plot([v[0] for v in values], [v[1] for v in values], 'o-', color=COLORS[j], label=f'{routes} routes', markersize=4)
        ax.set_xticks([2, 4, 8, 16]); ax.set_xlabel('Catalog worlds'); ax.set_ylabel(metric.replace('_', ' ').capitalize())
        decoration(ax)
    axes[0, -1].legend(frameon=False, fontsize=8)
    fig.suptitle('Dependent scaling siblings: full fixed observe-cover acquisition')
    fig.text(.5, .01, 'Repeated semantic routes and one parent family; operation counters, not independent evidence or elapsed time.', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .08, 1, .93])
    return fig, used


def figure_bytes(fig):
    """Remove timestamps and stabilize SVG IDs for exact-byte offline replay."""
    result = {}
    try:
        for extension in ('png', 'svg', 'pdf'):
            output = BytesIO()
            metadata = ({'Software': 'Phase11 offline analysis'} if extension == 'png' else
                        {'Date': None, 'Creator': 'Phase11 offline analysis'} if extension == 'svg' else
                        {'CreationDate': None, 'ModDate': None, 'Creator': 'Phase11 offline analysis'})
            fig.savefig(output, format=extension, dpi=180, metadata=metadata)
            result[extension] = output.getvalue()
    finally:
        plt.close(fig)
    return result


def build_figures():
    source = ROOT/'results/phase11/analysis'
    manifest = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    for name, digest in manifest['files'].items():
        if sha((source/name).read_bytes()) != digest:
            raise ValueError('ANALYSIS_HASH_MISMATCH:'+name)
    tables = {p.stem: read_rows(p) for p in source.glob('*.jsonl')}
    outputs = {}
    for name, function in [('deterministic_acquisition', deterministic), ('matched_model_comparison', model_comparison),
                           ('bounded_recovery', recovery), ('actual_api_costs', actual_costs),
                           ('paired_family_effects', family_effects), ('dependent_scaling', scaling)]:
        fig, rows = function(tables)
        for extension, data in figure_bytes(fig).items():
            outputs[name+'.'+extension] = data
        outputs[name+'.csv'] = csv_bytes(rows)
    outputs['manifest.json'] = jb({'analysis_manifest_sha256': sha((source/'manifest.json').read_bytes()),
                                   'files': {k: sha(v) for k, v in sorted(outputs.items())},
                                   'style': 'Matplotlib; honest zero-based outcome/cost axes; paired differences -100..100 percentage points',
                                   'uncertainty': 'descriptive equal-family bootstrap; scaling is dependent and shown without intervals'})
    destination = ROOT/'results/phase11/figures'
    for name, data in outputs.items():
        if (destination/name).exists() and (destination/name).read_bytes() != data:
            raise ValueError('IMMUTABLE_FIGURE_MISMATCH:'+name)
    for name, data in sorted(outputs.items()):
        immutable(destination/name, data)
    return {'figures': 6, 'files': len(outputs), 'directory': str(destination)}


if __name__ == '__main__':
    print(json.dumps(build_figures(), sort_keys=True), flush=True)
