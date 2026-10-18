"""Replay saved candidates locally, never issue model requests or rewrite results."""
import gzip,hashlib,json
from pathlib import Path
from rm15.campaign import evaluate,check_freeze,jobs
from rm15.provider import CAP
ROOT=Path(__file__).resolve().parent


def signature(result):
    if result is None:return None
    return {k:result[k] for k in ('accepted','safe_complete','correct_stop')}|{'records':[{'score':r['score'],'stop':r['stop'],'seed':r['seed'],'secret':r['secret'],'committed':r['committed'],'trace':r['trace'],'events':r['events'],'steps':r['cost'].get('steps',0)} for r in result['records']]}


def main():
    check_freeze();expected={j['id'] for j in jobs()};paths={p.stem.removesuffix('.json'):p for p in (ROOT/'results/episodes').glob('formal--*.json.gz')}
    if set(paths)!=expected:raise ValueError('INCOMPLETE_GRID')
    checked=0;worlds=0
    for name,path in sorted(paths.items()):
        saved=json.loads(gzip.decompress(path.read_bytes()));job=saved['job']
        for a in saved['attempts']:
            fresh=evaluate(a['parsed'],job,early=True)
            if signature(fresh)!=signature(a['validation']):raise ValueError('VALIDATION_REPLAY_MISMATCH:'+name)
            worlds+=len(fresh['records'])
        if saved['selected']:
            for phase in ('final','scale'):
                fresh=evaluate(saved['selected'],job,phase)
                if signature(fresh)!=signature(saved[phase]):raise ValueError('FINAL_REPLAY_MISMATCH:'+name+':'+phase)
                worlds+=len(fresh['records'])
        checked+=1
        if checked%100==0:print(json.dumps({'replayed':checked,'worlds':worlds}),flush=True)
    old=ROOT.parent/'goal-recovery-v14/api/budget.jsonl';data=(ROOT/'api/budget.jsonl').read_bytes()
    if not data.startswith(old.read_bytes()):raise ValueError('LEDGER_PREFIX_CHANGED')
    latest={r['reservation_id']:r for r in map(json.loads,data.decode().splitlines())};exposure=sum(r.get('cost_usd',r['reserved_usd']) for r in latest.values())
    if exposure>CAP:raise ValueError('BUDGET_EXCEEDED')
    report={'episodes':checked,'world_replays':worlds,'network_requests':0,'frozen_code_verified':True,'old_ledger_prefix_preserved':True,'cumulative_upper_usd':exposure,'cap_usd':CAP,'remaining_upper_usd':CAP-exposure,'ledger_sha256':hashlib.sha256(data).hexdigest()}
    (ROOT/'reports/replay_verification.json').write_bytes((json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report))

if __name__=='__main__':main()
