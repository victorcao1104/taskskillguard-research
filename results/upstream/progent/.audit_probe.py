"""Local characterization only: no LLM/API/network/tool effects; upstream is unmodified."""
import contextlib
import copy
import importlib.metadata
import io
import json
import os
from pathlib import Path
import sys

os.environ['SECAGENT_GENERATE'] = 'False'
os.environ['ENABLE_SECAGENT'] = 'False'
os.environ['SECAGENT_POLICY_MODEL'] = 'audit-no-llm'
import secagent.tool as tool
import secagent.policy_analysis as pa
from jsonschema import validate
import z3

records = []
def observe(name, function, expected):
    try:
        actual = function()
        ok = actual == expected
        records.append(dict(name=name, expected=expected, actual=actual, characterized=ok))
    except Exception as error:
        records.append(dict(name=name, error=type(error).__name__ + ': ' + str(error), characterized=False))

def allowed(policy, kwargs=None, name='send'):
    tool.update_security_policy(policy)
    try:
        tool.check_tool_call(name, {} if kwargs is None else kwargs)
        return True
    except tool.ValidationError:
        return False

def policy(schema, effect=0):
    return {'send': [(100, effect, {'recipient': schema}, 0)]}

narrow = policy({'type': 'string', 'enum': ['alice@example.test']})
wide = policy({'type': 'string', 'enum': ['alice@example.test', 'bob@example.test']})
observe('allow_known_argument', lambda: allowed(narrow, {'recipient':'alice@example.test'}), True)
observe('reject_disallowed_argument', lambda: allowed(narrow, {'recipient':'bob@example.test'}), False)
observe('deny_unknown_tool_when_policy_exists', lambda: allowed(narrow, {}, 'unknown'), False)
observe('empty_policy_denies', lambda: allowed({}), False)
observe('uninitialized_policy_allows', lambda: allowed(None), True)
observe('missing_restricted_argument_is_skipped', lambda: allowed(narrow, {}), True)
observe('narrowing_enum_recognized', lambda: pa.security_policy_subset_check(wide, narrow), True)
observe('expansion_enum_rejected', lambda: pa.security_policy_subset_check(narrow, wide), False)
observe('new_tool_expansion_rejected', lambda: pa.security_policy_subset_check(narrow, {'other': [(100,0,{},0)]}), False)
observe('forbid_precedes_allow_same_priority', lambda: allowed({'send':[(1,0,{},0),(1,1,{},0)]}), False)
observe('higher_priority_allow_short_circuits_later_forbid', lambda: allowed({'send':[(1,0,{},0),(100,1,{},0)]}), True)

def default_binding():
    def send(recipient: str = 'bob@example.test'):
        """Return a mock recipient without external effects."""
        return recipient
    wrapped = tool.secure_tool_wrapper(send)
    tool.update_security_policy(copy.deepcopy(narrow))
    try:
        wrapped()
        return False
    except tool.ValidationError:
        return True
observe('python_wrapper_binds_defaults_and_denies', default_binding, True)

observe('jsonschema_const_expansion_misclassified', lambda: pa.security_policy_subset_check(policy({'type':'string','const':'alice'}), policy({'type':'string'})), True)
observe('unsupported_regex_anchor_expansion_misclassified', lambda: pa.security_policy_subset_check(policy({'type':'string','pattern':'^alice$'}), policy({'type':'string'})), True)
observe('forbid_to_allow_same_condition_misclassified', lambda: pa.security_policy_subset_check(policy({'type':'string'},1), policy({'type':'string'},0)), True)

def first_only():
    original = {'send':[(100,0,{},0),(100,1,{},0)]}
    new = {'send':[(100,0,{},0),(100,0,{'recipient':{'enum':['bob']}},0)]}
    return pa.security_policy_subset_check(original,new)
observe('comparator_only_first_rule_checked', first_only, True)

def regex_difference():
    schema = {'type':'string','pattern':'alice'}
    validate('xalicex', schema)
    x=z3.String('audit_regex')
    solver=z3.Solver()
    solver.add(pa.build_constraints(x,schema),x=='xalicex')
    return str(solver.check())
observe('jsonschema_search_vs_z3_full_match', regex_difference, 'unsat')

def forced_unknown():
    class FakeSolver:
        def add(self,*args): pass
        def set(self,*args): pass
        def check(self): return z3.unknown
    real = pa.Solver
    pa.Solver = FakeSolver
    try:
        return pa.security_policy_subset_check(narrow, wide)
    finally:
        pa.Solver = real
observe('injected_unknown_treated_as_subset', forced_unknown, True)

def mocked_update(narrow_only):
    old_api, old_decide, old_generate = tool.api_request, tool.decide_whether_to_update, tool.generate_policy
    old_narrow = os.environ.get('SECAGENT_ONLY_ALLOW_NARROW')
    tool.update_security_policy(copy.deepcopy(narrow))
    tool.init_user_query = 'Send mock message to alice@example.test.'
    tool.generate_policy = True
    tool.decide_whether_to_update = lambda *args: True
    tool.api_request = lambda *args: json.dumps([{'name':'send','args':wide['send'][0][2]}])
    os.environ['SECAGENT_ONLY_ALLOW_NARROW'] = str(narrow_only)
    try:
        tool.generate_update_security_policy({'name':'read'}, 'mock data', manual_check=False)
        try:
            tool.check_tool_call('send', {'recipient':'bob@example.test'})
            return True
        except tool.ValidationError:
            return False
    finally:
        tool.api_request, tool.decide_whether_to_update, tool.generate_policy = old_api, old_decide, old_generate
        if old_narrow is None:
            os.environ.pop('SECAGENT_ONLY_ALLOW_NARROW', None)
        else:
            os.environ['SECAGENT_ONLY_ALLOW_NARROW'] = old_narrow
observe('mocked_update_default_auto_approves_expansion', lambda: mocked_update(False), True)
observe('mocked_update_narrow_only_rejects_enum_expansion', lambda: mocked_update(True), False)

versions={name:importlib.metadata.version(name) for name in ['z3-solver','jsonschema','pydantic','docstring_parser']}
output={'scope':'Official unmodified core imported from source; custom deterministic characterization, not upstream full test suite or paper replication.', 'python':sys.version, 'versions':versions, 'records':records, 'characterized_count':sum(r['characterized'] for r in records), 'total':len(records)}
Path(__file__).with_name('.audit_results.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
print(json.dumps(output,indent=2))
sys.exit(0 if all(r['characterized'] for r in records) else 1)
