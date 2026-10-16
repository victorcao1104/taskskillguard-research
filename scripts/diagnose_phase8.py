"""Post-outcome attribution of gate-related completion differences, no tuning."""
from collections import Counter
import json
from phase8_common import ROOT,read_rows,jb,rb,immutable


def main():
    truth={r['case_id']:r for r in read_rows(ROOT/'results/phase8/semantics/truth.jsonl')}
    obs={(r['case_id'],r['model'],r['view']):r for r in read_rows(ROOT/'results/phase8/api/observations.jsonl') if r['replicate']==0}
    rows=read_rows(ROOT/'results/phase8/integrated/vm_results.jsonl')
    key=lambda r:(r['case_id'],r['world_index'],r['fault'],r['policy'])
    index={(key(r),r['pipeline']):r for r in rows if r['split']=='heldout'}
    details=[];blocks=[]
    for k in sorted({k for k,p in index}):
        allow=index[(k,'all_allow')];block=index[(k,'all_block')]
        if block['result']['authorized_goal'] and not allow['result']['authorized_goal']:
            blocks.append({'case_id':k[0],'world_index':k[1],'fault':k[2],'policy':k[3],
                'allow_failure':allow['result']['failure_reason'],
                'allow_attempts':allow['result']['attempt_log'],'block_attempts':block['result']['attempt_log'],
                'allow_committed_effects':[e for e in allow['result']['trace'] if e['committed']]})
        for model in ('gpt-4.1-mini','gpt-6-luna'):
            d=index[(k,model+':D')];f=index[(k,model+':F')]
            if d['result']['authorized_goal'] and not f['result']['authorized_goal']:
                event=next((e for e in f['result']['trace'] if e['status']=='model_gate'),None)
                pred=obs[(k[0],model,'F')]['parsed'];sid=event['id'] if event else None
                t=next((s for s in truth[k[0]]['labels'] if s['id']==sid),{})
                w=next((s for s in truth[k[0]]['worlds'][k[1]]['labels'] if s['id']==sid),{})
                details.append({'case_id':k[0],'family':f['family'],'world_index':k[1],'fault':k[2],'policy':k[3],
                    'model':model,'site':sid,'F_authorization':pred['by_id'].get(sid,{}).get('authorization','invalid'),
                    'aggregate_truth':t.get('authorization'),'world_truth':w.get('authorization'),
                    'F_failure':f['result']['failure_reason'],'F_protocol_valid':pred['protocol_valid']})
    summary={'scope':'post-outcome diagnostic only; no policy/prompt changes or model reruns',
             'D_success_F_failure_conditions':len(details),'details_by_model':{},
             'all_block_wins_conditions':len(blocks),'all_block_wins_families':dict(Counter(truth[r['case_id']]['family'] for r in blocks))}
    for model in ('gpt-4.1-mini','gpt-6-luna'):
        rs=[r for r in details if r['model']==model]
        summary['details_by_model'][model]={'conditions':len(rs),'case_worlds':len({(r['case_id'],r['world_index']) for r in rs}),
            'categories':dict(Counter(str((r['F_authorization'],r['aggregate_truth'],r['world_truth'])) for r in rs))}
    out=ROOT/'results/phase8/diagnostics'
    immutable(out/'gate_failures.jsonl',rb(details));immutable(out/'all_block_wins.jsonl',rb(blocks));immutable(out/'summary.json',jb(summary))
    print(json.dumps(summary),flush=True)
    return summary


if __name__=='__main__':main()
