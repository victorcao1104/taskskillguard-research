"""Offline first-observation extraction evaluation and blinded review handoff."""
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.extraction_v4 import extract_graph_v4
from tsg.extraction_v5 import extract_graph_v5
from tsg.evidence_v4 import select_graph
from prepare_phase4 import immutable, json_bytes, rows_bytes, sha
from evaluate_extraction_phase4 import compare

def rows(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s]

def extraction():
    source_files=['src/tsg/extraction_v5.py','src/tsg/shell_v5.py','scripts/prepare_phase5.py',
                  'scripts/evaluate_extraction_phase4.py']
    freeze={p:sha((ROOT/p).read_bytes()) for p in source_files}
    immutable(ROOT/'results/phase5/extraction_primary/source_freeze.json',json_bytes(freeze))
    observations=[]
    for generation,count in [('phase5',48),('phase4',50)]:
        fixtures=[f for p in sorted((ROOT/f'data/{generation}').glob('fixtures_*.jsonl')) for f in rows(p)]
        if len(fixtures)!=count: raise ValueError('FIXTURE_COUNT_MISMATCH')
        for f in fixtures:
            for version,extractor in [('v4',extract_graph_v4),('v5',extract_graph_v5)]:
                graph=extractor(f['id'],f['files'])
                observations.append({**compare(f,graph),'extractor':version,'generation':generation})
                immutable(ROOT/f'results/phase5/extraction_primary/graphs/{generation}/{version}/{f["id"]}.json',json_bytes(graph))
    groups=[]
    for generation in ('phase4','phase5'):
        for version in ('v4','v5'):
            for split in ('all','dev','validation','heldout'):
                subset=[r for r in observations if r['generation']==generation and r['extractor']==version and (split=='all' or r['split']==split)]
                m=dict(sum((Counter(r['metrics']) for r in subset),Counter()))
                # Counter omits zeros; retain a consistent metric schema.
                for key in subset[0]['metrics']: m.setdefault(key,0)
                groups.append({'generation':generation,'extractor':version,'split':split,'fixtures':len(subset),
                    'families':len({r['family'] for r in subset}),**m,
                    'precision':m['matched']/m['actual'] if m['actual'] else None,
                    'recall':m['matched']/m['expected'] if m['expected'] else None})
    summary={'groups':groups,'source_freeze':freeze,
             'claim':'New family first observations separate from old fixture regression; supported recall never substitutes total recall.',
             'metric':'Maximum source-span/operation matching, resource errors and unknown omissions separate; inherited immutable scorer',
             'holdout_tuning':False,'real_human_accuracy':None}
    immutable(ROOT/'results/phase5/extraction_primary/observations.jsonl',rows_bytes(observations))
    immutable(ROOT/'results/phase5/extraction_primary/summary.json',json_bytes(summary))
    print(json.dumps(groups),flush=True)

def real_and_packet():
    source=rows(ROOT/'data/phase3/real_prepared.jsonl')
    if len(source)!=180: raise ValueError('REAL_DENOMINATOR_MISMATCH')
    sources=[]; packet=[]; strata=[]; prepared=[]
    for p in source:
        graph=extract_graph_v5(p['skill_id'],p['files'])
        bounded,actions,selection=select_graph(graph)
        immutable(ROOT/f'results/phase5/real/graphs/{p["skill_id"]}.json',json_bytes(graph))
        sources.append({k:p[k] for k in ('skill_id','source_native_id','family_id','files','provenance','coverage') if k in p})
        prepared.append({**{k:p[k] for k in ('skill_id','source_native_id','family_id','split')},
                         'files':p['files'],'actions':actions,'graph':bounded,'coverage':selection,
                         'source_coverage':p['coverage'],'original_provenance':p['provenance']})
        selected=[]
        for action in actions:
            selected.append(('candidate',action['provenance']))
        # Four deterministic unknown-reason strata per bundle, one source span
        # each, plus a zero-candidate overview and every explicit truncated file.
        uncertainties={}
        for u in graph['unresolved']:
            file=u.get('file')
            if file not in p['files'] or not p['files'][file].splitlines(): continue
            first=u.get('line_start',1); last=u.get('line_end',first)
            span={'file':file,'line_start':max(1,first),'line_end':min(len(p['files'][file].splitlines()),max(first,last))}
            key=u['reason']
            if span['line_start']<=span['line_end']:
                uncertainties.setdefault(key,[]).append(span)
        reasons=sorted(uncertainties,key=lambda k:sha((p['skill_id']+k).encode()))[:4]
        for reason in reasons:
            span=min(uncertainties[reason],key=lambda s:sha(json_bytes(s)))
            selected.append(('unsupported:'+reason,span))
        if not actions:
            for file,text in sorted(p['files'].items()):
                if text.splitlines():
                    selected.append(('zero_candidate',{'file':file,'line_start':1,'line_end':min(40,len(text.splitlines()))})); break
        for file,text in sorted(p['files'].items()):
            lines=text.splitlines()
            if lines and any('TRUNCAT' in line.upper() for line in lines[-3:]):
                selected.append(('truncated_tail',{'file':file,'line_start':max(1,len(lines)-15),'line_end':len(lines)}))
        for index,(stratum,span) in enumerate(selected):
            rid='review_'+sha((p['skill_id']+str(index)+stratum).encode())[:18]
            packet.append({'review_id':rid,'skill_id':p['skill_id'],'source_ref':'sources.jsonl',
                           'source_sha256':graph['source_sha256'],'provenance':span,'labels':{},'notes':'',
                           'status':'pending_independent_human_review'})
            strata.append({'review_id':rid,'stratum':stratum,'skill_id':p['skill_id'],'source_native_id':p['source_native_id']})
    out=ROOT/'data/phase5/human_review'
    for name,data in [('sources.jsonl',sources),('rater_A.jsonl',packet),('rater_B.jsonl',packet),('selection_manifest.jsonl',strata)]:
        immutable(out/name,rows_bytes(data))
    immutable(ROOT/'data/phase5/real_prepared.jsonl',rows_bytes(prepared))
    summary={'skills':180,'all_candidates':sum(sum(n['privilege_relevant'] for n in rows_graph['nodes']) for rows_graph in
                (json.loads((ROOT/f'results/phase5/real/graphs/{p["skill_id"]}.json').read_text(encoding='utf-8')) for p in prepared)),
             'selected_candidates':sum(len(p['actions']) for p in prepared),'zero_selected':sum(not p['actions'] for p in prepared),
             'review_items_per_rater':len(packet),'review_strata':dict(Counter(r['stratum'] for r in strata)),
             'human_labels':0,'accuracy':None,'source_sha256':sha((ROOT/'data/phase3/real_prepared.jsonl').read_bytes())}
    immutable(ROOT/'results/phase5/real/summary.json',json_bytes(summary)); print(json.dumps(summary),flush=True)

if __name__=='__main__':
    extraction()
    real_and_packet()
