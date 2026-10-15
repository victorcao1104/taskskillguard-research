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
