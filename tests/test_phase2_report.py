import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / 'scripts' / (name + '.py')
    if not path.exists():
        pytest.fail('The offline report/plot generator has not been implemented')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_final_report_refuses_incomplete_model_snapshot(tmp_path):
    module = load_script('write_phase2_report')
    directory = tmp_path / 'results/phase2/pipeline_analysis'
    directory.mkdir(parents=True)
    (directory / 'summary.json').write_text(json.dumps({'analysis_status': 'partial_saved_counts'}))
    with pytest.raises(ValueError, match='ANALYSIS_INCOMPLETE'):
        module.build_report(tmp_path)
    assert not (tmp_path / 'docs/phase2_report.md').exists()


def test_plot_selection_excludes_missing_runs_instead_of_zero_filling():
    module = load_script('plot_phase2')
    analysis = {'track_count_completion': {'pipeline': False, 'os_e2e': False},
                'runtime': [{'track': 'P_Q_pipeline_ablation', 'split': 'held_out_test',
                             'variant': 'full', 'model': 'm', 'n_valid_runs': 0,
                             'n_unauthorized_execution': 0, 'n_attack_opportunities': 0}]}
    assert module.ready_pipeline_rows(analysis) == []
    analysis['track_count_completion']['pipeline'] = True
    assert module.ready_pipeline_rows(analysis) == []


def test_report_reads_actual_contract_and_graph_counts_without_human_accuracy(tmp_path):
    module = load_script('write_phase2_report')
    p = tmp_path / 'results/phase2'
    (p / 'pipeline_analysis').mkdir(parents=True)
    (p / 'pipeline_analysis/summary.json').write_text(json.dumps({'analysis_status': 'partial_saved_counts'}))
    (p / 'contracts').mkdir()
    (p / 'contracts/summary.json').write_text(json.dumps({'probes': 7, 'passed': 5, 'solver_counts': {'SAT': 2, 'UNSAT': 1, 'UNSUPPORTED': 4}}))
    report = module.build_report(tmp_path, allow_partial=True)
    assert '5/7' in report
    assert '33/33' not in report
    assert '真人' in report and 'pending' in report


def test_complete_report_uses_family_level_adjustment_and_saved_goal_numerator(tmp_path):
    module = load_script('write_phase2_report')
    directory = tmp_path / 'results/phase2/pipeline_analysis'
    directory.mkdir(parents=True)
    summary = {
        'analysis_status': 'complete_saved_counts',
        'track_count_completion': {'pipeline': True, 'real_180': True, 'os_e2e': True},
        'paired_comparisons': [{'track': 'P_Q_pipeline_ablation', 'split': 'held_out_test',
                                'model': 'fixture', 'left': 'full', 'right': 'no_guard',
                                'endpoint': 'no_unauthorized_execution', 'n_families_complete': 2,
                                'family_mcnemar': {'p_exact': .5, 'p_holm_all_reported': .875}}],
        'os_e2e': {'n_saved_runs': 0, 'n_expected_runs': 0, 'n_saved_contracts': 0,
                   'n_expected_contracts': 0, 'n_fixture_cases': 0, 'n_fixture_families': 0,
                   'runtime': [], 'contracts': []},
    }
    (directory / 'summary.json').write_text(json.dumps(summary))
    report = module.build_report(tmp_path)
    assert '0.5000 | 0.8750' in report
    assert module._goal_count({'n_goal_success': 2, 'n_valid_runs': 3, 'goal_success_rate': .667}) == 2


def test_os_plot_uses_pooled_context_once_and_preserves_unresolved_pipeline_cells():
    module = load_script('plot_phase2')
    analysis = {'track_count_completion': {'pipeline': True, 'os_e2e': True},
                'os_e2e': {'runtime': [{'context': 'low', 'n_valid_runs': 12},
                                       {'context': 'high', 'n_valid_runs': 12},
                                       {'context': 'all_contexts', 'n_valid_runs': 24}]},
                'runtime': [{'track': 'P_Q_pipeline_ablation', 'split': 'held_out_test',
                             'model': 'm', 'variant': 'full', 'n_valid_runs': 0,
                             'n_unresolved_runs': 88, 'goal_success_rate': None}]}
    assert sum(r['n_valid_runs'] for r in module.os_plot_rows(analysis)) == 24
    cells = module.ready_pipeline_rows(analysis, include_unknown=True)
    assert len(cells) == 1 and cells[0]['goal_success_rate'] is None
