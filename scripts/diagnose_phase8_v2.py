"""Correct V1's no-gate sentinel; retain V1 artifacts and reproducibility."""
from collections import Counter
import json
from phase8_common import ROOT,read_rows,jb,rb,immutable
from diagnose_phase8 import main as original


def main():
    previous=original()
    rows=read_rows(ROOT/'results/phase8/diagnostics/gate_failures.jsonl')
    for r in rows:
        if r['site'] is None:
            r['F_authorization']=None
            r['cause_class']='original_path_failure_without_model_gate'
        elif not r['F_protocol_valid']:r['cause_class']='invalid_response_gate'
        elif r['F_authorization']==r['aggregate_truth']=='unknown' and r['world_truth']=='yes':
            r['cause_class']='cross_world_conservative_gate'
        else:r['cause_class']='prediction_or_execution_state_difference'
    summary={**previous,'scope':'post-outcome diagnostic V2; no model-gate event is null, not an invalid model response',
             'supersedes':'results/phase8/diagnostics/summary.json','details_by_model':{}}
    for model in ('gpt-4.1-mini','gpt-6-luna'):
        rs=[r for r in rows if r['model']==model]
        summary['details_by_model'][model]={'conditions':len(rs),'case_worlds':len({(r['case_id'],r['world_index']) for r in rs}),
            'causes':dict(Counter(r['cause_class'] for r in rs)),
            'categories':dict(Counter(str((r['F_authorization'],r['aggregate_truth'],r['world_truth'])) for r in rs))}
    out=ROOT/'results/phase8/diagnostics_v2'
    immutable(out/'gate_failures.jsonl',rb(rows));immutable(out/'summary.json',jb(summary))
    print(json.dumps(summary),flush=True);return summary


if __name__=='__main__':main()
