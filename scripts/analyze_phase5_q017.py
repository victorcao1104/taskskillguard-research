"""Publish separate clarified-spec observations; no merger into primary scores."""
import json
from pathlib import Path
import os
from run_phase5 import ROOT,read_rows
from tsg.reasoning_v5 import project_edges
from analyze_phase5 import analyze_inputs,publish_package
from prepare_phase4 import sha

def main():
    import tiktoken
    os.environ.setdefault('TIKTOKEN_CACHE_DIR',str(ROOT/'work/tiktoken'))
    enc=tiktoken.get_encoding('o200k_base')
    base=ROOT/'results/phase5_q017'
    jobs=read_rows(base/'acquisition/jobs.jsonl'); observations=read_rows(base/'api/observations.jsonl')
    case,=read_rows(ROOT/'data/phase5/reasoning_q017_clarified.jsonl')
    graph=json.loads((base/'acquisition/graph.json').read_text(encoding='utf-8'))
    auto=project_edges(graph,case['public']['canonical_nodes'])
    oracle=case['private']['oracle_edges']
    triple=lambda es:{(e['source'],e['target'],e['type']) for e in es}
    a,o=triple(auto),triple(oracle)
    edge={'case_id':case['case_id'],'family':case['family'],'split':case['split'],'auto_edges':auto,'oracle_edges':oracle,
          'true_positive':len(a&o),'extra':len(a-o),'missed':len(o-a),'auto_count':len(a),'oracle_count':len(o)}
    controls=[]
    for context in ('allow','deny','missing'):
        js=[j for j in jobs if j['context']==context and j['model']=='gpt-4.1-mini']
        controls.append({'case_id':case['case_id'],'context':context,'base_equal':True,
                         'local_tokens':{j['view']:len(enc.encode(j['prompt'])) for j in js}})
    package=analyze_inputs(jobs,observations,[case],[edge],controls,{case['case_id']:graph},expected_jobs=None)
    package['summary.json']['followup_interpretation']={
        'single_family_only':True,'intervals_not_population_inference':True,'primary_replacement':False,
        'reason':'Source-specification ambiguity corrected, not a retry of failed outcomes.',
        'source_sha256':sha((ROOT/'data/phase5/reasoning_q017_clarified.jsonl').read_bytes())}
    publish_package(base/'analysis',package)
    print(json.dumps({'planned':len(jobs),'protocol':package['summary.json']['main_protocol']['overall']}))

if __name__=='__main__': main()
