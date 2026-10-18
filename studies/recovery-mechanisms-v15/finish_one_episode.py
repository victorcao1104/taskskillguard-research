"""Finish only the one interrupted episode; never launch a batch runner."""
import argparse
import json
from pathlib import Path
from rm15.provider import Provider, request_job
from runtime_error_adapter import install
import strict_state
import transport_recovery as recovery

TARGET='strictstate--state--aggregation.interval_union--fixed--confirmed--B--gpt-6-luna'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');args=parser.parse_args()
    install();recovery.check();records=recovery.originals()
    complete={p.stem.removesuffix('.json') for p in (recovery.DEST/'episodes').glob('*.json.gz')}
    missing=set(records)-complete
    if not missing:print('All 512 episodes already saved; no API calls.');return
    if missing!={TARGET}:raise ValueError('UNEXPECTED_MISSING_SET')
    request=request_job(records[TARGET]['job']['model'],strict_state.payload(records[TARGET]['job'],[]),TARGET.replace('strictstate--','strictretry--',1)+'--slot0')
    raw_path=recovery.ROOT/'api/raw'/(request['expected_request_hash']+'.json')
    raw=json.loads(raw_path.read_bytes())
    if raw['status']!='completed':raise ValueError('FIRST_RESPONSE_NOT_ALREADY_SAVED')
    print(json.dumps({'completed_retained':len(complete),'only_target':TARGET,'first_answer_already_cached':True,'maximum_new_requests':1,'maximum_new_reservation_usd':0.004}),flush=True)
    if not args.live:return
    with strict_state._exclusive_runner(recovery.ROOT):
        provider=Provider(recovery.ROOT,live=True)
        if provider.exposure+0.004>provider.budget.limit:raise ValueError('BUDGET')
        result=recovery.episode(provider,records[TARGET])
        print(json.dumps({'saved':TARGET,'accepted':result['selected'] is not None,'upper_exposure':provider.exposure}),flush=True)


if __name__=='__main__':main()
