"""Evidence consistency and old-version preservation audit; read-only except report."""
import gzip
import hashlib
import json
import platform
import re
import subprocess
from collections import Counter
from pathlib import Path
from gr14.campaign import STUDY,ROOT,source_hashes,grid
from gr14.provider import immutable,decode
from gr14.data import inputs_for
from analyze import replay_compare,read_rows
from compact_summaries import strip_records

def main():
    issues=[];replays=[];verified_data=set();summary_count=0
    for campaign in ('development','main','combined','controls','combined_controls'):
        for p in (STUDY/'results'/campaign).glob('*.json'):
            summary=json.loads(p.read_text(encoding='utf-8'))
            full=json.loads(gzip.decompress(p.with_suffix('.json.gz').read_bytes()))
            expected=strip_records(full);expected.setdefault('attempts',[])
            if summary!=expected:issues.append('SUMMARY_EVIDENCE_MISMATCH:'+campaign+'/'+p.name)
            summary_count+=1
    for p in (STUDY/'results/stress').glob('*.json'):
        summary=json.loads(p.read_text(encoding='utf-8'));full=json.loads(gzip.decompress(p.with_suffix('.json.gz').read_bytes()))
        if summary['final']!=strip_records(full):issues.append('STRESS_SUMMARY_MISMATCH:'+p.name)
        source=STUDY/'results'/summary['campaign']/(p.stem.removeprefix(summary['campaign']+'--')+'.json')
        if summary['selected']!=json.loads(source.read_text(encoding='utf-8'))['selected']:issues.append('STRESS_PROGRAM_MISMATCH:'+p.name)
        summary_count+=1
    for campaign in ('main','combined'):
        manifest=json.loads((STUDY/'provenance'/f'{campaign}_freeze.json').read_text(encoding='utf-8'))
        if manifest['source_hashes']!=source_hashes():issues.append('SOURCE_DRIFT:'+campaign)
        rows=read_rows(campaign)
        planned={(c['case_id'],m,model,r) for c,m,model,r in grid(campaign)}
        for c,_,_,_ in grid(campaign):
            if c['case_id'] in verified_data:continue
            saved=json.loads((STUDY/'data'/f"{c['case_id']}.json").read_text(encoding='utf-8'))
            expected={'case':c,'inputs':{phase:inputs_for(c,phase) for phase in ('validation','final','stress')}}
            if saved!=expected:issues.append('FROZEN_DATA_MISMATCH:'+c['case_id'])
            verified_data.add(c['case_id'])
        actual={(r['case_id'],r['method'],r['model'],r['replicate']) for r in rows}
        if actual!=planned or len(rows)!=len(planned):issues.append('GRID_MISMATCH:'+campaign)
        check=replay_compare(ROOT/'work'/f'v14-{campaign}-fresh',campaign);replays.append(check)
        if check['mismatches'] or check['compared']!=len(rows):issues.append('REPLAY_MISMATCH:'+campaign)
    rawpaths=list((STUDY/'api/raw').glob('*.json'));raws=[json.loads(p.read_text(encoding='utf-8')) for p in rawpaths]
    for r in raws:
        recomputed=hashlib.sha256(json.dumps({'request':r['request'],'replicate':r['replicate']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if recomputed!=r['request_hash']:issues.append('RAW_REQUEST_HASH_MISMATCH:'+r['request_hash'])
    requests=list((STUDY/'api/requests').glob('*.json'));request_hashes=set()
    for p in requests:
        j=json.loads(p.read_text(encoding='utf-8'));request_hashes.add(j['expected_request_hash'])
        if not (STUDY/'api/raw'/f"{j['expected_request_hash']}.json").exists():issues.append('MISSING_RAW:'+p.name)
    if request_hashes!={r['request_hash'] for r in raws}:issues.append('REQUEST_RAW_SET_MISMATCH')
    episode_requests=sum(r['requests'] for c in ('development','main','combined') for r in read_rows(c))
    if episode_requests!=len(raws):issues.append('REQUEST_COUNT_MISMATCH')
    old=ROOT/'studies/stateful-recovery-v13/api/budget.jsonl';new=STUDY/'api/budget.jsonl'
    if not new.read_bytes().startswith(old.read_bytes()):issues.append('OLD_LEDGER_PREFIX_CHANGED')
    changed=subprocess.check_output(['git','diff','--name-status','archive-before-goal-recovery-v14-20261018','--diff-filter=DMRT'],cwd=ROOT,text=True)
    if changed.strip():issues.append('OLD_TRACKED_FILES_CHANGED')
    # Count only; never print a possible credential match.
    key_pattern=re.compile(rb'(?<![A-Za-z0-9])sk-(?:proj-)?[A-Za-z0-9_-]{24,}')
    credential_files=[]
    for p in STUDY.rglob('*'):
        if p.is_file() and p.suffix in ('.json','.jsonl','.py','.md','.txt') and key_pattern.search(p.read_bytes()):credential_files.append(str(p.relative_to(STUDY)))
    if credential_files:issues.append('CREDENTIAL_PATTERN_REQUIRES_REVIEW')
    result={'issues':issues,'python':platform.python_version(),'platform':platform.platform(),'replay':replays,'verified_frozen_cases':len(verified_data),'summary_gzip_comparisons':summary_count,
        'raw_count':len(raws),'recorded_episode_requests':episode_requests,'raw_statuses':dict(Counter(r.get('status') for r in raws)),
        'provider_models':dict(Counter(r.get('response',{}).get('model','unavailable') for r in raws)),
        'normalization':dict(Counter(decode(r)['normalization'] or 'none' for r in raws)),
        'old_tracked_changes':changed.splitlines(),'old_ledger_prefix_bytes':old.stat().st_size,
        'old_ledger_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'credential_pattern_files':credential_files,
        'interpretation':'Fresh cached replay compares selected programs, attempts, all validation/final scores and traces; only wall/CPU timing is excluded. No API requests made by replay.'}
    immutable(STUDY/'reports/reproduction_audit.json',result)
    print(json.dumps(result,indent=2))
    if issues:raise SystemExit(1)
if __name__=='__main__':main()
