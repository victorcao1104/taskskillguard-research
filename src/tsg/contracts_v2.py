"""Bounded JSON-Schema contracts, SMT comparison, and separate evidence ledgers.

Independent research implementation; see docs/phase2_contracts.md for its
grammar and proof boundary. This module performs no tool or network execution.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
import z3


SCHEMA_PATH = Path(__file__).resolve().parents[2] / 'configs' / 'contract_v2.schema.json'
CONTRACT_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
Draft202012Validator.check_schema(CONTRACT_SCHEMA)
_VALIDATOR = Draft202012Validator(CONTRACT_SCHEMA)
EMPTY_PARAMETERS = {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}
_DOMAIN = re.compile(r'(?=.{1,253}\Z)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\Z')
_SEGMENT = re.compile(r'[A-Za-z0-9._~-]+\Z')
_TRUSTED = frozenset({'user', 'administrator'})


def canonical_resource(resource):
    """Canonical names in the virtual sandbox; deliberately no host filesystem IO.

    No encoded characters, queries, fragments, credentials, non-443 ports,
    dot segments, backslashes, or non-ASCII path characters are supported.
    """
    if not isinstance(resource, str) or not resource or len(resource) > 512:
        raise ValueError('INVALID_RESOURCE')
    if any(ord(c) < 32 or ord(c) > 126 for c in resource) or any(c in resource for c in ('%', '\\', '?', '#')):
        raise ValueError('INVALID_RESOURCE')
    if resource.startswith('https://'):
        try:
            parsed = urlsplit(resource)
            host = parsed.hostname or ''
            if (not _DOMAIN.fullmatch(host) or parsed.username or parsed.password
                    or parsed.port not in (None, 443)):
                raise ValueError('INVALID_RESOURCE')
            path = parsed.path or '/'
        except ValueError:
            raise ValueError('INVALID_RESOURCE') from None
        parts = path.strip('/').split('/') if path != '/' else []
        if not path.startswith('/') or '//' in path or any(not _SEGMENT.fullmatch(p) or p in {'.', '..'} for p in parts):
            raise ValueError('INVALID_RESOURCE')
        return 'https://' + host + path
    if resource != '/sandbox' and not resource.startswith('/sandbox/'):
        raise ValueError('INVALID_RESOURCE')
    parts = resource[1:].split('/')
    if any(not _SEGMENT.fullmatch(p) or p in {'.', '..'} for p in parts):
        raise ValueError('INVALID_RESOURCE')
    return resource


def _validate_semantics(obj):
    errors = []
    ids = set()
    for rule in obj['rules']:
        if rule['rule_id'] in ids:
            errors.append('DUPLICATE_RULE_ID')
        ids.add(rule['rule_id'])
        resource = rule['resource']
        try:
            if isinstance(resource, str):
                if canonical_resource(resource) != resource:
                    errors.append('NONCANONICAL_RESOURCE')
            elif 'path_prefix' in resource:
                prefix = resource['path_prefix']
                if canonical_resource(prefix) != prefix or not prefix.startswith('/sandbox'):
                    errors.append('INVALID_PATH_PREFIX')
            elif any(not _DOMAIN.fullmatch(d) for d in resource['domains']):
                errors.append('INVALID_DOMAIN')
        except (ValueError, TypeError):
            errors.append('INVALID_RESOURCE')
        if rule.get('expires_after_step', rule.get('starts_at_step', 0)) < rule.get('starts_at_step', 0):
            errors.append('INVALID_LEASE_WINDOW')
        schema = rule.get('parameters', EMPTY_PARAMETERS)
        if set(schema.get('required', [])) - set(schema['properties']):
            errors.append('REQUIRED_PROPERTY_NOT_DECLARED')
        for prop in schema['properties'].values():
            if prop['type'] != 'integer' and any(k in prop for k in ('minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum')):
                errors.append('UNSUPPORTED_SCALAR_BOUND')
            values = prop.get('enum', []) + ([prop['const']] if 'const' in prop else [])
            type_validator = Draft202012Validator({'type': prop['type']})
            if any(not type_validator.is_valid(v) for v in values):
                errors.append('SCALAR_TYPE_MISMATCH')
    return errors


@dataclass(frozen=True)
class Contract:
    _json: str
    errors: tuple[str, ...] = ()

    def __post_init__(self):
        # A direct constructor cannot bypass the from_dict validation boundary.
        if self.errors:
            return
        try:
            if len(self._json) > 262144:
                errors = ['CONTRACT_TOO_LARGE']
            else:
                obj = json.loads(self._json)
                errors = ['SCHEMA:' + '/'.join(str(p) for p in e.absolute_path) + ':' + str(e.validator)
                          for e in _VALIDATOR.iter_errors(obj)]
                if not errors:
                    errors = _validate_semantics(obj)
            object.__setattr__(self, 'errors', tuple(errors))
        except (TypeError, ValueError, RecursionError):
            object.__setattr__(self, 'errors', ('INVALID_JSON_VALUE',))

    @classmethod
    def from_dict(cls, value):
        try:
            encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
            if len(encoded) > 262144:
                return cls('{}', ('CONTRACT_TOO_LARGE',))
            return cls(encoded)
        except (TypeError, ValueError, RecursionError):
            return cls('{}', ('INVALID_JSON_VALUE',))

    def valid(self):
        return not self.errors

    def to_dict(self):
        return json.loads(self._json)

    @property
    def digest(self):
        return sha256(self._json.encode()).hexdigest()

    def allows(self, operation, resource, step, args=None, stage='default', uses=0, temporal=True):
        return self.decision(operation, resource, step, args, stage, uses, temporal)[0]

    def decision(self, operation, resource, step, args=None, stage='default', uses=0, temporal=True):
        if not self.valid():
            return False, 'UNSUPPORTED_CONTRACT'
        if type(step) is not int or step < 0 or type(uses) is not int or uses < 0 or not isinstance(stage, str):
            return False, 'INVALID_CONTEXT'
        try:
            canonical = canonical_resource(resource)
        except (TypeError, ValueError):
            return False, 'INVALID_RESOURCE'
        args = {} if args is None else args
        if not isinstance(args, dict):
            return False, 'PARAMETERS_DENY'
        matched = [r for r in self.to_dict()['rules'] if r['operation'] == operation and _resource_matches(r['resource'], canonical)]
        if not matched:
            return False, 'POLICY_DENY'
        matches = [r for r in matched if Draft202012Validator(r.get('parameters', EMPTY_PARAMETERS)).is_valid(args)]
        if not matches:
            return False, 'PARAMETERS_DENY'
        active = [r for r in matches if not temporal or _in_window(r, step, stage)]
        if any(r['effect'] == 'forbid' for r in active):
            return False, 'FORBID'
        allowed = [r for r in active if r['effect'] == 'allow']
        if any(not temporal or 'max_uses' not in r or uses < r['max_uses'] for r in allowed):
            return True, 'ALLOW'
        if allowed:
            return False, 'QUOTA_EXHAUSTED'
        candidates = [r for r in matches if r['effect'] == 'allow']
        if not candidates:
            return False, 'POLICY_DENY'
        if all(step > r.get('expires_after_step', float('inf')) for r in candidates):
            return False, 'LEASE_EXPIRED'
        if all(step < r.get('starts_at_step', 0) for r in candidates):
            return False, 'LEASE_NOT_STARTED'
        if all('allowed_stages' in r and stage not in r['allowed_stages'] for r in candidates):
            return False, 'STAGE_DENY'
        return False, 'LEASE_INACTIVE'


def _in_window(rule, step, stage):
    return (step >= rule.get('starts_at_step', 0)
            and ('expires_after_step' not in rule or step <= rule['expires_after_step'])
            and ('allowed_stages' not in rule or stage in rule['allowed_stages']))


def _resource_matches(selector, canonical):
    if isinstance(selector, str):
        return canonical == selector
    if 'path_prefix' in selector:
        prefix = selector['path_prefix']
        return canonical == prefix or canonical.startswith(prefix + '/')
    return canonical.startswith('https://') and urlsplit(canonical).hostname in selector['domains']


class _SymbolicCall:
    """One isolated Z3 context per query, including every empty connective."""
    def __init__(self, contracts):
        self.ctx = z3.Context()
        self.operation, self.resource, self.stage = z3.Strings('operation resource stage', ctx=self.ctx)
        self.step, self.uses = z3.Ints('step uses', ctx=self.ctx)
        rules = [r for c in contracts for r in c.to_dict()['rules']]
        fields = sorted({k for r in rules for k in r.get('parameters', EMPTY_PARAMETERS)['properties']})
        self.fields = {k: (z3.Bool('has_' + k, ctx=self.ctx), z3.Int('type_' + k, ctx=self.ctx),
                           z3.String('str_' + k, ctx=self.ctx), z3.Int('int_' + k, ctx=self.ctx),
                           z3.Bool('bool_' + k, ctx=self.ctx)) for k in fields}
        # Constrain witnesses to precisely the supported canonical resource grammar.
        ch = z3.Union(*[z3.Range(a, b, ctx=self.ctx) for a, b in [('A', 'Z'), ('a', 'z'), ('0', '9')]],
                      *[z3.Re(c, ctx=self.ctx) for c in '._~-'])
        segment = z3.Diff(z3.Plus(ch), z3.Union(z3.Re('.', ctx=self.ctx), z3.Re('..', ctx=self.ctx)))
        rest = z3.Star(z3.Concat(z3.Re('/', ctx=self.ctx), segment))
        paths = z3.Concat(z3.Re('/sandbox', ctx=self.ctx), rest)
        domains = set()
        for r in rules:
            selector = r['resource']
            if isinstance(selector, dict) and 'domains' in selector:
                domains.update(selector['domains'])
            elif isinstance(selector, str) and selector.startswith('https://'):
                domains.add(urlsplit(selector).hostname)
        urls = [z3.Concat(z3.Re('https://' + d, ctx=self.ctx),
                          z3.Union(z3.Re('/', ctx=self.ctx),
                                   z3.Concat(z3.Re('/', ctx=self.ctx), segment, rest,
                                             z3.Option(z3.Re('/', ctx=self.ctx))))) for d in sorted(domains)]
        grammar = z3.Union(paths, *urls) if urls else paths
        self.domain = self.all([self.step >= 0, self.uses >= 0, z3.InRe(self.resource, grammar), z3.Length(self.resource) <= 512])

    def all(self, clauses):
        return z3.And(*clauses) if clauses else z3.BoolVal(True, ctx=self.ctx)

    def any(self, clauses):
        return z3.Or(*clauses) if clauses else z3.BoolVal(False, ctx=self.ctx)

    def parameters(self, schema):
        clauses = []
        properties = schema['properties']
        for key, (present, tag, string, integer, boolean) in self.fields.items():
            if key not in properties:
                clauses.append(z3.Not(present))
                continue
            prop = properties[key]
            type_id = {'string': 0, 'integer': 1, 'boolean': 2}[prop['type']]
            value = [string, integer, boolean][type_id]
            restrictions = [tag == type_id]
            if 'const' in prop:
                restrictions.append(value == prop['const'])
            if 'enum' in prop:
                restrictions.append(self.any([value == v for v in prop['enum']]))
            for key_op, op in [('minimum', lambda a, b: a >= b), ('maximum', lambda a, b: a <= b),
                               ('exclusiveMinimum', lambda a, b: a > b), ('exclusiveMaximum', lambda a, b: a < b)]:
                if key_op in prop:
                    restrictions.append(op(value, prop[key_op]))
            clauses.append(z3.Implies(present, self.all(restrictions)))
            if key in schema.get('required', []):
                clauses.append(present)
        return self.all(clauses)

    def rule(self, rule):
        selector = rule['resource']
        if isinstance(selector, str):
            resource = self.resource == selector
        elif 'path_prefix' in selector:
            prefix = selector['path_prefix']
            resource = z3.Or(self.resource == prefix, z3.PrefixOf(prefix + '/', self.resource))
        else:
            resource = self.any([z3.PrefixOf('https://' + d + '/', self.resource) for d in selector['domains']])
        clauses = [self.operation == rule['operation'], resource,
                   self.parameters(rule.get('parameters', EMPTY_PARAMETERS)), self.step >= rule.get('starts_at_step', 0)]
        if 'expires_after_step' in rule:
            clauses.append(self.step <= rule['expires_after_step'])
        if 'allowed_stages' in rule:
            clauses.append(self.any([self.stage == stage for stage in rule['allowed_stages']]))
        if rule['effect'] == 'allow' and 'max_uses' in rule:
            clauses.append(self.uses < rule['max_uses'])
        return self.all(clauses)

    def allows(self, contract):
        rules = contract.to_dict()['rules']
        return self.all([self.any([self.rule(r) for r in rules if r['effect'] == 'allow']),
                         z3.Not(self.any([self.rule(r) for r in rules if r['effect'] == 'forbid']))])

    def witness(self, model):
        def evaluate(value):
            return model.eval(value, model_completion=True)
        args = {}
        for key, (present, tag, string, integer, boolean) in self.fields.items():
            if z3.is_true(evaluate(present)):
                type_id = evaluate(tag).as_long()
                args[key] = (evaluate(string).as_string() if type_id == 0 else evaluate(integer).as_long()
                             if type_id == 1 else z3.is_true(evaluate(boolean)))
        return {'operation': evaluate(self.operation).as_string(), 'resource': evaluate(self.resource).as_string(),
                'step': evaluate(self.step).as_long(), 'uses': evaluate(self.uses).as_long(),
                'stage': evaluate(self.stage).as_string(), 'args': args}


def compare_contracts(old, new, timeout_ms=2000):
    """Prove Allow(new,c) => Allow(old,c) inside the documented grammar only."""
    base = {'relation': 'unknown', 'solver': 'UNSUPPORTED', 'witness': None, 'reason': 'UNSUPPORTED_CONTRACT'}
    if not isinstance(old, Contract) or not isinstance(new, Contract) or not old.valid() or not new.valid():
        return base
    if type(timeout_ms) is not int or timeout_ms < 1:
        return {**base, 'reason': 'INVALID_TIMEOUT'}
    try:
        symbolic = _SymbolicCall((old, new))
        solver = z3.Solver(ctx=symbolic.ctx)
        solver.set(timeout=timeout_ms)
        solver.add(symbolic.domain, symbolic.allows(new), z3.Not(symbolic.allows(old)))
        result = solver.check()
        if result == z3.unsat:
            return {'relation': 'subset', 'solver': 'UNSAT', 'witness': None, 'reason': 'PROVED_WITHIN_SUPPORTED_GRAMMAR'}
        if result == z3.sat:
            witness = symbolic.witness(solver.model())
            # A SAT witness is usable evidence only if concrete execution agrees.
            if new.allows(**witness) and not old.allows(**witness):
                return {'relation': 'expansion', 'solver': 'SAT', 'witness': witness, 'reason': 'REPLAYED_EXPANSION_WITNESS'}
            return {**base, 'solver': 'UNKNOWN', 'reason': 'WITNESS_RUNTIME_MISMATCH'}
        return {**base, 'solver': 'UNKNOWN', 'reason': solver.reason_unknown()}
    except (z3.Z3Exception, ValueError, TypeError, KeyError):
        return {**base, 'solver': 'UNKNOWN', 'reason': 'COMPILER_OR_SOLVER_ERROR'}


class ContractGuard:
    def __init__(self, contract, *, lease=True):
        self.contract = contract
        self.lease = lease
        self.uses = {}
        self.last_step = -1

    def check(self, operation, resource, step, args=None, stage='default'):
        if type(step) is not int or step < 0 or step < self.last_step:
            return False, 'CLOCK_ROLLBACK'
        self.last_step = step
        try:
            canonical = canonical_resource(resource)
        except (TypeError, ValueError):
            return False, 'INVALID_RESOURCE'
        key = (operation, canonical)
        decision = self.contract.decision(operation, canonical, step, args, stage, self.uses.get(key, 0), self.lease)
        if decision[0]:
            self.uses[key] = self.uses.get(key, 0) + 1
        return decision


class DualLedger:
    """Trusted harness API. Skill/model data may call only record_skill_evidence.

    register_approval is an explicit trusted-channel capability, not a parser of
    model-provided actor/approved strings. The embedding runtime must enforce
    that channel boundary. No cryptographic identity claim is made here.
    """
    def __init__(self, initial_contract, trusted_initial_evidence=('task_initial',)):
        if not isinstance(initial_contract, Contract) or not initial_contract.valid():
            raise ValueError('UNSUPPORTED_INITIAL_CONTRACT')
        self._effective = initial_contract
        self._ceiling = initial_contract
        self._authority = [{'approval_id': 'task_initial', 'actor': 'user', 'approved': True,
                            'consumed': True,
                            'evidence_ids': list(trusted_initial_evidence),
                            'task_id': initial_contract.to_dict()['task_id'],
                            'contract_digest': initial_contract.digest, 'scope': initial_contract.to_dict(),
                            'timestamp_utc': datetime.now(timezone.utc).isoformat()}]
        self._skill_evidence = []
        self._events = []
        if not self._evidence_valid(initial_contract):
            raise ValueError('UNTRUSTED_INITIAL_EVIDENCE')

    @property
    def effective(self):
        return self._effective

    @property
    def task_ceiling(self):
        return self._ceiling

    @property
    def authority_ledger(self):
        return deepcopy(self._authority)

    @property
    def skill_evidence_ledger(self):
        return deepcopy(self._skill_evidence)

    @property
    def events(self):
        return deepcopy(self._events)

    def record_skill_evidence(self, evidence_id, source, claim):
        # The content remains audit evidence even when it claims to be trusted.
        self._skill_evidence.append({'evidence_id': str(evidence_id), 'source': str(source),
                                     'claim': str(claim), 'authority': False,
                                     'task_id': self._effective.to_dict()['task_id']})

    def register_approval(self, approval_id, proposed, *, actor='user', approved=False, evidence_ids=None):
        if (actor not in _TRUSTED or approved is not True or not isinstance(approval_id, str) or not approval_id
                or not isinstance(proposed, Contract) or not proposed.valid()
                or proposed.to_dict()['task_id'] != self._effective.to_dict()['task_id']
                or any(a['approval_id'] == approval_id for a in self._authority)):
            return False
        evidence_ids = [approval_id] if evidence_ids is None else evidence_ids
        if not isinstance(evidence_ids, (list, tuple)) or not evidence_ids or any(not isinstance(x, str) or not x for x in evidence_ids):
            return False
        self._authority.append({'approval_id': approval_id, 'actor': actor, 'approved': True,
                                'consumed': False,
                                'evidence_ids': list(evidence_ids), 'task_id': proposed.to_dict()['task_id'],
                                'contract_digest': proposed.digest, 'scope': proposed.to_dict(),
                                'timestamp_utc': datetime.now(timezone.utc).isoformat()})
        return True

    def _evidence_valid(self, proposed):
        authorities = {row['approval_id']: row for row in self._authority}
        obj = proposed.to_dict()
        forbids = [r for r in obj['rules'] if r['effect'] == 'forbid']
        for rule in obj['rules']:
            if rule['effect'] != 'allow':
                continue
            record = authorities.get(rule['approval_id'])
            if record is None or not set(rule['evidence_ids']).issubset(record['evidence_ids']):
                return False
            if record['contract_digest'] != proposed.digest:
                # The rule's actual granted scope (after local forbids) must be
                # within the specific authority record cited by that rule.
                scoped = Contract.from_dict({**obj, 'rules': [rule, *forbids]})
                if compare_contracts(Contract.from_dict(record['scope']), scoped)['relation'] != 'subset':
                    return False
        return True

    def update(self, proposed, approval_id=None):
        result = compare_contracts(self._effective, proposed)
        supported = isinstance(proposed, Contract) and proposed.valid()
        same_task = supported and proposed.to_dict()['task_id'] == self._effective.to_dict()['task_id']
        approval = next((a for a in self._authority if a['approval_id'] == approval_id), None)
        exact_approval = (approval is not None and not approval['consumed'] and supported
                          and approval['contract_digest'] == proposed.digest)
        accept = (same_task and self._evidence_valid(proposed) and
                  (result['relation'] == 'subset' or (result['relation'] == 'expansion' and exact_approval)))
        reason = ('ACCEPTED' if accept else 'TASK_MISMATCH' if supported and not same_task else
                  'UNTRUSTED_EVIDENCE' if supported and not self._evidence_valid(proposed) else
                  'APPROVAL_REQUIRED' if result['relation'] == 'expansion' else 'UNKNOWN_RETAINED')
        self._events.append({**result, 'accepted': bool(accept), 'approval_id': approval_id,
                             'update_reason': reason, 'old_digest': self._effective.digest,
                             'proposed_digest': proposed.digest if isinstance(proposed, Contract) else None})
        if accept:
            self._effective = proposed
            if result['relation'] == 'expansion':
                self._ceiling = proposed
                approval['consumed'] = True
        return bool(accept)
