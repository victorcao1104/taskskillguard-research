"""Remove duplicated trace arrays from summaries; preserve full gzip evidence."""
import gzip
import json
from pathlib import Path
from gr14.campaign import STUDY

def strip_records(obj):
    if isinstance(obj,dict):return {k:strip_records(v) for k,v in obj.items() if k!='records'}
    if isinstance(obj,list):return [strip_records(v) for v in obj]
    return obj

def main():
    before=after=changed=0
    for folder in ('controls','combined_controls'):
        for p in (STUDY/'results'/folder).glob('*.json'):
            raw=p.read_bytes();summary=json.loads(raw);evidence=json.loads(gzip.decompress(p.with_suffix('.json.gz').read_bytes()))
            for k in ('other_phases','stress'):
                if k in summary and strip_records(summary[k])!=strip_records(evidence[k]):raise ValueError('SUMMARY_EVIDENCE_MISMATCH')
            compact=strip_records(summary);data=(json.dumps(compact,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
            before+=len(raw);after+=len(data)
            if data!=raw:
                tmp=p.with_suffix('.compact.tmp');tmp.write_bytes(data);tmp.replace(p);changed+=1
    print(json.dumps({'summaries_compacted':changed,'bytes_before':before,'bytes_after':after,'full_gzip_evidence_unchanged':True}))
if __name__=='__main__':main()
