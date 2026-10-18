"""Strong task-specific compiler and simple source-deletion references, no API."""
import gzip,json
from pathlib import Path
from rm15.campaign import evaluate
from rm15.tasks import TEMPLATES,source,solver
from rm15.protocol import LEVELS
from rm15.recovery import transform_compute,snapshot
from rm15.tasks import instance
ROOT=Path(__file__).resolve().parent


def main():
    rows=[]
    for t in TEMPLATES:
        for method in ('specialist_compiler','stop','delete_only'):
            for level in LEVELS if method=='delete_only' else ('absent',):
                job={'template':t,'campaign_kind':'source','method':method,'source_level':level,'history':'fresh'}
                if method=='specialist_compiler':parsed={'status':'candidate','program':{'compute':solver(t),'effects':''}}
                elif method=='stop':parsed={'status':'stop','reason_code':'NONE'}
                else:
                    # Literal deletion removes only the forbidden read, leaving its dependent gate.
                    code='\n'.join(line for line in source(t,level).splitlines() if "read('/private/token')" not in line and 'read("/private/token")' not in line)
                    parsed={'status':'candidate','program':{'compute':code,'effects':''}}
                rows.append({'job':job,'program':parsed,**{phase:evaluate(parsed,job,phase) for phase in ('validation','final','scale')}})
    folder=ROOT/'results';folder.mkdir(exist_ok=True)
    path=folder/'strong_controls.json.gz'
    if path.exists():raise ValueError('CONTROL_RESULTS_ALREADY_EXIST')
    path.write_bytes(gzip.compress(json.dumps(rows,sort_keys=True).encode(),mtime=0))
    out={m:{'cases':sum(r['job']['method']==m for r in rows),'final':sum(r['job']['method']==m and r['final']['accepted'] for r in rows),'scale':sum(r['job']['method']==m and r['scale']['accepted'] for r in rows)} for m in ('specialist_compiler','stop','delete_only')}
    (ROOT/'reports/controls_summary.json').write_bytes((json.dumps(out,indent=2)+'\n').encode());print(json.dumps(out))

if __name__=='__main__':main()
