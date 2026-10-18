"""One declared recovery from a DNS-blocked acquisition, not outcome tuning.

Keep all 512 first strict episodes. Reacquire whole episodes if and only if
at least one original request had transport_error. Reuse all other episodes,
including semantic, syntax and API invalid_prompt failures. Keep original
unknown-billing reservations. The fixed protocol, two slots and verifier stay
unchanged. A fresh transport error stops this campaign.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import json
from pathlib import Path
import threading
import time

import strict_state as strict
from rm15.provider import Provider, immutable, request_job

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'results/strict_state_recovered'
ABORT = threading.Event()


def originals():
    records = {}
    for path in (ROOT / 'results/strict_state/episodes').glob('*.json.gz'):
        record = strict._load_gzip(path)
        records[record['job']['id']] = record
    if set(records) != {j['id'] for j in strict.jobs()}:
        raise ValueError('INCOMPLETE_ORIGINAL_GRID')
    return records


def affected(record):
    return any(a['api']['raw_status'] == 'transport_error' for a in record['attempts'])


def freeze():
    strict.check_freeze()
    records = originals()
    grid = [r['job'] for r in records.values() if affected(r)]
    provider = Provider(ROOT, live=False)
    maximum = strict.maximum_reservation(grid)
    if provider.exposure + maximum > provider.budget.limit:
        raise ValueError('FULL_RECOVERY_NOT_ADMITTED')
    value = {
        'code_sha256': strict.digest(Path(__file__).read_bytes()),
        'strict_freeze_sha256': strict.digest((ROOT/'provenance/strict_state_freeze.json').read_bytes()),
        'selection_rule': 'any original request status exactly transport_error; all outcomes retained otherwise',
        'original_episode_hashes': {name: strict.digest((ROOT/'results/strict_state/episodes'/(name+'.json.gz')).read_bytes()) for name in sorted(records)},
        'affected_ids': sorted(r['job']['id'] for r in records.values() if affected(r)),
        'new_request_prefix': 'strictretry', 'candidate_slots': 2,
        'maximum_additional_reservation_usd': maximum,
        'inherited_exposure_usd': provider.exposure,
        'cumulative_cap_usd': provider.budget.limit,
        'remaining_at_admission_usd': provider.budget.limit-provider.exposure,
        'old_reservations_released': False, 'new_allowance_usd': 0,
        'scope': 'environment-recovered acquisition; same strict semantics; one model draw retained for unaffected episodes; fresh draw for affected episodes; no pooling as independent repeats'
    }
    immutable(ROOT/'provenance/transport_recovery_freeze.json', value)
    print(json.dumps({k:value[k] for k in ('maximum_additional_reservation_usd','inherited_exposure_usd','remaining_at_admission_usd')}), flush=True)


def check():
    strict.check_freeze()
    definition=json.loads((ROOT/'provenance/transport_recovery_freeze.json').read_bytes())
    if strict.digest(Path(__file__).read_bytes()) != definition['code_sha256']:
        raise ValueError('RECOVERY_CODE_CHANGED')
    for name, expected in definition['original_episode_hashes'].items():
        if strict.digest((ROOT/'results/strict_state/episodes'/(name+'.json.gz')).read_bytes()) != expected:
            raise ValueError('ORIGINAL_CHANGED')
    return definition


def episode(provider, original):
    job=original['job']; path=DEST/'episodes'/(job['id']+'.json.gz')
    if path.exists(): return strict._load_gzip(path)
    if not affected(original):
        strict._save_gzip(path,original)
        return original
    attempts=[];selected=None
    for slot in range(2):
        if ABORT.is_set(): raise RuntimeError('RECOVERY_CIRCUIT_OPEN')
        attempt_path=DEST/'attempts'/(job['id']+'--slot'+str(slot)+'.json.gz')
        if attempt_path.exists():
            attempt=strict._load_gzip(attempt_path)
        else:
            started=time.perf_counter();prompt=strict.payload(job,attempts)
            seconds=time.perf_counter()-started
            request_id=job['id'].replace('strictstate--','strictretry--',1)+'--slot'+str(slot)
            request=request_job(job['model'],prompt,request_id)
            api=provider.call(request)
            api.update(request_id=request_id,prompt_preparation_seconds=seconds,prompt_state_checks=int(job['method']!='A'))
            parsed=api['parsed'];validation=strict.evaluate(parsed,job)
            attempt={'slot':slot,'api':api,'request_metadata':strict.request_metadata(request),'parsed':parsed,'program':parsed.get('program'),'feedback':validation['feedback'],'validation':validation}
            strict._save_gzip(attempt_path,attempt)
        if attempt['api']['raw_status']=='transport_error':
            ABORT.set()
            raise RuntimeError('FRESH_TRANSPORT_FAILURE_RETAINED_NO_AUTOMATIC_RETRY')
        attempts.append(attempt)
        if attempt['validation']['accepted']:
            selected=attempt['parsed'];break
    record={'job':job,'attempts':attempts,'selected':selected,'api_requests':len(attempts),
            'final':strict.evaluate(selected,job,'final') if selected else None,
            'scale':strict.evaluate(selected,job,'scale') if selected else None,
            'acquisition_recovery':{'original_id':job['id'],'reason':'transport_error','original_retained':True}}
    strict._save_gzip(path,record)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',action='store_true');parser.add_argument('--live',action='store_true')
    parser.add_argument('--workers',type=int,default=6);parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    if args.freeze:freeze();return
    check();records=originals();grid=[records[name] for name in sorted(records)]
    if args.limit:grid=grid[:args.limit]
    with strict._exclusive_runner(ROOT):
        provider=Provider(ROOT,live=args.live)
        # A warm-up actual request prevents dispatching a full grid into a blocked environment.
        first=next((r for r in grid if affected(r)),grid[0]);episode(provider,first)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(episode,provider,r):r['job']['id'] for r in grid}
            for count,future in enumerate(as_completed(futures),1):
                record=future.result()
                print(json.dumps({'done':count,'total':len(grid),'id':record['job']['id'],'accepted':record['selected'] is not None,'upper_spend':provider.exposure}),flush=True)


if __name__=='__main__':main()
