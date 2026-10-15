"""Post-outcome descriptive evidence error taxonomy; no rescoring or repair."""
from collections import Counter
import json
import sys
from phase7_common import ROOT,cases,read_rows,sha,jb,rb,immutable
sys.path.insert(0,str(ROOT/'src'))
from tsg.evidence_v7 import solve,labels_from_worlds,AXES

def main():
    cs={c['case_id']:c for c in cases()};obs=read_rows(ROOT/'results/phase7/api/observations.jsonl')
    rows=[];counts=Counter();inconsistent=0;valid=0
    for r in obs:
        if r['view']!='B2' or r['replicate']!=0:continue
        if not r['parsed']['protocol_valid']:continue
        valid+=1;c=cs[r['case_id']];gold={g['id']:g for g in solve(c)['judgments']}
        legal_sets={};bad_global=False
        for sid,p in r['parsed']['by_id'].items():
            g=gold[sid];pw=p['worlds'];gw=g['worlds'];counts['candidates']+=1
            own=labels_from_worlds(pw,c['catalog_closed']) if pw else {}
            label_bad=[a for a in AXES if own.get(a)!=p[a]]
            counts['candidate_label_evidence_inconsistent']+=bool(label_bad)
            mismatch=[]
            if len(pw)!=len(gw):counts['world_count_mismatch']+=1
            for x,y in zip(pw,gw):
                counts['candidate_world_pairs']+=1
                fields=[k for k in y if x.get(k)!=y[k]]
                counts.update(fields)
                for k in ('legal_routes','avoiding_routes'):
                    if k in fields and sorted(x[k])==y[k]:counts[k+'_order_only']+=1
                mismatch.append({'world':y['world'],'fields':fields})
                key=x['world'];signature=tuple(x['legal_routes'])
                if key in legal_sets and legal_sets[key]!=signature:bad_global=True
                legal_sets[key]=signature
            rows.append({'job_id':r['job_id'],'model':r['model'],'split':r['split'],'id':sid,
                         'label_evidence_inconsistent_axes':label_bad,'world_errors':mismatch})
        inconsistent+=bad_global
    summary={'scope':'post-outcome descriptive, no changed answers or primary scoring',
             'valid_main_B2_conditions':valid,'conditions_with_inconsistent_legal_routes_across_candidates':inconsistent,
             'counts':dict(counts),'observations_sha256':sha(rb(obs))}
    immutable(ROOT/'results/phase7/analysis/evidence_diagnostics.json',jb(summary))
    immutable(ROOT/'results/phase7/analysis/evidence_diagnostics.jsonl',rb(rows))
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
