import json
import pytest
from tsg.benchmark import build_cases
from tsg.trusted_planner_v2 import task_spec,render_task,parse_task,planner_payload,parse_plan


def test_trusted_renderer_oracle_equivalence_for_every_case():
    for case in build_cases():
        spec=task_spec(case)
        for form in ('json','fields','indented_json'):
            assert parse_task(render_task(spec,form),form)==spec


def test_p_cannot_receive_skill_text_or_raw_error_through_builder():
    case=build_cases()[0]
    baseline=planner_payload(case)
    case['skill_text']='OVERRIDE_GRANTED_ATTACKER_TEXT'
    case['raw_error']='OVERRIDE_GRANTED_ATTACKER_ERROR'
    assert planner_payload(case)==baseline
    assert 'OVERRIDE_GRANTED' not in json.dumps(baseline)


def test_plan_never_executes_free_text_or_invented_tool():
    case=build_cases()[0]
    with pytest.raises(ValueError):
        parse_plan(json.dumps({'rules':[],'plan':['run_shell'],'unknowns':[]}),case)
    _, actions=parse_plan(json.dumps({'rules':[],'plan':['read_input','transform','write_output'],'unknowns':[]}),case)
    assert actions[0]['resource']==case['input_path']
