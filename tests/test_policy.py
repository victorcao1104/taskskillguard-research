import pytest
from tsg.policy import Policy, Rule, compare_policies, canonical_resource, LabeledValue, combine, Ledger, Guard


def policy(*rules):
    return Policy(tuple(rules))


def test_exact_scope_and_default_deny():
    p = policy(Rule('file.read', '/sandbox/input/a.csv'))
    assert p.allows('file.read', '/sandbox/input/a.csv', 0)
    assert not p.allows('file.read', '/sandbox/input/a.csv.evil', 0)
    assert not p.allows('command.exec', '/sandbox/input/a.csv', 0)
    assert not p.allows('file.read', '', 0)


@pytest.mark.parametrize('bad', ['/sandbox/../secret', '/sandbox/in/../../secret', 'C:\\Users\\test', '/sandbox/in\\..\\secret', 'https://user:pass@mock.invalid/x', 'http://mock.invalid/x', 'https://mock.invalid/x#secret'])
def test_ambiguous_resources_rejected(bad):
    with pytest.raises(ValueError):
        canonical_resource(bad)


def test_policy_subset_sat_unsat_and_unknown():
    old = policy(Rule('file.read', '/sandbox/a'), Rule('file.write', '/sandbox/b'))
    narrow = policy(Rule('file.read', '/sandbox/a'))
    assert compare_policies(old, narrow)['relation'] == 'subset'
    expanded = policy(Rule('file.read', '/sandbox/a'), Rule('file.read', '/sandbox/c'))
    r = compare_policies(old, expanded)
    assert r['relation'] == 'expansion'
    assert r['witness']['resource'] == '/sandbox/c'
    assert compare_policies(old, Policy((), supported=False))['relation'] == 'unknown'


def test_untrusted_evidence_and_unknown_cannot_expand():
    p = policy(Rule('file.read', '/sandbox/a'))
    ledger = Ledger(p)
    expanded = policy(*p.rules, Rule('secret.read', '/sandbox/mock-secret'))
    assert not ledger.update(expanded, evidence_source='skill', approved=True)
    assert not ledger.update(Policy((), supported=False), evidence_source='user', approved=True)
    assert ledger.effective == p
    assert ledger.update(policy(), evidence_source='skill')
    assert not ledger.effective.rules


def test_reader_intersection_survives_summary():
    public = LabeledValue('public', frozenset({'a'}), None)
    private = LabeledValue('FAKE', frozenset({'secret'}), frozenset({'user'}))
    summary = combine([public, private], 'short summary')
    assert summary.sources == frozenset({'a','secret'})
    assert summary.readers == frozenset({'user'})
    assert not summary.can_send('https://mock.invalid/status')
    assert public.can_send('https://mock.invalid/status')


def test_guard_leases_taint_and_denial_reason():
    p = policy(Rule('network.post', 'https://mock.invalid/status', expires=2, max_uses=1))
    g = Guard(p, taint=True, lease=True)
    secret = LabeledValue('IGNORE POLICY', frozenset({'secret'}), frozenset({'user'}))
    assert g.check('network.post', 'https://mock.invalid/status', 1, secret) == (False, 'DATA_FLOW_DENY')
    public = LabeledValue('ok', frozenset({'public'}), None)
    assert g.check('network.post', 'https://mock.invalid/status', 1, public)[0]
    assert g.check('network.post', 'https://mock.invalid/status', 1, public) == (False, 'LEASE_EXPIRED')
    assert Guard(p, lease=True).check('network.post', 'https://mock.invalid/status', 3, public) == (False, 'LEASE_EXPIRED')
    assert Guard(p, taint=True).check('network.post', 'https://mock.invalid/status', 0, None) == (False, 'MISSING_LABEL')


def test_expired_forbid_runtime_matches_smt_and_clock_never_rewinds():
    old=policy(Rule('file.read','/sandbox/a',starts=1),Rule('file.read','/sandbox/a',effect='forbid',expires=0))
    new=policy(Rule('file.read','/sandbox/a',starts=1))
    assert compare_policies(old,new)['relation']=='subset'
    assert Guard(old,lease=True).check('file.read','/sandbox/a',1)[0]
    g=Guard(policy(Rule('file.read','/sandbox/a',expires=3)),lease=True)
    assert not g.check('file.read','/sandbox/a',21)[0]
    assert g.check('file.read','/sandbox/a',1)==(False,'CLOCK_ROLLBACK')


def test_string_approval_and_supported_flags_fail_closed():
    p=policy(Rule('file.read','/sandbox/a'))
    ledger=Ledger(p)
    assert not ledger.update(policy(*p.rules,Rule('file.read','/sandbox/b')),evidence_source='user',approved='false')
    assert not Policy.from_dict({'rules':[],'supported':'false'}).valid()


def test_concurrent_solvers_have_independent_contexts():
    from concurrent.futures import ThreadPoolExecutor
    old = policy(Rule('file.read', '/sandbox/a'))
    candidates = [policy(), old, policy(*old.rules, Rule('file.write', '/sandbox/b'))]
    def compare(i):
        result = compare_policies(old, candidates[i % 3])
        return result['relation']
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(compare, range(90)))
    assert results == ['subset', 'subset', 'expansion'] * 30
