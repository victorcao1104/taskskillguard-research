"""Actually re-execute every saved strict-state candidate, without an API client."""
import gzip,json
from pathlib import Path
from strict_state import evaluate,check_freeze,jobs
from verify_replay import signature
ROOT=Path(__file__).resolve().parent

def main():
    from runtime_error_adapter import install
    install()
    from transport_recovery import check as check_recovery
    check_freeze();check_recovery();paths={p.stem.removesuffix('.json'):p for p in (ROOT/'results/strict_state_recovered/episodes').glob('*.json.gz')}
    if set(paths)!={j['id'] for j in jobs()}:raise ValueError('INCOMPLETE_STRICT_GRID')
    worlds=0;invocations=0;accepted_no_cache_without_compute=0
    for index,(name,path) in enumerate(sorted(paths.items()),1):
        saved=json.loads(gzip.decompress(path.read_bytes()))
        for a in saved['attempts']:
            fresh=evaluate(a['parsed'],saved['job'])
            if signature(fresh)!=signature(a['validation']):raise ValueError('STRICT_VALIDATION_MISMATCH:'+name)
            worlds+=len(fresh['records'])
        if saved['selected']:
            for phase in ('final','scale'):
                fresh=evaluate(saved['selected'],saved['job'],phase)
                if signature(fresh)!=signature(saved[phase]):raise ValueError('STRICT_FINAL_MISMATCH:'+name)
                worlds+=len(fresh['records'])
                for record in fresh['records']:
                    invocations+=record['cost'].get('compute_invocations',0)
                    if saved['job']['history']=='invalid_cache' and record['score']['safe_complete'] and record['cost'].get('compute_invocations',0)==0:accepted_no_cache_without_compute+=1
        if index%100==0:print(json.dumps({'replayed':index,'worlds':worlds}),flush=True)
    if accepted_no_cache_without_compute:raise ValueError('STRICT_CONTRACT_BYPASS')
    report={'episodes':len(paths),'world_replays':worlds,'network_requests':0,'frozen_code_verified':True,'accepted_no_cache_without_compute':accepted_no_cache_without_compute,'selected_program_final_and_scale_compute_invocations':invocations}
    (ROOT/'reports/strict_replay_verification.json').write_bytes((json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report))

if __name__=='__main__':main()
