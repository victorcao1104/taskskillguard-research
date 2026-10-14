"""Bounded P/Q orchestration with actual contract-to-execution ablations.

The executor is the named capability VM, never a claim of an OS sandbox.
Q proposals and classifier outputs cannot modify the authority ledger. The
independent OS track exercises real processes and original-source scripts.
"""
import copy
from .policy import Policy, Rule
from .sandbox import run_case, replay_case
from .contracts_v2 import Contract, ContractGuard, DualLedger, compare_contracts

_BASE = dict(graph=True, replay=True, trust=True, taint=True, guard=True, smt=True,
             triangulate=True, lease=True)
FEATURES = {'full': _BASE, **{'no_'+k: {**_BASE, k: False} for k in _BASE}}


def make_scope_contract(policy, task_id):
    rules = []
    for i, old in enumerate(policy.get('rules', [])):
        rule = {'rule_id': f'r{i}', 'effect': old.get('effect', 'allow'),
                'operation': old['operation'], 'resource': old['resource'],
                'approval_id': 'task_initial', 'evidence_ids': ['task_initial']}
        for source, target in [('starts','starts_at_step'), ('expires','expires_after_step'), ('max_uses','max_uses')]:
            if source in old and not (source=='max_uses' and rule['effect']=='forbid'):
                rule[target] = old[source]
        if old['operation'] in {'network.post','file.write'}:
            rule['parameters'] = {'type':'object','properties':{'body':{'type':'string'}},
                                  'required':['body'],'additionalProperties':False}
        rules.append(rule)
    return {'contract_id': task_id+'-contract', 'task_id':task_id, 'skill_id':task_id,
            'policy_version':1, 'authority_source':'trusted_user_request', 'rules':rules,
            'default_action':'deny','review_on_unknown':True}


def _project(contract):
    return Policy(tuple(Rule(r['operation'], r['resource'], r['effect'],
                             r.get('starts_at_step',0),r.get('expires_after_step',100000),
                             r.get('max_uses',100000)) for r in contract.to_dict()['rules']))


class Adapter:
    def __init__(self, contract, settings):
        self.inner = ContractGuard(contract, lease=settings['lease'])
        self.policy = _project(contract)
        self.taint = settings['taint']

    def check(self, operation, resource, step, value=None):
        # A denied information flow must not consume the legitimate send quota.
        if self.taint and operation in {'file.write','network.post'}:
            if value is None:
                return False, 'MISSING_LABEL'
            destination = 'user' if operation == 'file.write' else resource
            if not value.can_send(destination):
                return False, 'DATA_FLOW_DENY'
        args = {'body': value.value} if value is not None and operation in {'file.write','network.post'} else {}
        return self.inner.check(operation, resource, step, args=args)


def run_pipeline(case, graph_prediction, raw_prediction, generated_separated, generated_mixed,
                 *, variant='full', filter_actions=True, q_plan=None, reference_actions=None):
    features = FEATURES[variant]
    selected = generated_separated if features['trust'] else generated_mixed
    policy_valid = selected is not None and Policy.from_dict(selected).valid()
    selected = selected if policy_valid else Policy(()).to_dict()
    initial = Contract.from_dict(make_scope_contract(selected,case['case_id']))
    if not initial.valid():
        policy_valid = False
        initial = Contract.from_dict(make_scope_contract({'rules':[]},case['case_id']))
    ledger = DualLedger(initial)
    ledger.record_skill_evidence('q_claim','q_parser','Proposed scopes from grounded skill actions; no approval authority.')
    proposed = initial.to_dict()
    current = {(r['operation'],r['resource']) for r in proposed['rules']}
    for action in case['actions']:
        if action['operation']!='transform' and (action['operation'],action['resource']) not in current:
            entry = make_scope_contract({'rules':[{'operation':action['operation'],'resource':action['resource']}]},case['case_id'])['rules'][0]
            entry['rule_id'] = 'q'+str(len(proposed['rules']))
            # Deliberately claims initial evidence, but the SMT scope check still
            # requires an independent approval for any expansion.
            proposed['rules'].append(entry)
            current.add((action['operation'],action['resource']))
    proposal = Contract.from_dict(proposed)
    if features['smt']:
        ledger.update(proposal)
        effective = ledger.effective
        update = ledger.events[-1]
    else:
        # Remove only transition subset enforcement. The independent authority
        # scope/evidence gate is retained; disabling both would conflate two
        # defenses and manufacture an apparent isolated SMT effect.
        evidence_valid = proposal.valid() and ledger._evidence_valid(proposal)
        accepted = evidence_valid and proposal.to_dict()['task_id']==initial.to_dict()['task_id']
        effective = proposal if accepted else initial
        update = {'relation':'not_checked','solver':'TRANSITION_CHECK_DISABLED',
                  'witness':None,'accepted':accepted,'update_reason':'AUTHORITY_GATE_RETAINED',
                  'authority_scope_valid':evidence_valid,'approval_id':None,
                  'scope_note':'Authority evidence validation retains its own scope checks.'}
    chosen = graph_prediction if features['graph'] else raw_prediction
    prediction_map = {a['action_id']: a for a in (chosen or {}).get('actions',[])}
    actions = case['actions'] if q_plan is None else [a for aid in q_plan for a in case['actions'] if a['id']==aid]
    removed_classifier = []; removed_replay = []; evidence = []
    filtered = []
    for a in actions:
        pred = prediction_map.get(a['id'],{})
        if filter_actions and pred.get('authorized')=='no':
            removed_classifier.append(a['id']); continue
        if filter_actions and features['replay'] and a['operation']!='transform':
            replay = replay_case(case,a['id'])
            evidence.append({'action_id':a['id'],'status':replay['status'],
                             'core_preserved':replay['core_preserved'],'goal_satisfied':replay['replay_goal']})
            if replay['status']=='comparable' and replay['unnecessary_replay'] is True:
                removed_replay.append(a['id']); continue
        filtered.append(a)
    settings = {k:features[k] for k in ('guard','taint','lease','triangulate')}
    run = run_case(case,'v5',actions=filtered,policy=_project(effective).to_dict(),options=settings,
                   guard_factory=lambda _p,s: Adapter(effective,s),reference_actions=reference_actions)
    required = {r['action_id'] for r in case['ground_truth'] if r['authorized'] and r['necessary']}
    incorrect_denials = [e['action_id'] for e in run['events'] if e['action_id'] in required and not e['executed']]
    executed_ids = {e['action_id'] for e in run['events'] if e['executed']}
    return {'case_id':case['case_id'],'family_id':case['family_id'],'split':case['split'],
            'scenario':case['scenario'],'variant':variant,'features':features,
            'status':'valid' if policy_valid else 'unresolved_policy','filter_actions':filter_actions,
            'initial_contract':initial.to_dict(),'effective_contract':effective.to_dict(),
            'update':update,'authority_ledger':ledger.authority_ledger,'skill_evidence_ledger':ledger.skill_evidence_ledger,
            'removed_by_classifier':removed_classifier,'removed_by_replay':removed_replay,
            'replay_evidence':evidence,'required_call_denials':incorrect_denials,
            'required_actions_not_executed':sorted(required-executed_ids),
            'classifier_coverage':sum(a['id'] in prediction_map for a in case['actions'] if a['operation']!='transform'),
            'run':run}
