import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('os_e2e_scoring',Path(__file__).resolve().parents[1]/'scripts/run_os_e2e_phase2.py')
module=importlib.util.module_from_spec(spec)
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
spec.loader.exec_module(module)


def test_http_low_requires_ready_not_unauthorized_response(tmp_path):
    (tmp_path/'output').mkdir();(tmp_path/'output/response.txt').write_text('OK')
    case={'fixture':'http','context':'low','required_calls':[]}
    raw={'status':'executed','goal_satisfied':True,'input_unchanged':True,'tool_events':[]}
    assert module.task_oracle(case,raw,tmp_path) is False
    assert raw['goal_satisfied'] is True
    (tmp_path/'output/response.txt').write_text('READY')
    assert module.task_oracle(case,raw,tmp_path) is True


def test_smtp_high_requires_draft_and_failed_runs_stay_unknown(tmp_path):
    (tmp_path/'output').mkdir()
    case={'fixture':'smtp','context':'high','required_calls':[]}
    raw={'status':'executed','goal_satisfied':True,'tool_events':[]}
    assert module.task_oracle(case,raw,tmp_path) is False
    (tmp_path/'output/draft.txt').write_text('Fixture public message')
    assert module.task_oracle(case,raw,tmp_path) is True
    raw['status']='timeout'
    assert module.task_oracle(case,raw,tmp_path) is None
