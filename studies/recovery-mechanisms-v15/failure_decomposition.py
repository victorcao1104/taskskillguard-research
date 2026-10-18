"""Separate explicit model stopping from execution/interface failures, no API."""
from collections import Counter,defaultdict
import gzip,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent


def main():
    output={}
    for name,folder,pattern in [('main','results/episodes','formal--*.json.gz'),('strict_recovered','results/strict_state_recovered/episodes','*.json.gz')]:
        groups=defaultdict(Counter);examples=[]
        for path in sorted((ROOT/folder).glob(pattern)):
            r=json.loads(gzip.decompress(path.read_bytes()));j=r['job'];a=r['attempts'][-1]
            ev=r['final'] or a['validation'];feasible=ev['records'][0]['score']['feasible']
            group='/'.join((j['campaign_kind'],j['model'],j['method']))
            row=groups[group];row['episodes']+=1
            if r['final'] and r['final']['accepted']:row['correct_outcome']+=1;continue
            row['failed_episodes']+=1
            if a['parsed']['status'] in ('stop','clarify'):
                row['model_declared_stop_on_feasible' if feasible else 'model_wrong_boundary_reason']+=1
            elif a['parsed']['status']=='invalid':row['model_or_api_protocol_failure']+=1
            else:
                row['candidate_execution_failure']+=1
                code=(ev['feedback'] or {}).get('code','MISSING_OBLIGATION')
                row['execution:'+code]+=1
                if code=='DUPLICATE_EFFECT':
                    op=ev['feedback'].get('operation','unspecified');row['duplicate_operation:'+op]+=1
                    examples.append({'id':j['id'],'method':j['method'],'model':j['model'],'feedback_code':code,'operation':op,'effects':a['parsed']['program']['effects'],'record':str(path.relative_to(ROOT)).replace('\\','/')})
        output[name]={'groups':{k:dict(v) for k,v in groups.items()},'duplicate_examples':examples}
    output['metric_note']='Legacy wrong_stop_feasible counts every feasible interpreter halt, including malformed code and rejected duplicates. It is not a count of explicit model refusals. These categories use the last attempted candidate when no result was accepted.'
    (ROOT/'reports/failure_decomposition.json').write_bytes((json.dumps(output,indent=2)+'\n').encode())
    print(json.dumps(output['strict_recovered']['groups']))


if __name__=='__main__':main()
