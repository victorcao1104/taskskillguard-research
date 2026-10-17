"""Entire adaptive grid rerun after uniform sandbox transport failure.

Original 96 failures and reservations remain. Only the campaign identity/output
change; source, prompts, normalizer, grants and verifier are untouched.
"""
from pathlib import Path
import argparse
import robust_run
from robust_protocol import NormalizedProvider
from sr13.io import read,save,digest
from run import D,budget


class NetworkRerunProvider(NormalizedProvider):
    def propose(self,*args,**kwargs):
        assert kwargs['campaign']=='robust_adaptive'
        kwargs['campaign']='robust_adaptive_network_rerun'
        return super().propose(*args,**kwargs)


def run(env_file=None,*,cached=False,output=None):
    frozen=read(D/'provenance/adaptive_network_rerun.json')
    assert frozen['source_sha256']==digest(Path(__file__).read_bytes())
    old=robust_run.NormalizedProvider;robust_run.NormalizedProvider=NetworkRerunProvider
    try:
        robust_run.run(env_file,cached=cached,output=output or D/'results/robust_adaptive_network',adaptive=True)
    finally:robust_run.NormalizedProvider=old


def freeze():
    paths=list((D/'results/robust_adaptive').glob('*--*.json'));assert len(paths)==96
    hashes=[]
    for p in paths:
        r=read(p);assert not r['accepted']
        requests=[a['request']['hash'] for a in r['attempts'] if a.get('request')];assert len(requests)==1
        raw=read(D/'api/raw'/f'{requests[0]}.json');assert raw['status']=='transport_error' and raw['error_type']=='URLError'
        hashes+=requests
    b,a=budget();assert b.total_cost+1.69092<=b.limit
    save(D/'provenance/adaptive_network_rerun.json',{'source_sha256':digest(Path(__file__).read_bytes()),
         'reason':'All 96 original normalized adaptive episodes have one URLError transport failure; no model answer. Started in network-restricted default sandbox. Rerun entire grid with outbound permission.',
         'old_failed_request_hashes':sorted(hashes),'episodes':96,'old_evidence_preserved':True,
         'new_exposure_at_freeze':b.total_cost-a['inherited_upper_usd'],'worst_rerun_bound_usd':1.69092,
         'change':'Only unique request campaign and output directory; frozen methods/prompts/checker unchanged.'})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','run']);p.add_argument('--env-file',type=Path)
    p.add_argument('--cached',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    if a.command=='freeze':freeze()
    else:run(a.env_file,cached=a.cached,output=a.output)
