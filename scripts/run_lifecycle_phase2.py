"""Complete task workflows isolate expiry, quota, and monotone revocation."""
import copy
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.benchmark import build_cases
from tsg.policy import Policy,Guard,Ledger
from tsg.sandbox import run_case


class LifecycleGuard:
    def __init__(self,policy,settings,shrink):
        self.policy=policy;self.inner=Guard(policy,taint=True,lease=settings['lease'])
        self.ledger=Ledger(policy);self.shrink=shrink;self.updated=False
    def check(self,op,resource,step,value=None):
        if self.shrink and not self.updated and step>=3:
            narrowed=Policy(tuple(r for r in self.policy.rules if r.operation!='file.read'))
            self.ledger.update(narrowed,evidence_source='trusted_runtime',approved=False)
            self.policy=self.ledger.effective;self.inner.policy=self.policy;self.updated=True
        return self.inner.check(op,resource,step,value)


def main():
    rows=[]
    for base in [c for c in build_cases() if c['scenario']=='post_task_reuse']:
        for target in ('expiry_only','quota_only'):
            case=copy.deepcopy(base)
            for rule in case['policy']['rules']:
                if rule['operation']=='file.read':
                    rule.update(expires=2 if target=='expiry_only' else 100,max_uses=1000 if target=='expiry_only' else 1)
            case['trusted_prompt']+=' The read permission expires after step 2.' if target=='expiry_only' else ' Read the input only once.'
            case['case_id']+='-'+target
            for mode in ('static_scope','monotonic_shrink','shrink_and_lease','lease_only'):
                holder=[]
                def factory(policy,settings):
                    guard=LifecycleGuard(policy,settings,mode in {'monotonic_shrink','shrink_and_lease'})
                    holder.append(guard);return guard
                result=run_case(case,'v5',options={'lease':mode in {'shrink_and_lease','lease_only'},'triangulate':False},guard_factory=factory)
                late=next(e for e in result['events'] if e['action_id']=='a_late')
                rows.append({'case_id':case['case_id'],'family_id':case['family_id'],'target':target,'configuration':mode,
                             'late_call_executed':late['executed'],'late_reason':late['reason_code'],
                             'task_completion':result['goal_satisfied'],'approval_count':0,
                             'updates':holder[0].ledger.events,'run':result,
                             'scope':'capability VM lifecycle; fixed trusted step clock; no API calls'})
    destination=ROOT/'results/phase2/lifecycle';destination.mkdir(parents=True,exist_ok=True)
    (destination/'e7_policy_updates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    summary=[]
    for target in ('expiry_only','quota_only'):
        for mode in ('static_scope','monotonic_shrink','shrink_and_lease','lease_only'):
            chosen=[r for r in rows if r['target']==target and r['configuration']==mode]
            summary.append({'target':target,'configuration':mode,'n':len(chosen),'late_executions':sum(r['late_call_executed'] for r in chosen),
                            'task_completions':sum(r['task_completion'] for r in chosen)})
    (destination/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({'runs':len(rows),'summary':summary}))


if __name__=='__main__':main()
