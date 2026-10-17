"""Post-hoc, zero-API new-input stress of all accepted normalized main programs."""
from sr13.io import read,save,save_trial
from sr13.data import make_inputs
from sr13.verify import evaluate
from sr13.engine import start_meter
from run import D
from state_amendment import physical_history
from pathlib import Path
import argparse


def run(output=None):
    output=Path(output) if output else D/'results/stress_inputs'
    cases={c['case_id']:c for c in read(D/'data/cases.json')};rows=[]
    paths=sorted((D/'results/robust_protocol').glob('*--*.json'))
    if len(paths)!=1152:raise ValueError('NORMALIZED_MAIN_INCOMPLETE')
    with physical_history():
        for path in paths:
            r=read(path)
            if not r['accepted']:continue
            out=output/path.name
            if out.exists():record=read(out)
            else:
                c=cases[r['case_id']];meter=start_meter()
                result=evaluate(r['deployed_program'],c,[make_inputs(c,s) for s in range(2001,2065)])
                record={'case_id':c['case_id'],'method':r['method'],'model':r['model'],'replicate':r['replicate'],
                        'primary_safe':r['evaluation']['safe_complete'],'evaluation':result,'cost':dict(meter)}
                save_trial(out,record)
            rows.append({k:record[k] for k in ('case_id','method','model','replicate','primary_safe','evaluation','cost')})
    save(output/'summary.json',{'seeds':[2001,2064],'accepted_programs':len(rows),'records':rows,
        'interpretation':'Post-hoc 64 additional input seeds after eight-seed failures were observed. No method tuning, no new independent task families.'})
    print({'accepted_programs':len(rows),'primary_safe_but_stress_failed':sum(r['primary_safe'] and not r['evaluation']['safe_complete'] for r in rows)})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args()
    run(a.output)
