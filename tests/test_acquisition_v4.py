import importlib.util
import json
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]


def runner():
    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location('phase4_runner',ROOT/'scripts/run_phase4.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prospective_grid_complete_paired_and_no_truth_sent():
    jobs, selection=runner().specs()
    assert Counter(j['track'] for j in jobs)=={'synthetic':144,'real':216,'discovery':24}
    assert len({j['job_id'] for j in jobs})==384
    assert len(selection['real_reasoning_ids'])==18
    assert len(selection['zero_candidate_discovery_ids'])==12
    groups={}
    for job in jobs:
        payload=json.loads(job['prompt'])
        assert 'truth' not in payload and 'truth' not in payload.get('task_context',{})
        if job['track']=='synthetic':
            assert all(c['id'].startswith('c_') for c in payload['candidates'])
            assert set(job['candidate_id_mapping'].values())==set(job['ids'])
        if job['track']!='discovery':
            groups.setdefault((job['track'],job['case_id'],job['context'],job['model']),{})[job['view']]=payload
    for views in groups.values():
        assert set(views)=={'raw','table','graph'}
        assert views['raw']=={k:v for k,v in views['table'].items() if k!='nodes'}
        assert views['table']=={k:v for k,v in views['graph'].items() if k!='edges'}


def test_selection_independent_of_input_order_and_unique_families():
    module=runner()
    prepared=module.rows(ROOT/'data/phase4/real_prepared.jsonl')
    for zero, count in [(False,18),(True,12)]:
        first=module.select_real(prepared,count,zero=zero)
        reverse=module.select_real(list(reversed(prepared)),count,zero=zero)
        assert [p['skill_id'] for p in first]==[p['skill_id'] for p in reverse]
        assert len({p['family_id'] for p in first})==count
