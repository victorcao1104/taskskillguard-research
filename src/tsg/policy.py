"""Restricted exact-resource policies. Inspired by Progent; independently written.

No general JSON Schema-to-SMT translation: unsupported semantics are UNKNOWN.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from urllib.parse import urlsplit, urlunsplit, unquote
from pathlib import PurePosixPath
import z3

TOOLS = frozenset({'file.read','file.write','file.delete','secret.read','network.get','network.post','email.send','db.read','db.write','command.exec'})


def canonical_resource(resource: str) -> str:
    if not isinstance(resource, str) or not resource or any(ord(c)<32 for c in resource) or '\\' in resource:
        raise ValueError('INVALID_RESOURCE')
    if resource.startswith('https://'):
        u = urlsplit(resource)
        if not u.hostname or ':' in u.hostname or u.username or u.password or u.fragment or u.port not in (None,443):
            raise ValueError('INVALID_URL')
        if '..' in unquote(u.path).split('/') or '%' in u.netloc:
            raise ValueError('INVALID_URL')
        return urlunsplit(('https', u.hostname.lower(), u.path or '/', u.query, ''))
    if not resource.startswith('/sandbox/') or '..' in resource.split('/') or ':' in resource or '%' in resource:
        raise ValueError('INVALID_PATH')
    return str(PurePosixPath(resource))


@dataclass(frozen=True)
class Rule:
    operation: str
    resource: str
    effect: str = 'allow'
    starts: int = 0
    expires: int = 100
    max_uses: int = 1000
    evidence_id: str = 'trusted_task'

    def valid(self):
        try:
            return (self.operation in TOOLS and self.effect in ('allow','forbid')
                    and canonical_resource(self.resource) == self.resource
                    and type(self.starts) is int and type(self.expires) is int and type(self.max_uses) is int
                    and 0 <= self.starts <= self.expires and self.max_uses >= 0)
        except (ValueError, TypeError):
            return False


@dataclass(frozen=True)
class Policy:
    rules: tuple[Rule, ...]
    supported: bool = True

    def valid(self):
        return self.supported is True and isinstance(self.rules,tuple) and all(isinstance(r,Rule) and r.valid() for r in self.rules)

    def allows(self, operation, resource, step, uses=0, temporal=True):
        if not self.valid() or operation not in TOOLS:
            return False
        try:
            resource = canonical_resource(resource)
        except (ValueError, TypeError):
            return False
        matched = [r for r in self.rules if r.operation==operation and r.resource==resource and
                   (not temporal or r.starts <= step <= r.expires and uses < r.max_uses)]
        return any(r.effect=='allow' for r in matched) and not any(r.effect=='forbid' for r in matched)

    def to_dict(self):
        return {'rules': [asdict(r) for r in self.rules], 'supported': self.supported, 'default_action':'deny'}

    @classmethod
    def from_dict(cls, value):
        try:
            if set(value)-{'rules','supported','default_action'} or value.get('default_action','deny')!='deny':
                return cls((), supported=False)
            result = cls(tuple(Rule(**r) for r in value['rules']), value.get('supported', True))
            return result if result.valid() else cls((), supported=False)
        except (TypeError,KeyError,ValueError):
            return cls((), supported=False)


def compare_policies(old: Policy, new: Policy, timeout_ms=1000):
    if not old.valid() or not new.valid():
        return {'relation':'unknown','solver':'UNSUPPORTED','witness':None}
    # The default Z3 context is not safe to share across API worker threads.
    # Every AST, including empty disjunctions, belongs to this call's context.
    context = z3.Context()
    operation, resource = z3.Strings('operation resource', ctx=context)
    step, uses = z3.Ints('step uses', ctx=context)
    def allowed(p):
        def cond(r):
            return z3.And(operation==r.operation, resource==r.resource, step>=r.starts, step<=r.expires, uses<r.max_uses)
        def disjunction(effect):
            terms = [cond(r) for r in p.rules if r.effect == effect]
            return z3.Or(*terms) if terms else z3.BoolVal(False, ctx=context)
        return z3.And(disjunction('allow'), z3.Not(disjunction('forbid')))
    solver = z3.Solver(ctx=context)
    solver.set(timeout=timeout_ms)
    solver.add(step>=0, uses>=0, allowed(new), z3.Not(allowed(old)))
    status = solver.check()
    if status == z3.unsat:
        return {'relation':'subset','solver':'UNSAT','witness':None}
    if status == z3.sat:
        m = solver.model()
        witness = {'operation':m.eval(operation).as_string(),'resource':m.eval(resource).as_string(),
                   'step':m.eval(step).as_long(),'uses':m.eval(uses).as_long()}
        return {'relation':'expansion','solver':'SAT','witness':witness}
    return {'relation':'unknown','solver':'UNKNOWN','witness':None}


class Ledger:
    def __init__(self, ceiling):
        self.ceiling = ceiling
        self.effective = ceiling
        self.events = []

    def update(self, proposed, evidence_source='skill', approved=False):
        comparison = compare_policies(self.effective, proposed)
        accept = comparison['relation']=='subset' or (comparison['relation']=='expansion' and evidence_source in {'user','administrator'} and approved is True)
        self.events.append({**comparison,'evidence_source':evidence_source,'approved':approved,'accepted':accept})
        if accept:
            self.effective = proposed
            if comparison['relation']=='expansion':
                self.ceiling = proposed
        return accept


@dataclass(frozen=True)
class LabeledValue:
    value: str
    sources: frozenset[str]
    readers: frozenset[str] | None  # None = explicitly public; missing object != public.

    def can_send(self, destination):
        return self.readers is None or destination in self.readers


def combine(values: list[LabeledValue], transformed_value: str) -> LabeledValue:
    sources = frozenset().union(*(v.sources for v in values))
    restrictions = [v.readers for v in values if v.readers is not None]
    readers = frozenset.intersection(*restrictions) if restrictions else None
    return LabeledValue(transformed_value, sources, readers)


class Guard:
    def __init__(self, policy, *, taint=False, lease=False):
        self.policy, self.taint, self.lease = policy, taint, lease
        self.uses = {}
        self.last_step = -1

    def check(self, operation, resource, step, value=None):
        if type(step) is not int or step < self.last_step:
            return False, 'CLOCK_ROLLBACK'
        self.last_step = step
        try:
            resource = canonical_resource(resource)
        except (ValueError,TypeError):
            return False, 'INVALID_RESOURCE'
        key = (operation,resource)
        used = self.uses.get(key,0)
        if not self.policy.allows(operation,resource,step,used,temporal=self.lease):
            potential = self.policy.valid() and any(r.effect=='allow' and r.operation==operation and r.resource==resource for r in self.policy.rules)
            active_forbid=any(r.effect=='forbid' and r.operation==operation and r.resource==resource and (not self.lease or r.starts<=step<=r.expires and used<r.max_uses) for r in self.policy.rules)
            return False, 'LEASE_EXPIRED' if self.lease and potential and not active_forbid else 'POLICY_DENY'
        if self.taint and operation in {'network.post','email.send','file.write','db.write'}:
            if value is None:
                return False, 'MISSING_LABEL'
            reader = 'user' if operation in {'file.write','db.write'} else resource
            if not value.can_send(reader):
                return False, 'DATA_FLOW_DENY'
        self.uses[key] = used+1
        return True, 'ALLOW'
