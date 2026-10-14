import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from tsg.benchmark import build_cases
from tsg.graph import extract_graph, read_bundle

root=Path(__file__).resolve().parents[1]
dest=root/'data/benchmark';dest.mkdir(parents=True,exist_ok=True)
cases=build_cases()
(dest/'synthetic_cases.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cases),encoding='utf-8')
graphs=root/'data/graphs';graphs.mkdir(parents=True,exist_ok=True)
rows=[json.loads(s) for s in (root/'data/manifests/skills_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
for i,row in enumerate(rows):
    files,coverage=read_bundle(row)
    graph=extract_graph(row['skill_id'],files)
    graph.update(coverage=coverage,source_native_id=row['source_native_id'],split=row['split'],family_id=row['family_id'])
    (graphs/(row['skill_id']+'.json')).write_text(json.dumps(graph,indent=2,ensure_ascii=False),encoding='utf-8')
    if (i+1)%30==0:print('static_graphs',i+1,flush=True)
print(json.dumps({'synthetic_cases':len(cases),'template_families':6,'static_real_graphs':len(rows)}))
