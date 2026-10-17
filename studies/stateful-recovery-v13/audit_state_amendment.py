"""Measure the history defect on every retained candidate, without API calls."""
from pathlib import Path
import json
from run import D
from sr13.io import read,save,semantic
from sr13.data import inputs_for
from sr13.verify import check,evaluate
from state_amendment import physical_history


def main():
    cases={c['case_id']:c for c in read(D/'data/cases.json')};rows=[];later_hashes=set()
    for campaign in ('offline','main'):
        for path in sorted((D/'results'/campaign).glob('*--*.json')):
            r=read(path);c=cases[r['case_id']]
            if not c.get('uncertain_delivery'):continue
            ins=inputs_for(c);attempts=r.get('attempts',[{'program':r.get('program'),'validation':r.get('validation')}])
            changed=[];decision_changed=[]
            for i,a in enumerate(attempts):
                if 'validation' not in a:continue
                old=check(a['program'],c,ins['validation'])
                with physical_history():new=check(a['program'],c,ins['validation'])
                if semantic(old)!=semantic(new):
                    changed.append({'iteration':i,'old':old,'corrected':new})
                    for later in attempts[i+1:]:
                        if later.get('request'):later_hashes.add(later['request']['hash'])
                if old['accepted']!=new['accepted']:decision_changed.append(i)
            old_final=evaluate(r['deployed_program'],c,ins['final']);old_final.pop('traces')
            with physical_history():new_final=evaluate(r['deployed_program'],c,ins['final'])
            new_final.pop('traces')
            rows.append({'path':path.relative_to(D).as_posix(),'changed_feedback':changed,
                         'changed_candidate_decisions':decision_changed,'changed_final_metrics':old_final!=new_final})
    result={'audited_episodes':len(rows),'feedback_changed_episodes':sum(bool(r['changed_feedback']) for r in rows),
            'feedback_changed_attempts':sum(len(r['changed_feedback']) for r in rows),
            'later_distinct_requests_after_changed_feedback':len(later_hashes),
            'changed_candidate_decisions':sum(len(r['changed_candidate_decisions']) for r in rows),
            'changed_fixed_program_final_metrics':sum(r['changed_final_metrics'] for r in rows),
            'records':rows,'interpretation':'Fixed-candidate invariance does not imply identical future model proposals. Whole unknown-receipt stratum is rerun.'}
    save(D/'analysis/state_amendment_audit.json',result);print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))


if __name__=='__main__':main()
