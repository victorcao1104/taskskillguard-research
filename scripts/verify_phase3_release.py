"""Read-only release audit: exact grids, immutable evidence and conservative cost.

Partial mode permits absent unfinished tracks, never corruption. No key lookup,
network access, model calls, corpus execution, or evidence mutation is performed.
An optional --output writes only the verification report to a new chosen path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.experiment_v3 import BASELINE, MODELS, protocol_jobs, synthesis_jobs
from tsg.analysis_v3 import VARIANTS, MECHANISMS

BASELINE_FILE_COUNT=10650
BASELINE_EXPOSURE=5.8589654
PRIMARY_EXPOSURE=13.5163768
FOLLOWUP_SELECTION_COUNTS={'credit_balance_exhausted':173,'max_output_tokens':1}
FOLLOWUP_FREEZE_REQUIRED={'scripts/resume_real_phase3.py','src/tsg/phase_protocol_v3.py',
    'src/tsg/models_v3.py','src/tsg/models.py','src/tsg/real_v3.py',
    'results/phase3_followup/manifest.json','results/phase3_followup/pending_trials.jsonl',
    'results/phase3_followup/dry_run_summary.json'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    path=Path(path)
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()] if path.exists() else []


def _safe_path(root,name):
    root=Path(root).resolve()
    if not isinstance(name,str) or '\\' in name or '\x00' in name:
        raise ValueError('UNSAFE_MANIFEST_PATH')
    pure=PurePosixPath(name)
    if pure.is_absolute() or '..' in pure.parts or ':' in name or not pure.parts:
        raise ValueError('UNSAFE_MANIFEST_PATH')
    if any(part in {'.git','.venv','local','work'} or (part.startswith('.env') and part!='.env.example') for part in pure.parts):
        raise ValueError('SENSITIVE_MANIFEST_PATH')
    path=(root/name).resolve()
    if not path.is_relative_to(root):
        raise ValueError('UNSAFE_MANIFEST_PATH')
    return path


def _manifest_entries(manifest):
    if isinstance(manifest.get('files_sha256'),dict):
        return [{'path':p,'sha256':h} for p,h in manifest['files_sha256'].items()]
    if isinstance(manifest.get('files'),list):
        return manifest['files']
    raise ValueError('INVALID_HASH_MANIFEST')


def verify_hash_manifest(root,manifest,*,manifest_path=None):
    errors=[]; seen=set(); checked=0
    try:
        entries=_manifest_entries(manifest)
    except (ValueError,AttributeError) as exc:
        return {'checked_files':0,'errors':[str(exc)]}
    for entry in entries:
        name=entry.get('path') if isinstance(entry,dict) else None
        try:
            path=_safe_path(root,name)
            if name in seen:
                errors.append('DUPLICATE_MANIFEST_PATH:'+name); continue
            seen.add(name)
            if manifest_path is not None and path==Path(manifest_path).resolve():
                errors.append('SELF_REFERENTIAL_MANIFEST:'+name); continue
            if not isinstance(entry.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',entry['sha256']):
                errors.append('INVALID_MANIFEST_DIGEST:'+name); continue
            checked+=1
            if not path.is_file():
                errors.append('MISSING_HASHED_FILE:'+name)
            elif sha(path)!=entry['sha256']:
                errors.append('HASH_MISMATCH:'+name)
        except (ValueError,OSError) as exc:
            errors.append(str(exc)+':'+str(name))
    return {'checked_files':checked,'listed_files':len(entries),'errors':errors}


def verify_grid(actual,expected,fields,*,allow_partial=False):
    def key(row):
        return tuple(row.get(k) for k in fields)
    expected_map={key(r):r for r in expected}; actual_keys=[key(r) for r in actual]
    errors=[]
    if len(expected_map)!=len(expected):
        errors.append('DUPLICATE_EXPECTED_CONDITION')
    duplicates=[k for k,n in Counter(actual_keys).items() if n>1]
    errors.extend('DUPLICATE_CONDITION:'+repr(k) for k in duplicates)
    unexpected=set(actual_keys)-set(expected_map)
    errors.extend('UNEXPECTED_CONDITION:'+repr(k) for k in sorted(unexpected,key=str))
    missing=set(expected_map)-set(actual_keys)
    if missing and not allow_partial:
        errors.append('MISSING_CONDITIONS:'+str(len(missing)))
    for row in actual:
        wanted=expected_map.get(key(row))
        if wanted is None:
            continue
        wrong=[k for k,v in wanted.items() if row.get(k)!=v]
        if wrong:
            errors.append('METADATA_MISMATCH:'+repr(key(row))+':'+','.join(sorted(wrong)))
    return {'expected':len(expected),'observed':len(actual),'missing':len(missing),
            'unexpected':len(unexpected),'duplicate_conditions':len(duplicates),
            'complete':not errors and not missing,'errors':errors}


def verify_budget(old_path,new_path,*,expected_baseline=BASELINE_EXPOSURE):
    errors=[]; old_bytes=Path(old_path).read_bytes(); new_bytes=Path(new_path).read_bytes()
    if not new_bytes.startswith(old_bytes):
        errors.append('BUDGET_PREFIX_CHANGED')
    def latest(data):
        return {r['reservation_id']:r for r in (json.loads(s) for s in data.decode('utf-8').splitlines() if s.strip())}
    old=latest(old_bytes); new=latest(new_bytes)
    def exposure(records):
        values=[r.get('cost_usd',r['reserved_usd']) for r in records.values()]
        if any(type(v) not in {int,float} or not math.isfinite(v) or v<0 for v in values):
            raise ValueError('INVALID_BUDGET_AMOUNT')
        return math.fsum(values)
    baseline=exposure(old); total=exposure(new)
    if not math.isclose(baseline,expected_baseline,abs_tol=1e-8,rel_tol=0):
        errors.append('BUDGET_BASELINE_MISMATCH')
    if any(new.get(k)!=v for k,v in old.items()):
        errors.append('HISTORICAL_RESERVATION_CHANGED')
    if total>20:
        errors.append('BUDGET_LIMIT_EXCEEDED')
    return {'historical_exposure_usd':baseline,'cumulative_exposure_usd':total,
            'incremental_exposure_usd':total-baseline,'historical_reservations':len(old),
            'cumulative_reservations':len(new),'prefix_sha256':hashlib.sha256(old_bytes).hexdigest(),
            'errors':errors}


def verify_raw_reference(fingerprint,directory,ledger):
    errors=[]
    if not isinstance(fingerprint,str) or not re.fullmatch('[0-9a-f]{64}',fingerprint):
        return {'errors':['INVALID_REQUEST_REFERENCE']}
    path=Path(directory)/(fingerprint+'.json')
    if not path.exists():
        return {'errors':['RAW_RESPONSE_MISSING']}
    try:
        raw=load(path)
        actual=hashlib.sha256(json.dumps({'request':raw['request'],'replicate':raw['replicate']},
                                          sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if actual!=fingerprint or raw.get('request_hash')!=fingerprint:
            errors.append('REQUEST_FINGERPRINT_MISMATCH')
        rid=raw.get('reservation_id')
        if rid not in ledger:
            errors.append('RESERVATION_MISSING')
        elif ledger[rid].get('model') is not None and ledger[rid]['model']!=raw['request'].get('model'):
            errors.append('RESERVATION_MODEL_MISMATCH')
        return {'reservation_id':rid,'request_hash':fingerprint,'model':raw['request'].get('model'),
                'replicate':raw['replicate'],'errors':errors}
    except (ValueError,TypeError,KeyError) as exc:
        return {'errors':['MALFORMED_RAW_RESPONSE:'+type(exc).__name__]}


def request_identity_errors(row,raw_summary,*,check_replicate):
    errors=[]
    if raw_summary.get('model')!=row.get('model'):
        errors.append('REFERENCED_MODEL_MISMATCH')
    if check_replicate and raw_summary.get('replicate')!=row.get('replicate',0):
        errors.append('REFERENCED_REPLICATE_MISMATCH')
    return errors


def verify_human_pending(value,path='$'):
    errors=[]
    if isinstance(value,dict):
        for key,item in value.items():
            location=path+'.'+key
            if key in {'semantic_accuracy','human_semantic_accuracy','human_accuracy'} and item is not None:
                errors.append('UNSUPPORTED_HUMAN_ACCURACY_CLAIM:'+location)
            if key=='human_annotated' and item is not False:
                errors.append('HUMAN_ANNOTATION_NOT_PENDING:'+location)
            if key in {'rater_a','rater_b','adjudication'} and item:
                errors.append('HUMAN_LABEL_NOT_PENDING:'+location)
            errors.extend(verify_human_pending(item,location))
    elif isinstance(value,list):
        for index,item in enumerate(value):
            errors.extend(verify_human_pending(item,f'{path}[{index}]'))
    return errors


def expected_grids(root):
    root=Path(root); grids={}
    old=rows(root/'data/benchmark/synthetic_cases.jsonl'); new=rows(root/'data/phase3/synthetic_cases.jsonl')
    prepared=rows(root/'data/phase3/real_prepared.jsonl')
    os_path=root/'results/phase2/os_e2e/frozen_tasks.json'
    os_tasks=load(os_path) if os_path.exists() else []
    def meta(case):
        return {k:case[k] for k in ('case_id','family_id','split','scenario')}
    def put(name,records,fields=('job_id',),references=()):
        grids[name]={'rows':records,'fields':fields,'references':references}
    put('api/factorial.jsonl',[{**meta(j['case']),**{k:j[k] for k in ('job_id','model','replicate','protocol_mode','catalog')},'track':'factorial'}
                              for j in protocol_jobs(old)],references=('request_hash',))
    for track,cases in [('regression',old),('new',new)]:
        expected=[{**meta(j['case']),**{k:j[k] for k in ('job_id','model','replicate','track')}} for j in synthesis_jobs(cases,track)]
        put(f'api/{track}.jsonl',expected,references=('p_request_hash','q_request_hash'))
        if track=='new':
            for split in sorted({r['split'] for r in expected}):
                name=f'api/new_{split}.jsonl'
                if (root/'results/phase3'/name).exists():
                    put(name,[r for r in expected if r['split']==split],references=('p_request_hash','q_request_hash'))
        for variant in VARIANTS:
            put(f'runtime/{track}_{variant}.jsonl',[{**r,'variant':variant} for r in expected],references=('p_request_hash','q_request_hash'))
    if (root/'results/phase3/api/smoke.jsonl').exists():
        smoke=[c for c in old if c['case_id'] in {'csv-0-low','csv-0-derived_summary'}]
        put('api/smoke.jsonl',[{**meta(j['case']),**{k:j[k] for k in ('job_id','model','replicate','track')}}
                              for j in synthesis_jobs(smoke,'smoke')],references=('p_request_hash','q_request_hash'))
    put('runtime/historical_same_inputs.jsonl',
        [{**{k:c[k] for k in ('case_id','family_id','split')},'model':model,'replicate':rep}
         for c in old for model in MODELS for rep in (0,1)],('case_id','model','replicate'),('p_request_hash',))
    put('runtime/mechanisms.jsonl',[{**meta(c),'variant':v,'model':None,'contract_source':'trusted_specification_fixed_control'}
                                  for c in new for v in MECHANISMS],('case_id','variant'))
    put('runtime/component_probes.jsonl',[{'probe':p,'variant':v} for p in ('public_wrong_body','confidential_same_literal')
                                        for v in ('full','no_body','no_taint')],('probe','variant'))
    put('api/real.jsonl',[{'job_id':f'real-{r["skill_id"]}-{context}-{variant}-{model}',
                          'skill_id':r['skill_id'],'context':context,'variant':variant,'model':model}
                         for r in prepared for context in r['contexts'] for variant in ('raw','graph_v2') for model in MODELS],references=('request_hash',))
    put('api/os_contracts.jsonl',[{'job_id':f'os-{c["case_id"]}-{model}-{mixed}','case_id':c['case_id'],'model':model,'mixed':mixed}
                                for c in os_tasks for model in MODELS for mixed in (False,True)],references=('request_hash',))
    os_rows=[]
    for case in os_tasks:
        origins=[('oracle_correct_policy',None)]+[(origin,model) for origin in ('LLM_generated_separated','LLM_generated_mixed') for model in MODELS]
        for origin,model in origins:
            for guard in (False,True):
                for rep in (0,1):
                    os_rows.append({'case_id':case['case_id'],'family_id':'os-template-'+case['fixture'],'origin':origin,
                                    'model':model,'guard_enabled':guard,'replicate':rep})
    put('os/runs.jsonl',os_rows,('case_id','origin','model','guard_enabled','replicate'),('request_hash',))
    return grids


def _verify_amendment_link(root,number,record_path,before_path,after_path):
    """Verify one immutable before/after transition rather than final-only state."""
    errors=[]
    data=load(record_path); before=load(before_path); after=load(after_path)
    previous_key='initial_freeze_sha256' if number==1 else 'previous_freeze_sha256'
    if data.get(previous_key)!=sha(before_path):
        errors.append('INITIAL_FREEZE_LINK_MISMATCH' if number==1 else 'PREVIOUS_FREEZE_LINK_MISMATCH')
    if number>1:
        try:
            if _safe_path(root,data.get('previous_freeze_file'))!=before_path.resolve():
                errors.append('PREVIOUS_FREEZE_FILE_MISMATCH')
        except ValueError:
            errors.append('PREVIOUS_FREEZE_FILE_INVALID')
    if data.get('amended_freeze_sha256')!=sha(after_path):
        errors.append('AMENDED_FREEZE_LINK_MISMATCH')
    changed={p for p in set(before['files_sha256'])|set(after['files_sha256'])
             if before['files_sha256'].get(p)!=after['files_sha256'].get(p)}
    listed={x if isinstance(x,str) else x.get('path') for x in data.get('changed_files',[])}
    if changed!=listed:
        errors.append('AMENDMENT_CHANGED_FILES_MISMATCH')
    if not data.get('reasons'):
        errors.append('AMENDMENT_REASON_MISSING')
    if data.get('code_commit')!=after.get('code_commit'):
        errors.append('AMENDMENT_CODE_COMMIT_MISMATCH')
    boundary=data.get('acquisition_boundary')
    try:
        if not _safe_path(root,boundary).is_file():
            errors.append('AMENDMENT_BOUNDARY_MISSING')
    except ValueError:
        errors.append('AMENDMENT_BOUNDARY_INVALID')
    return {'number':number,'record':record_path.relative_to(root).as_posix(),
            'previous_freeze':before_path.relative_to(root).as_posix(),
            'amended_freeze':after_path.relative_to(root).as_posix(),
            'changed_files':sorted(changed),'errors':errors}


def _amendment_report(root,freeze_path):
    root=Path(root); freeze_path=Path(freeze_path)
    provenance=freeze_path.parent; initial=provenance/'formal_freeze_initial.json'
    first=provenance/'amendment_1.json'; second=provenance/'amendment_2.json'
    intermediate=provenance/'formal_freeze_amendment_1.json'
    if not initial.exists():
        return {'amended':False,'amendments':[],'errors':['AMENDMENT_INITIAL_FREEZE_MISSING'] if first.exists() or second.exists() else [],'incomplete':[]}
    if not first.exists():
        return {'amended':True,'amendments':[],'errors':[], 'incomplete':['freeze_amendment_record_missing']}
    if second.exists() and not intermediate.exists():
        return {'amended':True,'amendments':[],'errors':['AMENDMENT_PREVIOUS_FREEZE_MISSING'],'incomplete':[]}
    links=[_verify_amendment_link(root,1,first,initial,intermediate if second.exists() else freeze_path)]
    if second.exists():
        links.append(_verify_amendment_link(root,2,second,intermediate,freeze_path))
    errors=[f'amendment_{link["number"]}:'+error for link in links for error in link['errors']]
    unsupported=[p.name for p in provenance.glob('amendment_*.json')
                 if re.fullmatch(r'amendment_\d+\.json',p.name) and p.name not in {'amendment_1.json','amendment_2.json'}]
    errors.extend('UNSUPPORTED_AMENDMENT:'+name for name in unsupported)
    return {'amended':True,'amendments':links,'changed_files':sorted({p for link in links for p in link['changed_files']}),
            'errors':errors,'incomplete':[]}


def release_required_paths(root,manifest_path):
    root=Path(root).resolve(); manifest_path=Path(manifest_path).resolve()
    paths={p for folder in ('data/phase3','results/phase3','results/phase3_followup') for p in (root/folder).rglob('*')
           if p.is_file() and p.resolve()!=manifest_path and
           (p.suffix!='.tmp' or any((root/folder/'provenance') in p.parents
                                  for folder in ('results/phase3','results/phase3_followup')))}
    paths.update(p for folder in ('src','tests') for p in (root/folder).rglob('*v3*.py'))
    paths.update((root/'scripts').glob('*phase3*.py'))
    paths.update((root/'docs').glob('phase3*.md'))
    paths.update(root/name for name in ('PHASE3.md','docs/reproduction_phase3.md'))
    required={p.relative_to(root).as_posix() for p in paths if p.is_file()}
    required.add('.github/workflows/phase3-tests.yml')
    return required


def _source_manifest(root,source_hashes,required=()):
    checked=verify_hash_manifest(root,{'files_sha256':source_hashes})
    missing=set(required)-set(source_hashes)
    checked['errors'].extend('SOURCE_HASH_COVERAGE_MISSING:'+name for name in sorted(missing))
    return checked


def verify_phase_protocol(root,*,allow_partial=False):
    """Check saved-input linkage and exact derived conditions without replaying."""
    root=Path(root); base=root/'results/phase3'; folder=base/'phase_protocol'
    report={'errors':[],'incomplete':[],'grids':{}}
    errors=report['errors']; incomplete=report['incomplete']
    summary_path=folder/'summary.json'
    if not summary_path.exists():
        incomplete.append('phase_protocol/summary.json'); return report
    summary=load(summary_path); hashes=summary.get('source_sha256',{})
    required={'data/benchmark/synthetic_cases.jsonl','data/phase3/synthetic_cases.jsonl'}
    pairs={'api/regression.jsonl':'api/regression.jsonl','api/new.jsonl':'api/new.jsonl',
           'runtime/regression_full.jsonl':'runtime/regression_full.jsonl',
           'runtime/new_full.jsonl':'runtime/new_full.jsonl','diagnostics/factorial.jsonl':'api/factorial.jsonl',
           'diagnostics/os_contracts.jsonl':'api/os_contracts.jsonl','diagnostics/real.jsonl':'api/real.jsonl'}
    # The final release includes real-source replay, not only the synthetic subset.
    if summary.get('include_real') is not True:
        incomplete.append('phase_protocol/include_real')
    required.add('data/phase3/real_prepared.jsonl')
    for name,source in pairs.items():
        source_name='results/phase3/'+source; required.add(source_name)
        original=rows(root/source_name)
        for row in original:
            for key in ('request_hash','p_request_hash','q_request_hash'):
                if row.get(key): required.add('results/phase3/api/raw/'+row[key]+'.json')
        target=folder/name
        if not target.exists():
            incomplete.append('phase_protocol/'+name); continue
        actual=rows(target)
        fields=('job_id',)
        stable=('job_id','case_id','family_id','split','scenario','model','replicate','track',
                'skill_id','context','variant','mixed','request_hash','p_request_hash','q_request_hash')
        expected=[{**{k:r[k] for k in stable if k in r},'exploratory_posthoc':True} for r in original]
        checked=verify_grid(actual,expected,fields,allow_partial=allow_partial)
        report['grids'][name]=checked; errors.extend(name+':'+e for e in checked['errors'])
        if checked['missing']: incomplete.append('phase_protocol/'+name)
        for row in actual: errors.extend(verify_human_pending(row))
    checked=_source_manifest(root,hashes,required); report['sources']=checked
    errors.extend(checked['errors']); errors.extend(verify_human_pending(summary))
    expected_flags={'exploratory_posthoc':True,'primary_files_modified':False,'additional_api_requests':0,
                    'additional_api_cost_usd':0,'os_execution_replayed':False}
    for key,value in expected_flags.items():
        if summary.get(key)!=value: errors.append('PHASE_REPLAY_METADATA_MISMATCH:'+key)
    if summary.get('complete') is not True: incomplete.append('phase_protocol/summary_incomplete')
    return report


def _followup_expected(root,primary,prepared):
    """Independently reconstruct eligibility and allowed request change from raw failures."""
    expected=[]; requests={}; sources=set(); errors=[]
    for row in primary:
        if row.get('status')!='unresolved': continue
        fingerprint=row.get('request_hash')
        if not isinstance(fingerprint,str) or not re.fullmatch('[0-9a-f]{64}',fingerprint):
            errors.append('ORIGINAL_REQUEST_REFERENCE_INVALID'); continue
        ref='results/phase3/api/raw/'+fingerprint+'.json'; sources.add(ref)
        raw=load(_safe_path(root,ref)); response=raw.get('response') or {}
        truncation=(raw.get('status')=='incomplete' and response.get('status')=='incomplete'
                    and (response.get('incomplete_details') or {}).get('reason')=='max_output_tokens')
        credit=(raw.get('status')=='api_error' and raw.get('http_status')==429
                and raw.get('error_code')=='credit_balance_exhausted')
        if not credit and not truncation: continue
        request=raw['request']; cap=request['max_output_tokens']; revised={**request,'max_output_tokens':6000 if truncation else cap}
        replicate=raw.get('replicate',0)
        if type(replicate) is not int or replicate<0: errors.append('ORIGINAL_REPLICATE_INVALID:'+row['job_id'])
        if truncation and cap>=6000: errors.append('TRUNCATION_CAP_NOT_INCREASED:'+row['job_id'])
        if request.get('model')!=row['model']: errors.append('ORIGINAL_MODEL_MISMATCH:'+row['job_id'])
        actual=hashlib.sha256(json.dumps({'request':request,'replicate':replicate},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if actual!=fingerprint or raw.get('request_hash')!=fingerprint: errors.append('ORIGINAL_REQUEST_HASH_MISMATCH:'+row['job_id'])
        new_hash=hashlib.sha256(json.dumps({'request':revised,'replicate':replicate},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        trial_id='phase3_real_followup_v1-'+hashlib.sha256((row['job_id']+':'+fingerprint).encode()).hexdigest()[:24]
        trial={'trial_id':trial_id,'original_job_id':row['job_id'],'original_request_hash':fingerprint,
            'original_raw_ref':ref,'original_raw_sha256':sha(root/ref),
            **{k:row[k] for k in ('skill_id','model','context','variant')},
            'split':prepared[row['skill_id']]['split'],
            'selection_reason':'max_output_tokens' if truncation else 'credit_balance_exhausted',
            'original_status':row['status'],'original_diagnostic_codes':row.get('diagnostic_codes',[]),
            'original_max_output_tokens':cap,'max_output_tokens':revised['max_output_tokens'],
            'adaptive_output_cap':truncation,'expected_request_hash':new_hash,
            'new_raw_ref':'results/phase3_followup/api/raw/'+new_hash+'.json',
            'request_change':{'max_output_tokens':[cap,6000]} if truncation else {},'replicate':replicate,
            'trial_kind':'new_followup_sample','phase_adapter':'phase_aware_posthoc_v1'}
        expected.append(trial); requests[trial_id]=revised
    return expected,requests,sources,errors


def verify_followup(root,*,allow_partial=False):
    root=Path(root); base=root/'results/phase3_followup'; errors=[]; incomplete=[]
    report={'errors':errors,'incomplete':incomplete}
    needed=('manifest.json','pending_trials.jsonl','api/budget.jsonl','provenance/acquisition_freeze.json','dry_run_summary.json')
    absent=[name for name in needed if not (base/name).exists()]
    if absent:
        incomplete.extend('followup/'+name for name in absent)
        # Missing unfinished evidence cannot conceal corruption of existing frozen inputs.
        for name,key in (('manifest.json','source_sha256'),('provenance/acquisition_freeze.json','files_sha256')):
            if (base/name).exists():
                checked=_source_manifest(root,load(base/name).get(key,{}))
                errors.extend(name+':'+e for e in checked['errors'])
        return report
    # Read summaries and results before the growing ledger. Missing in-flight outputs are not corruption.
    summary=load(base/'summary.json') if (base/'summary.json').exists() else None
    completed=rows(base/'api/real.jsonl'); manifest=load(base/'manifest.json'); pending=rows(base/'pending_trials.jsonl')
    primary=rows(root/'results/phase3/api/real.jsonl')
    prepared={r['skill_id']:r for r in rows(root/'data/phase3/real_prepared.jsonl')}
    expected,requests,raw_sources,selection_errors=_followup_expected(root,primary,prepared)
    errors.extend(selection_errors)
    counts=dict(Counter(t['selection_reason'] for t in expected))
    report['selection_counts']=counts
    if counts!=FOLLOWUP_SELECTION_COUNTS: errors.append('FOLLOWUP_SELECTION_COUNTS_MISMATCH')
    if manifest.get('selection_counts')!=counts or manifest.get('planned_trials')!=len(expected):
        errors.append('FOLLOWUP_MANIFEST_SELECTION_MISMATCH')
    for key,value in {'primary_results_replaced':False,'automatic_retries':0,'workers':1,'budget_limit_usd':20}.items():
        if manifest.get(key)!=value: errors.append('FOLLOWUP_MANIFEST_METADATA_MISMATCH:'+key)
    if manifest.get('pending_trials_sha256')!=sha(base/'pending_trials.jsonl'):
        errors.append('PENDING_TRIALS_HASH_MISMATCH')
    selection=verify_grid(pending,expected,('trial_id',))
    report['selection']=selection; errors.extend('selection:'+e for e in selection['errors'])
    required=raw_sources|{'data/phase3/real_prepared.jsonl','results/phase3/api/budget.jsonl'}|{
        'results/phase3/api/'+name+'.jsonl' for name in ('regression','new','factorial','os_contracts','real')}
    sources=_source_manifest(root,manifest.get('source_sha256',{}),required)
    report['sources']=sources; errors.extend(sources['errors'])
    frozen=load(base/'provenance/acquisition_freeze.json')
    freeze=_source_manifest(root,frozen.get('files_sha256',{}),FOLLOWUP_FREEZE_REQUIRED)
    report['freeze']=freeze; errors.extend('freeze:'+e for e in freeze['errors'])
    if frozen.get('cumulative_budget_limit_usd')!=20 or not math.isclose(frozen.get('historical_exposure_usd',0),PRIMARY_EXPOSURE,abs_tol=1e-8):
        errors.append('FOLLOWUP_FREEZE_BUDGET_MISMATCH')
    primary_budget=root/'results/phase3/api/budget.jsonl'; prefix=primary_budget.read_bytes()
    if manifest.get('primary_budget_prefix_bytes')!=len(prefix) or manifest.get('primary_budget_sha256')!=hashlib.sha256(prefix).hexdigest():
        errors.append('PRIMARY_BUDGET_MANIFEST_MISMATCH')
    budget=verify_budget(primary_budget,base/'api/budget.jsonl',expected_baseline=PRIMARY_EXPOSURE)
    report['budget']=budget; errors.extend(budget['errors'])
    if not math.isclose(manifest.get('inherited_cumulative_cost_usd',0),PRIMARY_EXPOSURE,abs_tol=1e-8):
        errors.append('FOLLOWUP_INHERITED_COST_MISMATCH')
    ledger={r['reservation_id']:r for r in rows(base/'api/budget.jsonl')}
    old_ids={r['reservation_id'] for r in rows(primary_budget)}
    result_fields=('trial_id','original_job_id','original_request_hash','original_raw_ref','skill_id','model','context',
                   'variant','split','trial_kind','selection_reason','adaptive_output_cap','max_output_tokens')
    wanted=[{**{k:t[k] for k in result_fields},'job_id':t['trial_id'],'request_hash':t['expected_request_hash'],
             'raw_ref':t['new_raw_ref']} for t in expected]
    grid=verify_grid(completed,wanted,('trial_id',),allow_partial=allow_partial)
    report['grid']=grid; errors.extend(grid['errors'])
    if grid['missing']: incomplete.append('followup/api/real.jsonl')
    by_trial={t['trial_id']:t for t in expected}; seen_reservations=set()
    for row in completed:
        trial=by_trial.get(row.get('trial_id'))
        if trial is None: continue
        checked=verify_raw_reference(row.get('request_hash'),base/'api/raw',ledger)
        errors.extend('raw:'+e for e in checked['errors'])
        if checked['errors']: continue
        rid=checked['reservation_id']
        if rid in old_ids: errors.append('PRIMARY_RESERVATION_REUSED:'+trial['trial_id'])
        if rid in seen_reservations: errors.append('FOLLOWUP_RESERVATION_REUSED:'+trial['trial_id'])
        seen_reservations.add(rid)
        raw=load(root/trial['new_raw_ref'])
        if raw.get('request')!=requests[trial['trial_id']] or raw.get('replicate')!=trial['replicate']:
            errors.append('FOLLOWUP_REQUEST_CHANGED:'+trial['trial_id'])
        if raw.get('tag')!=trial['trial_id']: errors.append('FOLLOWUP_RAW_TAG_MISMATCH:'+trial['trial_id'])
        errors.extend(verify_human_pending(row))
    allowed_raw={t['expected_request_hash'] for t in expected}
    unexpected_raw={p.stem for p in (base/'api/raw').glob('*.json')}-allowed_raw
    errors.extend('UNEXPECTED_FOLLOWUP_RAW:'+name for name in sorted(unexpected_raw))
    if summary is None:
        incomplete.append('followup/summary.json')
    else:
        errors.extend(verify_human_pending(summary))
        # A summary may lag a just-written result during acquisition; it must be a correct prefix.
        n=summary.get('completed_trials',-1)
        if type(n) is not int or n<0 or n>len(completed): errors.append('FOLLOWUP_SUMMARY_COUNT_MISMATCH')
        else:
            subset=completed[:n]
            if summary.get('status_counts')!=dict(Counter(r['status'] for r in subset)):
                errors.append('FOLLOWUP_SUMMARY_STATUS_MISMATCH')
            references=[{k:r[k] for k in ('trial_id','original_request_hash','request_hash','raw_ref')} for r in subset]
            if summary.get('raw_references')!=references: errors.append('FOLLOWUP_SUMMARY_REFERENCES_MISMATCH')
            if n!=len(expected): incomplete.append('followup/summary_incomplete')
        if summary.get('planned_trials')!=len(expected) or summary.get('remaining_trials')!=len(expected)-n:
            errors.append('FOLLOWUP_SUMMARY_PLANNED_MISMATCH')
        if summary.get('primary_files_modified') is not False: errors.append('FOLLOWUP_PRIMARY_MUTATION_CLAIM')
        for key,value in {'mode':'execute','workers':1,'automatic_retries':0,'budget_limit_usd':20}.items():
            if summary.get(key)!=value: errors.append('FOLLOWUP_SUMMARY_METADATA_MISMATCH:'+key)
        # Once the final result is present there can be no legitimate later call.
        # Compare final summary totals only after its count catches up to that result.
        if n==len(expected) and not grid['missing']:
            total=budget['cumulative_exposure_usd']; baseline=budget['historical_exposure_usd']
            values={'cumulative_cost_usd':total,'inherited_cumulative_cost_usd':baseline,
                    'followup_cost_usd':total-baseline,'remaining_budget_usd':20-total}
            for key,value in values.items():
                if not math.isclose(summary.get(key,-1),value,abs_tol=1e-8,rel_tol=0):
                    errors.append('FOLLOWUP_SUMMARY_COST_MISMATCH:'+key)
            if set(ledger)-old_ids!=seen_reservations: errors.append('FOLLOWUP_UNLINKED_RESERVATIONS')
    analysis_path=base/'analysis/summary.json'; consolidated_path=base/'analysis/consolidated_real.jsonl'
    if not analysis_path.exists() or not consolidated_path.exists():
        incomplete.append('followup/analysis')
    else:
        analysis=load(analysis_path); errors.extend(verify_human_pending(analysis))
        checked=_source_manifest(root,analysis.get('source_sha256',{}),{
            'results/phase3/api/real.jsonl','results/phase3/phase_protocol/diagnostics/real.jsonl',
            'results/phase3_followup/pending_trials.jsonl','results/phase3_followup/api/real.jsonl',
            'data/phase3/real_prepared.jsonl'})
        errors.extend('analysis:'+e for e in checked['errors'])
        phase={r['job_id']:r for r in rows(root/'results/phase3/phase_protocol/diagnostics/real.jsonl')}
        replacements={r['original_job_id']:r for r in completed}; merged=[]
        for old in primary:
            job=old['job_id']; replacement=replacements.get(job,phase.get(job))
            if replacement is None: errors.append('CONSOLIDATION_SOURCE_MISSING:'+job); continue
            merged.append({**replacement,'evidence_job_id':replacement['job_id'],'job_id':job,'primary_status':old['status'],
                           'evidence_source':'followup_new_sample' if job in replacements else 'primary_phase_reparse'})
        checked=verify_grid(rows(consolidated_path),merged,('job_id',))
        report['consolidation']=checked; errors.extend('consolidation:'+e for e in checked['errors'])
        if grid['missing']: errors.append('ANALYSIS_BEFORE_FOLLOWUP_COMPLETE')
        if analysis.get('primary_results_replaced') is not False or analysis.get('independent_prospective_evaluation') is not False:
            errors.append('FOLLOWUP_ANALYSIS_INTERPRETATION_MISMATCH')
    return report


def snapshot_evidence(root,grids):
    """Read dependent outputs before their append-only acquisition evidence.

    Checkpoints are atomic replacements. Reading all runtime outputs first,
    then API checkpoints, then the ledger ensures that a newly observed result
    is not checked against an older reservation snapshot during acquisition.
    """
    root=Path(root); base=root/'results/phase3'
    names=sorted(grids,key=lambda name:(name.startswith('api/'),name))
    loaded={name:rows(base/name) for name in names}
    old=root/'results/api/budget.jsonl'; current=base/'api/budget.jsonl'
    ledger={}; budget=None
    if old.exists() and current.exists():
        budget=verify_budget(old,current)
        ledger={r['reservation_id']:r for r in rows(current)}
    return {'checkpoints':loaded,'ledger':ledger,'budget':budget}


def verify_release(root,*,allow_partial=False,release_manifest=None):
    root=Path(root).resolve(); base=root/'results/phase3'; errors=[]; incomplete=[]; report={}
    baseline_path=base/'provenance/baseline_manifest.json'
    if baseline_path.exists():
        baseline=load(baseline_path); checked=verify_hash_manifest(root,baseline)
        report['baseline']=checked; errors.extend('baseline:'+e for e in checked['errors'])
        if baseline.get('baseline_commit')!=BASELINE:
            errors.append('BASELINE_COMMIT_MISMATCH')
        if checked['listed_files']!=BASELINE_FILE_COUNT:
            errors.append('BASELINE_FILE_COUNT_MISMATCH')
        try:
            names=set(subprocess.check_output(['git','ls-tree','-rz','--name-only',BASELINE],cwd=root).decode().split('\0'))-{''}
            if names!={r['path'] for r in baseline['files']}:
                errors.append('BASELINE_GIT_PATH_COVERAGE_MISMATCH')
        except (OSError,subprocess.CalledProcessError):
            errors.append('BASELINE_GIT_TREE_UNAVAILABLE')
    else:
        incomplete.append('baseline_manifest_missing')
    freeze_path=base/'provenance/formal_freeze.json'
    if freeze_path.exists():
        frozen=load(freeze_path); checked=verify_hash_manifest(root,frozen)
        report['freeze']=checked; errors.extend('freeze:'+e for e in checked['errors'])
        amendment=_amendment_report(root,freeze_path); report['amendment']=amendment
        errors.extend(amendment['errors']); incomplete.extend(amendment['incomplete'])
    else:
        incomplete.append('formal_freeze_missing')
    grids=expected_grids(root); inventory={}; refs={}; reference_count=0
    snapshot=snapshot_evidence(root,grids); loaded=snapshot['checkpoints']; ledger=snapshot['ledger']
    if snapshot['budget'] is not None:
        report['budget']=snapshot['budget']; errors.extend(report['budget']['errors'])
    else:
        incomplete.append('budget_ledger_missing')
    expected_counts={'api/factorial.jsonl':384,'api/regression.jsonl':528,'api/new.jsonl':1024,
                     'runtime/historical_same_inputs.jsonl':528,'runtime/mechanisms.jsonl':2048,
                     'runtime/component_probes.jsonl':6,'api/os_contracts.jsonl':48,'os/runs.jsonl':240}
    prepared=rows(root/'data/phase3/real_prepared.jsonl'); by_skill={r['skill_id']:r for r in prepared}
    if len(prepared)!=180:
        incomplete.append('prepared_skill_count')
    if len(by_skill)!=len(prepared):
        errors.append('DUPLICATE_PREPARED_SKILL')
    expected_counts['api/real.jsonl']=sum(len(r['contexts'])*4 for r in prepared) if prepared else 2160
    for name,count in expected_counts.items():
        if len(grids[name]['rows'])!=count:
            incomplete.append('input_grid_size:'+name)
    for name,grid in grids.items():
        path=base/name; actual=loaded[name]
        result=verify_grid(actual,grid['rows'],grid['fields'],allow_partial=allow_partial)
        inventory[name]=result; errors.extend(name+':'+e for e in result['errors'])
        if not path.exists() or result['missing']:
            incomplete.append(name)
        for row in actual:
            if name=='api/real.jsonl':
                errors.extend(name+':'+e for e in verify_human_pending(row))
                source=by_skill.get(row.get('skill_id'))
                if source and not source['action_ids']:
                    if not (row.get('model_evaluated') is False and row.get('empty_candidate_set') is True
                            and row.get('status')=='not_applicable' and row.get('request_hash') is None):
                        errors.append('EMPTY_CANDIDATE_MODEL_CREDIT:'+row.get('job_id','unknown'))
                elif row.get('model_evaluated') is False or row.get('empty_candidate_set') is True:
                    errors.append('NONEMPTY_CANDIDATE_SKIPPED:'+row.get('job_id','unknown'))
            for field in grid['references']:
                value=row.get(field)
                exempt=(name=='api/real.jsonl' and by_skill.get(row.get('skill_id'),{}).get('action_ids')==[]
                        or name=='os/runs.jsonl' and row.get('origin')=='oracle_correct_policy')
                if value is None and exempt:
                    continue
                directory=root/'results/api/raw' if name=='runtime/historical_same_inputs.jsonl' else base/'api/raw'
                key=(str(directory),value)
                if key not in refs:
                    refs[key]=verify_raw_reference(value,directory,ledger)
                reference_count+=1
                errors.extend(name+':'+str(value)+':'+e for e in refs[key]['errors'])
                if value is not None:
                    errors.extend(e+':'+name+':'+str(value) for e in request_identity_errors(
                        row,refs[key],check_replicate=name.startswith('api/') or name=='runtime/historical_same_inputs.jsonl'))
    # Runtime evidence must refer to its actual acquisition, not another valid request.
    for track in ('regression','new'):
        acquisition={r['job_id']:r for r in loaded[f'api/{track}.jsonl']}
        for variant in VARIANTS:
            name=f'runtime/{track}_{variant}.jsonl'
            for row in loaded[name]:
                source=acquisition.get(row.get('job_id'))
                if source is None or any(row.get(k)!=source.get(k) for k in ('p_request_hash','q_request_hash')):
                    errors.append('RUNTIME_ACQUISITION_REFERENCE_MISMATCH:'+name+':'+str(row.get('job_id')))
    os_contracts={(r['case_id'],r['model'],r['mixed']):r for r in loaded['api/os_contracts.jsonl']}
    for row in loaded['os/runs.jsonl']:
        if row.get('origin')=='oracle_correct_policy':
            continue
        source=os_contracts.get((row['case_id'],row['model'],row['origin']=='LLM_generated_mixed'))
        if source is None or source.get('request_hash')!=row.get('request_hash'):
            errors.append('OS_ACQUISITION_REFERENCE_MISMATCH:'+row['case_id'])
        if type(row.get('contract_decided')) is not bool:
            errors.append('OS_CONTRACT_DECISION_MISSING:'+row['case_id'])
    for path in (root/'data/phase3/real_annotation_handoff.jsonl',):
        if not path.exists():
            incomplete.append(path.relative_to(root).as_posix())
        for row in rows(path):
            errors.extend(verify_human_pending(row))
    for row in prepared:
        errors.extend(verify_human_pending(row))
    summary_path=base/'analysis/summary.json'
    if summary_path.exists():
        summary=load(summary_path); errors.extend(verify_human_pending(summary.get('real',{})))
        if summary.get('complete') is not True:
            incomplete.append('analysis_summary_incomplete')
    else:
        incomplete.append('analysis_summary_missing')
    for name,verify in (('phase_protocol',verify_phase_protocol),('followup',verify_followup)):
        checked=verify(root,allow_partial=allow_partial); report[name]=checked
        errors.extend(name+':'+e for e in checked['errors']); incomplete.extend(checked['incomplete'])
    manifest_path=Path(release_manifest) if release_manifest else base/'provenance/release_manifest.json'
    if not manifest_path.is_absolute():
        manifest_path=root/manifest_path
    if manifest_path.exists():
        manifest=load(manifest_path); checked=verify_hash_manifest(root,manifest,manifest_path=manifest_path)
        report['release_manifest']=checked; errors.extend('release:'+e for e in checked['errors'])
        listed={r['path'] for r in _manifest_entries(manifest)}
        required=release_required_paths(root,manifest_path)
        missing=required-listed
        if missing:
            errors.append('RELEASE_MANIFEST_COVERAGE_MISSING:'+str(len(missing)))
        report['release_manifest']['uncovered_paths']=sorted(missing)
    else:
        incomplete.append('release_manifest_missing')
    report.update(grids=inventory,request_references=reference_count,unique_referenced_requests=len(refs),
                  errors=sorted(set(errors)),incomplete=sorted(set(incomplete)),
                  complete=not errors and not incomplete,mode='partial' if allow_partial else 'final',
                  human_accuracy_check_scope='machine-readable claims and blank rater fields; no natural-language semantic guarantee')
    report['ok']=not errors and (allow_partial or not incomplete)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--allow-partial',action='store_true')
    parser.add_argument('--release-manifest',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        report=verify_release(args.root,allow_partial=args.allow_partial,release_manifest=args.release_manifest)
    except (ValueError,TypeError,KeyError,OSError) as exc:
        report={'ok':False,'complete':False,'errors':['AUDIT_INPUT_ERROR:'+type(exc).__name__+':'+str(exc)]}
    if args.output:
        if args.output.exists():
            raise ValueError('REPORT_OUTPUT_ALREADY_EXISTS')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,allow_nan=False))
    return 0 if report['ok'] else 1


if __name__=='__main__':
    raise SystemExit(main())
