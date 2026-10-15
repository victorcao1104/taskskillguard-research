import importlib.util
from pathlib import Path


def test_os_table_does_not_double_count_context_totals_and_subgroups():
    path=Path(__file__).resolve().parents[1]/'scripts/report_phase3.py'
    spec=importlib.util.spec_from_file_location('report_phase3',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows=[]
    for context,n in [('low',12),('high',12),('all_contexts',24)]:
        rows.append(dict(context=context,origin='oracle',model=None,guard_enabled=True,
                         n_expected_runs=n,n_valid_runs=n,n_goal_success=n,n_unauthorized_execution=0))
    result=module.historical_os_rows(rows)
    assert len(result)==1
    assert result[0]['conditions']==24
    assert result[0]['confirmed_completion']==24
