"""Post-freeze coverage amendment: compare candidate content by unique site ID.

V1's failed ordering-sensitive audit remains byte-identical and reproducible.
No data, semantic, model prompt, recovery policy or acquisition job is changed.
"""
import contextlib
import io
import json
import sys
from phase7_common import ROOT,cases,read_rows,jb,rb,immutable,verify_freeze
sys.path.insert(0,str(ROOT/'src'))

def semantics():
    import experiment_phase7 as original
    verify_freeze()
    # Reproduce all first observations, including the recorded ordering failure.
    output=io.StringIO()
    try:
        with contextlib.redirect_stdout(output): original.semantics()
    except ValueError as exc:
        if str(exc)!='SEMANTIC_VALIDATION_FAILED':raise
    first=json.loads((ROOT/'results/phase7/semantics/summary.json').read_text())
    from tsg.runtime_v6 import parse_source,candidates
    from tsg.truth_v6 import static_sites
    rows=[]
    for c in cases():
        ast=parse_source(c['source']);a=candidates(ast);b=static_sites(c['program'])
        amap={s['id']:s for s in a};bmap={s['id']:s for s in b}
        rows.append({'case_id':c['case_id'],'source_ast_equal':ast==c['program'],
                     'content_by_id_equal':amap==bmap,'production_unique':len(amap)==len(a),
                     'reference_unique':len(bmap)==len(b),'order_equal':a==b,
                     'production_order':[s['id'] for s in a],'reference_order':[s['id'] for s in b]})
    corrected=all(r['source_ast_equal'] and r['content_by_id_equal'] and r['production_unique'] and r['reference_unique'] for r in rows)
    summary={**first,'all_source_coverage':corrected,'order_only_differences':sum(not r['order_equal'] for r in rows),
             'amendment':'compare full candidate dictionaries keyed by unique site ID; preserve original order audit',
             'original_summary':'results/phase7/semantics/summary.json'}
    immutable(ROOT/'results/phase7/semantics/coverage_v2.jsonl',rb(rows))
    immutable(ROOT/'results/phase7/semantics/summary_v2.json',jb(summary))
    if not corrected or first['equal']!=first['comparisons'] or not all(first[k] for k in ('all_typed_equal','all_collapsed_equal','all_evidence_equal')):
        raise ValueError('V2_SEMANTIC_VALIDATION_FAILED')
    print(json.dumps(summary),flush=True)
    return summary

if __name__=='__main__':semantics()
