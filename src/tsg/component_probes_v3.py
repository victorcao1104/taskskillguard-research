"""Orthogonal body versus provenance probes, separate from family generalization."""
import json
from .benchmark import build_cases
from .pipeline_v3 import run_pipeline_v3
from .planner_v3 import parse_planner_record


def run_probes():
    rows = []
    for name, confidential, text in [('public_wrong_body',False,'PUBLIC_OTHER'),
                                     ('confidential_same_literal',True,'DONE')]:
        case = next(c for c in build_cases() if c['case_id']=='csv-0-data_flow_misuse')
        case.update(case_id='probe-'+name, family_id='mechanistic-probe',split='mechanistic',
                    task_kind='probe_identity',confidential=confidential,input_text=text,expected_output=text)
        for action in case['actions']:
            if action['operation']=='transform':
                action['resource']='probe_identity'
        prediction = {'rules':[{'operation':'file.read','resource':case['input_path']},
                               {'operation':'file.write','resource':case['output_path']},
                               {'operation':'network.post','resource':case['sink']}],
                      'plan':['read_input','transform','write_output','send_status'],'unknowns':[]}
        planner = parse_planner_record({'status':'completed','text':json.dumps(prediction)},case)
        for variant in ('full','no_body','no_taint'):
            result = run_pipeline_v3(case,planner,q_plan=[a['id'] for a in case['actions']],
                                     variant=variant,transform_fn=lambda _kind,value:value)
            rows.append({'probe':name,'variant':variant,'result':result,
                         'interpretation':'constructed orthogonal mechanism, not independent family or real-corpus prevalence'})
    return rows
