"""Post-hoc explanation of accepted programs failing held-out inputs; no repair."""
import gzip
import itertools
import json
from pathlib import Path
from gr14.campaign import STUDY
from gr14.data import make_case
from gr14.goals import truth
from gr14.provider import immutable

def main():
    findings=[]
    for campaign in ('main','combined'):
        for p in sorted((STUDY/'results'/campaign).glob('*.json')):
            r=json.loads(p.read_text(encoding='utf-8'))
            if r['selected'] is None or r['final']['safe_complete']:continue
            full=json.loads(gzip.decompress(p.with_suffix('.json.gz').read_bytes()))
            bad=[x for x in full['final']['records'] if not x['score']['safe_complete']]
            case=make_case(r['family'],r['condition']);goal=case['task']['goal']
            ce=r['final']['counterexample'];rows=ce['input']['rows'];counts={}
            for name,extra in [('trusted_goal',{}),('extra_dependencies',{'closed_dependencies':True}),('extra_dependencies_and_conflicts',{'closed_dependencies':True,'no_conflicts':True})]:
                n=0
                for size in range(goal['min_count'],goal['max_count']+1):
                    for subset in itertools.combinations(rows,size):
                        ordered=sorted(subset,key=lambda x:tuple(x[k] for k in goal['order_by'])) if goal['order_by'] else subset
                        n+=truth([x['id'] for x in ordered],rows,goal|extra)['valid']
                counts[name]=n
            findings.append({'campaign':campaign,'file':str(p.relative_to(STUDY)).replace('\\','/'),'case_id':r['case_id'],'method':r['method'],'model':r['model'],'replicate':r['replicate'],
                'trusted_goal':goal,'selected':r['selected'],'stop_codes':r['final']['stop_codes'],'bad_worlds':len(bad),'total_worlds':r['final']['world_runs'],
                'bad_seeds':sorted({x['input_seed'] for x in bad}),'reused_on_failure':[x['reused'] for x in bad],
                'counterexample_solution_counts':counts,'counterexample':ce,
                'interpretation':'Solution counts diagnose unnecessary constraints visible in candidate text; they are post-hoc evidence, not a new treatment or causal rerun.'})
    immutable(STUDY/'reports/accepted_failure_analysis.json',{'episodes':findings,'count':len(findings)})
    print(json.dumps([{k:x[k] for k in ('campaign','case_id','method','replicate','stop_codes','counterexample_solution_counts')} for x in findings],indent=2))

if __name__=='__main__':main()
