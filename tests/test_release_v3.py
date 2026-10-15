"""Release verification must reject corruption without mutating evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def api():
    path=Path(__file__).resolve().parents[1]/'scripts/verify_phase3_release.py'
    if not path.exists():
        pytest.fail('Phase-three release verifier is missing')
    spec=importlib.util.spec_from_file_location('verify_phase3_release_test',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def digest(data):
    return hashlib.sha256(data).hexdigest()


def test_baseline_hashes_every_listed_file_and_detects_same_count_replacement(tmp_path):
    (tmp_path/'a.txt').write_bytes(b'original')
    manifest={'files':[{'path':'a.txt','sha256':digest(b'original')}]}
    assert api().verify_hash_manifest(tmp_path,manifest)['errors']==[]
    (tmp_path/'a.txt').write_bytes(b'changed')
    result=api().verify_hash_manifest(tmp_path,manifest)
    assert result['checked_files']==1
    assert 'HASH_MISMATCH:a.txt' in result['errors']


def test_manifest_cannot_escape_workspace_read_secrets_duplicate_or_hash_itself(tmp_path):
    for name,code in [('../outside','UNSAFE_MANIFEST_PATH'),('.env','SENSITIVE_MANIFEST_PATH'),
                       ('manifest.json','SELF_REFERENTIAL_MANIFEST')]:
        report=api().verify_hash_manifest(tmp_path,{'files':[{'path':name,'sha256':'0'*64}]},
                                          manifest_path=tmp_path/'manifest.json')
        assert any(code in error for error in report['errors'])
    report=api().verify_hash_manifest(tmp_path,{'files':[{'path':'x','sha256':'0'*64}]*2})
    assert any('DUPLICATE_MANIFEST_PATH' in error for error in report['errors'])


def test_exact_grid_detects_duplicate_replacement_and_metadata_drift():
    expected=[{'job_id':'a','case_id':'case-a','model':'m'},{'job_id':'b','case_id':'case-b','model':'m'}]
    bad=[expected[0],dict(expected[0])]
    result=api().verify_grid(bad,expected,('job_id',))
    assert result['observed']==result['expected']==2
    assert any('DUPLICATE_CONDITION' in error for error in result['errors'])
    assert result['missing']==1
    result=api().verify_grid([expected[0],{**expected[1],'case_id':'wrong'}],expected,('job_id',))
    assert any('METADATA_MISMATCH' in error for error in result['errors'])


def test_partial_grid_tolerates_missing_only_not_duplicates():
    expected=[{'job_id':'a'},{'job_id':'b'}]
    assert api().verify_grid(expected[:1],expected,('job_id',),allow_partial=True)['errors']==[]
    assert api().verify_grid(expected[:1],expected,('job_id',))['errors']
    assert api().verify_grid([expected[0],expected[0]],expected,('job_id',),allow_partial=True)['errors']


def test_budget_preserves_exact_prefix_and_includes_unknown_reserved_cost(tmp_path):
    old=tmp_path/'old'; new=tmp_path/'new'
    old.write_bytes(b'{"reservation_id":"old","status":"settled","reserved_usd":5.8589654,"cost_usd":5.8589654}\n')
    new.write_bytes(old.read_bytes()+b'{"reservation_id":"new","status":"unknown_usage","reserved_usd":0.5}\n')
    result=api().verify_budget(old,new)
    assert result['errors']==[]
    assert result['cumulative_exposure_usd']==pytest.approx(6.3589654)
    new.write_bytes(new.read_bytes()+b'{"reservation_id":"more","reserved_usd":14}\n')
    assert 'BUDGET_LIMIT_EXCEEDED' in api().verify_budget(old,new)['errors']
    new.write_bytes(b' '+old.read_bytes())
    assert 'BUDGET_PREFIX_CHANGED' in api().verify_budget(old,new)['errors']


def test_raw_reference_recomputes_request_fingerprint_and_checks_ledger(tmp_path):
    request={'model':'m','text':{'format':{'type':'json_object'}}}
    hashed=digest(json.dumps({'request':request,'replicate':0},sort_keys=True,ensure_ascii=False).encode())
    record={'request_hash':hashed,'request':request,'replicate':0,'reservation_id':'rid'}
    path=tmp_path/(hashed+'.json'); path.write_text(json.dumps(record))
    ledger={'rid':{'model':'m'}}
    assert api().verify_raw_reference(hashed,tmp_path,ledger)['errors']==[]
    record['request']['text']['format']={'type':'json_schema','schema':{'type':'object'}}
    path.write_text(json.dumps(record))
    assert 'REQUEST_FINGERPRINT_MISMATCH' in api().verify_raw_reference(hashed,tmp_path,ledger)['errors']
    assert 'RESERVATION_MISSING' in api().verify_raw_reference(hashed,tmp_path,{})['errors']


def test_machine_readable_real_accuracy_claims_remain_null_and_labels_pending():
    good={'human_annotated':False,'semantic_accuracy':None,'nested':{'human_semantic_accuracy':None}}
    assert api().verify_human_pending(good)==[]
    assert api().verify_human_pending({**good,'semantic_accuracy':.99})
    assert api().verify_human_pending({'labels':{'rater_a':{'authorized':True}}})
    assert api().verify_human_pending({'human_annotated':True})


def test_checkpoint_grids_derive_full_identity_from_case_and_context_inputs(tmp_path):
    for folder in ('data/benchmark','data/phase3','results/phase2/os_e2e'):
        (tmp_path/folder).mkdir(parents=True)
    case={'case_id':'a','family_id':'f','split':'development','scenario':'low','task_kind':'csv',
          'input_path':'/sandbox/input/a','output_path':'/sandbox/output/a','sink':'https://example.invalid',
          'require_send':False,'confidential':False}
    (tmp_path/'data/benchmark/synthetic_cases.jsonl').write_text(json.dumps(case)+'\n')
    (tmp_path/'data/phase3/synthetic_cases.jsonl').write_text(json.dumps({**case,'case_id':'b'})+'\n')
    (tmp_path/'data/phase3/real_prepared.jsonl').write_text(json.dumps({'skill_id':'skill','contexts':{'review_only':{}},'action_ids':[]})+'\n')
    (tmp_path/'results/phase2/os_e2e/frozen_tasks.json').write_text(json.dumps([{'case_id':'os','fixture':'csv'}]))
    grids=api().expected_grids(tmp_path)
    assert {r['job_id'] for r in grids['api/regression.jsonl']['rows']}=={
        'regression-a-gpt-6-luna-0','regression-a-gpt-6-luna-1',
        'regression-a-gpt-4.1-mini-0','regression-a-gpt-4.1-mini-1'}
    assert len(grids['api/factorial.jsonl']['rows'])==16
    assert len(grids['api/real.jsonl']['rows'])==4
    assert len(grids['os/runs.jsonl']['rows'])==20


def test_release_manifest_hashes_artifacts_but_excludes_itself(tmp_path):
    (tmp_path/'artifact.json').write_bytes(b'{}')
    manifest={'files_sha256':{'artifact.json':digest(b'{}')}}
    target=tmp_path/'release_manifest.json'; target.write_text(json.dumps(manifest))
    assert api().verify_hash_manifest(tmp_path,manifest,manifest_path=target)['errors']==[]
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    api().verify_hash_manifest(tmp_path,manifest,manifest_path=target)
    assert before=={p.name:p.read_bytes() for p in tmp_path.iterdir()}


def test_release_coverage_includes_new_code_and_preserved_failure_artifacts(tmp_path):
    for name in ('src/tsg/example_v3.py','scripts/run_phase3.py','docs/phase3_design.md',
                 'results/phase3/provenance/interrupted.tmp','results/phase3/provenance/release_manifest.json'):
        path=tmp_path/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('fixture')
    required=api().release_required_paths(tmp_path,tmp_path/'results/phase3/provenance/release_manifest.json')
    assert 'src/tsg/example_v3.py' in required
    assert 'scripts/run_phase3.py' in required
    assert 'docs/phase3_design.md' in required
    assert 'results/phase3/provenance/interrupted.tmp' in required
    assert 'results/phase3/provenance/release_manifest.json' not in required


def test_request_reference_cannot_substitute_another_model_or_replicate():
    row={'model':'m','replicate':1}
    assert api().request_identity_errors(row,{'model':'m','replicate':1},check_replicate=True)==[]
    assert 'REFERENCED_REPLICATE_MISMATCH' in api().request_identity_errors(row,{'model':'m','replicate':0},check_replicate=True)
    assert 'REFERENCED_MODEL_MISMATCH' in api().request_identity_errors(row,{'model':'other','replicate':1},check_replicate=True)
    assert api().request_identity_errors(row,{'model':'m','replicate':0},check_replicate=False)==[]


def test_partial_snapshot_reads_ledger_after_checkpoint_growth(tmp_path,monkeypatch):
    module=api(); base=tmp_path/'results/phase3'; (base/'api').mkdir(parents=True)
    (tmp_path/'results/api').mkdir(parents=True)
    prefix=b'{"reservation_id":"old","reserved_usd":5.8589654}\n'
    (tmp_path/'results/api/budget.jsonl').write_bytes(prefix)
    ledger=base/'api/budget.jsonl'; ledger.write_bytes(prefix)
    checkpoint=base/'api/real.jsonl'; checkpoint.write_text('{"job_id":"new"}\n')
    original=module.rows
    def growing_read(path):
        if Path(path)==checkpoint:
            ledger.write_bytes(prefix+b'{"reservation_id":"new","reserved_usd":0.5}\n')
        return original(path)
    monkeypatch.setattr(module,'rows',growing_read)
    snapshot=module.snapshot_evidence(tmp_path,{'api/real.jsonl':{}})
    assert 'new' in snapshot['ledger']
    assert snapshot['budget']['cumulative_exposure_usd']==pytest.approx(6.3589654)


def test_second_amendment_verifies_first_against_preserved_intermediate_freeze(tmp_path):
    module=api(); folder=tmp_path/'results/phase3/provenance'; folder.mkdir(parents=True)
    initial={'code_commit':'initial','files_sha256':{'src/tsg/real_v3.py':'a'*64,'other.py':'1'*64}}
    first={'code_commit':'first','files_sha256':{'src/tsg/real_v3.py':'a'*64,'other.py':'2'*64}}
    final={'code_commit':'second','files_sha256':{'src/tsg/real_v3.py':'b'*64,'other.py':'2'*64}}
    def write(name,value):
        path=folder/name; path.write_text(json.dumps(value)); return path
    initial_path=write('formal_freeze_initial.json',initial)
    first_path=write('formal_freeze_amendment_1.json',first)
    final_path=write('formal_freeze.json',final)
    boundary=write('boundary.json',{'acquisition_complete':True})
    common={'reasons':['Offline portability correction.'],'acquisition_boundary':boundary.relative_to(tmp_path).as_posix()}
    write('amendment_1.json',{**common,'initial_freeze_sha256':module.sha(initial_path),
          'amended_freeze_sha256':module.sha(first_path),'code_commit':'first','changed_files':['other.py']})
    write('amendment_2.json',{**common,'previous_freeze_file':first_path.relative_to(tmp_path).as_posix(),
          'previous_freeze_sha256':module.sha(first_path),'amended_freeze_sha256':module.sha(final_path),
          'code_commit':'second','changed_files':['src/tsg/real_v3.py']})
    result=module._amendment_report(tmp_path,final_path)
    assert result['errors']==[] and result['incomplete']==[]
    assert [a['number'] for a in result['amendments']]==[1,2]
    first_path.write_text(json.dumps({**first,'code_commit':'tampered'}))
    assert module._amendment_report(tmp_path,final_path)['errors']


def test_second_amendment_cannot_replace_or_skip_the_first_record(tmp_path):
    module=api(); folder=tmp_path/'results/phase3/provenance'; folder.mkdir(parents=True)
    for name in ('formal_freeze_initial.json','formal_freeze.json'):
        (folder/name).write_text(json.dumps({'code_commit':'c','files_sha256':{}}))
    (folder/'amendment_2.json').write_text(json.dumps({'previous_freeze_file':'../outside.json'}))
    result=module._amendment_report(tmp_path,folder/'formal_freeze.json')
    assert result['errors'] or result['incomplete']


def test_release_coverage_includes_followup_and_reproduction_entrypoints(tmp_path):
    names=('PHASE3.md','docs/reproduction_phase3.md','results/phase3_followup/manifest.json',
           'results/phase3_followup/api/raw/response.json','results/phase3_followup/analysis/summary.json')
    for name in names:
        path=tmp_path/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('{}')
    required=api().release_required_paths(tmp_path,tmp_path/'release_manifest.json')
    assert set(names)<=required


def test_budget_can_verify_primary_acquisition_prefix_without_reusing_old_baseline(tmp_path):
    primary=tmp_path/'primary'; followup=tmp_path/'followup'
    primary.write_text('{"reservation_id":"p","reserved_usd":13.5163768}\n')
    followup.write_bytes(primary.read_bytes()+b'{"reservation_id":"f","reserved_usd":0.5}\n')
    result=api().verify_budget(primary,followup,expected_baseline=13.5163768)
    assert result['errors']==[] and result['incremental_exposure_usd']==pytest.approx(.5)
    followup.write_bytes(followup.read_bytes()+b'{"reservation_id":"p","reserved_usd":0}\n')
    assert 'HISTORICAL_RESERVATION_CHANGED' in api().verify_budget(primary,followup,expected_baseline=13.5163768)['errors']


def followup_fixture(root,module):
    def put(name,value,jsonl=False):
        path=root/name; path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text((''.join(json.dumps(r)+'\n' for r in value) if jsonl else json.dumps(value)),encoding='utf-8')
        return path
    primary=[]; pending=[]
    for i,reason in enumerate(('credit_balance_exhausted','max_output_tokens')):
        request={'model':'gpt-6-luna','input':[{'role':'developer','content':'system'},{'role':'user','content':str(i)}],
                 'max_output_tokens':3000,'text':{'format':{'type':'json_schema','schema':{'type':'object'}}}}
        fingerprint=digest(json.dumps({'request':request,'replicate':0},sort_keys=True,ensure_ascii=False).encode())
        raw={'request':request,'replicate':0,'request_hash':fingerprint,'reservation_id':'old'+str(i),
             'status':'api_error' if i==0 else 'incomplete','http_status':429,'error_code':reason,
             'response':{'status':'incomplete','incomplete_details':{'reason':'max_output_tokens'}} if i else None}
        oldref='results/phase3/api/raw/'+fingerprint+'.json'; rawpath=put(oldref,raw)
        job='job-'+str(i); trial_id='phase3_real_followup_v1-'+digest((job+':'+fingerprint).encode())[:24]
        revised={**request,'max_output_tokens':6000 if i else 3000}
        newhash=digest(json.dumps({'request':revised,'replicate':0},sort_keys=True,ensure_ascii=False).encode())
        primary.append({'job_id':job,'skill_id':'s','model':'gpt-6-luna','context':'edge','variant':'raw',
                        'status':'unresolved','request_hash':fingerprint,'diagnostic_codes':['API_ERROR']})
        pending.append({'trial_id':trial_id,'original_job_id':job,'original_request_hash':fingerprint,
            'original_raw_ref':oldref,'original_raw_sha256':module.sha(rawpath),'skill_id':'s','model':'gpt-6-luna',
            'context':'edge','variant':'raw','split':'held_out_test','selection_reason':reason,
            'original_status':'unresolved','original_diagnostic_codes':['API_ERROR'],
            'original_max_output_tokens':3000,'max_output_tokens':6000 if i else 3000,'adaptive_output_cap':bool(i),
            'expected_request_hash':newhash,'new_raw_ref':'results/phase3_followup/api/raw/'+newhash+'.json',
            'request_change':{'max_output_tokens':[3000,6000]} if i else {},'replicate':0,
            'trial_kind':'new_followup_sample','phase_adapter':'phase_aware_posthoc_v1'})
    put('results/phase3/api/real.jsonl',primary,True)
    put('data/phase3/real_prepared.jsonl',[{'skill_id':'s','split':'held_out_test'}],True)
    put('results/phase3/api/budget.jsonl',[{'reservation_id':'old'+str(i),'model':'gpt-6-luna',
                                         'status':'unknown_usage','reserved_usd':13.5163768/2} for i in range(2)],True)
    for name in ('regression','new','factorial','os_contracts'):
        put('results/phase3/api/'+name+'.jsonl',[],True)
    base=root/'results/phase3_followup'; trialpath=put('results/phase3_followup/pending_trials.jsonl',pending,True)
    prefix=(root/'results/phase3/api/budget.jsonl').read_bytes()
    sources={p.relative_to(root).as_posix():module.sha(p) for p in (root/'results/phase3/api').rglob('*') if p.is_file()}
    sources['data/phase3/real_prepared.jsonl']=module.sha(root/'data/phase3/real_prepared.jsonl')
    manifest={'version':'phase3_real_followup_v1','planned_trials':2,'selection_counts':{'credit_balance_exhausted':1,'max_output_tokens':1},
              'primary_results_replaced':False,'automatic_retries':0,'workers':1,'budget_limit_usd':20,
              'source_sha256':sources,'pending_trials_sha256':module.sha(trialpath),
              'primary_budget_prefix_bytes':len(prefix),'primary_budget_sha256':digest(prefix),
              'inherited_cumulative_cost_usd':13.5163768}
    put('results/phase3_followup/manifest.json',manifest)
    put('results/phase3_followup/dry_run_summary.json',{'mode':'dry_run','api_calls_this_run':0})
    (base/'api').mkdir(); (base/'api/budget.jsonl').write_bytes(prefix)
    freeze_names=list(module.FOLLOWUP_FREEZE_REQUIRED)
    for name in freeze_names:
        if not (root/name).exists(): put(name,{})
    put('results/phase3_followup/provenance/acquisition_freeze.json',{'files_sha256':{
        name:module.sha(root/name) for name in freeze_names},'cumulative_budget_limit_usd':20,
        'historical_exposure_usd':13.5163768})
    return primary,pending,put


def test_fup_partial(tmp_path,monkeypatch):
    module=api(); monkeypatch.setattr(module,'FOLLOWUP_SELECTION_COUNTS',{'credit_balance_exhausted':1,'max_output_tokens':1})
    primary,pending,put=followup_fixture(tmp_path,module)
    report=module.verify_followup(tmp_path,allow_partial=True)
    assert report['errors']==[] and report['grid']['missing']==2 and report['incomplete']
    trialfile=tmp_path/'results/phase3_followup/pending_trials.jsonl'
    altered=[{**pending[0],'max_output_tokens':6000},pending[1]]; put(trialfile.relative_to(tmp_path),altered,True)
    report=module.verify_followup(tmp_path,allow_partial=True)
    assert any('PENDING_TRIALS_HASH_MISMATCH' in e for e in report['errors'])
    assert any('METADATA_MISMATCH' in e for e in report['errors'])


def test_fup_raw(tmp_path,monkeypatch):
    module=api(); monkeypatch.setattr(module,'FOLLOWUP_SELECTION_COUNTS',{'credit_balance_exhausted':1,'max_output_tokens':1})
    primary,pending,put=followup_fixture(tmp_path,module); trial=pending[0]
    raw=json.loads((tmp_path/trial['original_raw_ref']).read_text()); raw['tag']=trial['trial_id']
    put(trial['new_raw_ref'],raw)
    result={k:trial[k] for k in ('trial_id','original_job_id','original_request_hash','original_raw_ref',
            'skill_id','model','context','variant','split','trial_kind','selection_reason','adaptive_output_cap','max_output_tokens')}
    result.update(job_id=trial['trial_id'],request_hash=trial['expected_request_hash'],raw_ref=trial['new_raw_ref'],status='unresolved')
    put('results/phase3_followup/api/real.jsonl',[result],True)
    report=module.verify_followup(tmp_path,allow_partial=True)
    assert any('PRIMARY_RESERVATION_REUSED' in e for e in report['errors'])


def test_phase_replay_checks_hashes_and_requires_all_derived_files(tmp_path):
    module=api(); source=tmp_path/'results/phase3/api/real.jsonl'; source.parent.mkdir(parents=True)
    row={'job_id':'j','skill_id':'s','model':'m','context':'edge','variant':'raw','request_hash':None,
         'model_evaluated':False,'empty_candidate_set':True,'status':'not_applicable'}
    source.write_text(json.dumps(row)+'\n')
    folder=tmp_path/'results/phase3/phase_protocol'; folder.mkdir()
    summary={'source_sha256':{'results/phase3/api/real.jsonl':module.sha(source)},'include_real':True,
             'complete':True,'exploratory_posthoc':True,'primary_files_modified':False,
             'additional_api_requests':0,'additional_api_cost_usd':0,'os_execution_replayed':False}
    (folder/'summary.json').write_text(json.dumps(summary))
    result=module.verify_phase_protocol(tmp_path,allow_partial=True)
    assert 'phase_protocol/diagnostics/real.jsonl' in result['incomplete']
    source.write_text('{}\n')
    assert any('HASH_MISMATCH' in e for e in module.verify_phase_protocol(tmp_path,allow_partial=True)['errors'])


def completed_followup_fixture(root,module):
    primary,pending,put=followup_fixture(root,module); completed=[]
    ledger=root/'results/phase3_followup/api/budget.jsonl'
    for i,trial in enumerate(pending):
        raw=json.loads((root/trial['original_raw_ref']).read_text())
        raw.update(tag=trial['trial_id'],reservation_id='new'+str(i),request_hash=trial['expected_request_hash'])
        raw['request']['max_output_tokens']=trial['max_output_tokens']
        put(trial['new_raw_ref'],raw)
        with ledger.open('a') as stream:
            stream.write(json.dumps({'reservation_id':'new'+str(i),'model':'gpt-6-luna','status':'settled','reserved_usd':.1,'cost_usd':.1})+'\n')
        row={k:trial[k] for k in ('trial_id','original_job_id','original_request_hash','original_raw_ref',
            'skill_id','model','context','variant','split','trial_kind','selection_reason','adaptive_output_cap','max_output_tokens')}
        row.update(job_id=trial['trial_id'],request_hash=trial['expected_request_hash'],raw_ref=trial['new_raw_ref'],
                   status='valid' if i==0 else 'unresolved')
        completed.append(row)
    put('results/phase3_followup/api/real.jsonl',completed,True)
    summary={'mode':'execute','planned_trials':2,'completed_trials':2,'remaining_trials':0,'status_counts':{'valid':1,'unresolved':1},
             'workers':1,'automatic_retries':0,'budget_limit_usd':20,'primary_files_modified':False,
             'cumulative_cost_usd':13.7163768,'inherited_cumulative_cost_usd':13.5163768,'followup_cost_usd':.2,
             'remaining_budget_usd':6.2836232,
             'raw_references':[{k:r[k] for k in ('trial_id','original_request_hash','request_hash','raw_ref')} for r in completed]}
    put('results/phase3_followup/summary.json',summary)
    put('results/phase3/phase_protocol/diagnostics/real.jsonl',primary,True)
    names=('results/phase3/api/real.jsonl','results/phase3/phase_protocol/diagnostics/real.jsonl',
           'results/phase3_followup/pending_trials.jsonl','results/phase3_followup/api/real.jsonl','data/phase3/real_prepared.jsonl')
    put('results/phase3_followup/analysis/summary.json',{'primary_results_replaced':False,
        'independent_prospective_evaluation':False,'human_accuracy':None,'source_sha256':{n:module.sha(root/n) for n in names}})
    merged=[{**row,'evidence_job_id':row['job_id'],'job_id':row['original_job_id'],
             'primary_status':'unresolved','evidence_source':'followup_new_sample'} for row in completed]
    put('results/phase3_followup/analysis/consolidated_real.jsonl',merged,True)
    return summary,merged,put


def test_fup_final(tmp_path,monkeypatch):
    module=api(); monkeypatch.setattr(module,'FOLLOWUP_SELECTION_COUNTS',{'credit_balance_exhausted':1,'max_output_tokens':1})
    summary,merged,put=completed_followup_fixture(tmp_path,module)
    result=module.verify_followup(tmp_path)
    assert result['errors']==[] and result['incomplete']==[]
    merged[1]['status']='valid'
    put('results/phase3_followup/analysis/consolidated_real.jsonl',merged,True)
    assert any('consolidation:METADATA_MISMATCH' in e for e in module.verify_followup(tmp_path)['errors'])


def test_fup_cost(tmp_path,monkeypatch):
    module=api(); monkeypatch.setattr(module,'FOLLOWUP_SELECTION_COUNTS',{'credit_balance_exhausted':1,'max_output_tokens':1})
    summary,merged,put=completed_followup_fixture(tmp_path,module)
    put('results/phase3_followup/summary.json',{**summary,'cumulative_cost_usd':0})
    assert 'FOLLOWUP_SUMMARY_COST_MISMATCH:cumulative_cost_usd' in module.verify_followup(tmp_path)['errors']
