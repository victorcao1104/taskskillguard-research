"""Held-out larger-input audit; exact identical programs share physical replay only."""
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
from gr14.campaign import STUDY
from gr14.data import FAMILIES,make_case,inputs_for
from gr14.verify import evaluate
from gr14.provider import immutable

def one(family):
    out=STUDY/'results/stress';out.mkdir(parents=True,exist_ok=True);cache={};count=0
    for campaign in ('main','combined'):
        for path in sorted((STUDY/'results'/campaign).glob(f'{family}--*.json')):
            r=json.loads(path.read_text(encoding='utf-8'));name=campaign+'--'+path.stem;p=out/(name+'.json')
            evidence=out/(name+'.json.gz')
            if p.exists() and evidence.exists():
                prior=json.loads(p.read_text(encoding='utf-8'))
                full=json.loads(gzip.decompress(evidence.read_bytes()))
                if prior['final']!={k:v for k,v in full.items() if k!='records'}:
                    raise ValueError('STRESS_EVIDENCE_MISMATCH:'+name)
                continue
            c=make_case(r['family'],r['condition']);program=r.get('selected') or {'compute':'pass','effects':'pass'};state=r.get('state',False) if r.get('selected') else False;reuse=r.get('reuse',True)
            key=hashlib.sha256(json.dumps([c,program,state,reuse,'stress'],sort_keys=True).encode()).hexdigest()
            hit=key in cache
            if not hit:cache[key]=evaluate(program,c,inputs_for(c,'stress'),state=state,reuse=reuse)
            result=cache[key]
            summary={k:r[k] for k in ('campaign','case_id','family','condition','method','model','replicate','expected_status')}|{'final':{k:v for k,v in result.items() if k!='records'},'selected':r.get('selected'),'physical_replay_shared':hit,'replay_key':key}
            if p.exists():
                prior=json.loads(p.read_text(encoding='utf-8'))
                if prior['final']!=summary['final'] or prior['selected']!=summary['selected']:
                    raise ValueError('STRESS_RESUME_MISMATCH:'+name)
                summary=prior
            data=gzip.compress(json.dumps(result,sort_keys=True).encode(),mtime=0)
            temporary=evidence.with_suffix('.gz.pending');temporary.write_bytes(data);temporary.replace(evidence)
            immutable(p,summary);count+=1
    return {'family':family,'new_rows':count,'unique_evaluations':len(cache)}

if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=3) as pool:
        for f in as_completed([pool.submit(one,fam) for fam in FAMILIES]):print(json.dumps(f.result()),flush=True)
