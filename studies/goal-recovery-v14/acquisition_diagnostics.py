"""Separate provider and protocol failures from candidate execution outcomes."""
import json
from collections import Counter
from gr14.campaign import STUDY
from gr14.provider import immutable

out={}
for campaign in ('development','main','combined'):
    counts=Counter();normalization=Counter();incidents=[]
    for path in sorted((STUDY/'results'/campaign).glob('*.json')):
        row=json.loads(path.read_text(encoding='utf-8'))
        for attempt in row['attempts']:
            response=attempt.get('response')
            if not response:continue
            status=response['raw_status'];counts[status]+=1;normalization[response.get('normalization') or 'none']+=1
            if status!='completed':
                raw=json.loads((STUDY/'api/raw'/f"{response['request_hash']}.json").read_text(encoding='utf-8'))
                incidents.append({k:row[k] for k in ('case_id','method','model','replicate')}|{'request_hash':response['request_hash'],'raw_status':status,
                    'http_status':raw.get('http_status'),'error_type':raw.get('error_type'),'error_code':raw.get('error_code'),
                    'episode_safe_complete':row['final']['safe_complete'],'feedback':attempt.get('feedback')})
    out[campaign]={'raw_statuses':dict(counts),'normalization':dict(normalization),'incidents':incidents}
out['interpretation']='Provider errors are retained in acquired completion rates. They do not by themselves establish that a generated program failed. No selective replacement requests were made.'
immutable(STUDY/'reports/acquisition_diagnostics.json',out)
print(json.dumps({k:v['raw_statuses'] for k,v in out.items() if isinstance(v,dict)},indent=2))
