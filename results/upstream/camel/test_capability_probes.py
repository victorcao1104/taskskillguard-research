"""Local, model-free audit probes; not part of upstream CaMeL tests."""
import ast
import pytest

from camel import security_policy as sp
from camel.capabilities import (
    Capabilities, can_readers_read_value, get_all_readers,
    get_all_sources, is_public, is_trusted, readers, sources,
)
from camel.interpreter import interpreter as ip, namespace as ns, result, value


class LocalTool(value.CaMeLCallable):
    def __init__(self, name, fn):
        self._name = name
        self._python_value = fn
        self._metadata = Capabilities.camel()
        self._dependencies = ()
        self._recv = None

    def make_args_by_keyword_preserve_values(self, args, kwargs):
        return dict(zip(("text",), args._python_value)) | {
            key.raw: item for key, item in kwargs._python_value.items()
        }


class LocalPolicy(sp.SecurityPolicyEngine):
    def __init__(self, rules=()):
        self.policies = list(rules)
        self.no_side_effect_tools = {"query_ai_assistant"}


def run(code, variables=None, mode=ip.MetadataEvalMode.NORMAL, policy=None):
    return ip.camel_eval(
        ast.parse(code), ns.Namespace.with_builtins(variables), [], (),
        ip.EvalArgs(policy or sp.NoSecurityPolicyEngine(), mode),
    )


def private_text(text="MOCK_SECRET", tool="mock_document"):
    return value.CaMeLStr.from_raw(
        text,
        Capabilities(frozenset({sources.Tool(tool)}), frozenset({"alice@example.test"})),
        (),
    )


def test_arithmetic_sources_union_and_readers_intersection():
    a = value.CaMeLInt(4, Capabilities(frozenset({sources.Tool("source_a")}),
        frozenset({"alice", "bob"})), ())
    b = value.CaMeLInt(5, Capabilities(frozenset({sources.Tool("source_b")}),
        frozenset({"alice", "carol"})), ())
    evaluated = run("a + b", {"a": a, "b": b})
    assert isinstance(evaluated.result, result.Ok)
    out = evaluated.result.value
    assert out.raw == 9
    assert get_all_readers(out)[0] == frozenset({"alice"})
    assert {sources.Tool("source_a"), sources.Tool("source_b")} <= get_all_sources(out)[0]


def test_string_transform_preserves_provenance_and_readers():
    evaluated = run("secret.lower()", {"secret": private_text()})
    assert isinstance(evaluated.result, result.Ok)
    out = evaluated.result.value
    assert out.raw == "mock_secret"
    assert not is_trusted(out)
    assert not is_public(out)
    assert can_readers_read_value({"alice@example.test"}, out)
    assert not can_readers_read_value({"mallory@example.test"}, out)


@pytest.mark.parametrize("mode,expected_public", [(ip.MetadataEvalMode.NORMAL, True), (ip.MetadataEvalMode.STRICT, False)])
def test_branch_assignment_modes(mode, expected_public):
    evaluated = run("if secret:\n    output = 'ok'\noutput", {"secret": private_text()}, mode)
    assert isinstance(evaluated.result, result.Ok)
    assert is_public(evaluated.result.value) is expected_public


@pytest.mark.parametrize("mode,expected_public", [(ip.MetadataEvalMode.NORMAL, True), (ip.MetadataEvalMode.STRICT, False)])
def test_mock_q_call_taints_later_assignment_only_in_strict(mode, expected_public):
    variables = {
        "secret": private_text(),
        "query_ai_assistant": LocalTool("query_ai_assistant", lambda text: "parsed"),
    }
    evaluated = run("parsed = query_ai_assistant(secret)\noutput = 'ok'\noutput", variables, mode)
    assert isinstance(evaluated.result, result.Ok)
    assert is_public(evaluated.result.value) is expected_public
    assert not is_public(evaluated.namespace.variables["parsed"])


@pytest.mark.parametrize("recipient,allowed", [("alice@example.test", True), ("mallory@example.test", False)])
def test_policy_checks_before_mock_side_effect(recipient, allowed):
    calls = []
    def policy(tool_name, kwargs):
        return sp.Allowed() if can_readers_read_value({recipient}, kwargs["text"]) else sp.Denied("recipient cannot read")
    variables = {"secret": private_text(), "emit": LocalTool("emit", lambda text: calls.append(text))}
    if allowed:
        evaluated = run("emit(secret)", variables, policy=LocalPolicy([("emit", policy)]))
        assert isinstance(evaluated.result, result.Ok)
        assert calls == ["MOCK_SECRET"]
    else:
        with pytest.raises(sp.SecurityPolicyDeniedError):
            run("emit(secret)", variables, policy=LocalPolicy([("emit", policy)]))
        assert calls == []


def test_unknown_external_tool_denied_without_invocation():
    calls = []
    with pytest.raises(sp.SecurityPolicyDeniedError):
        run("unknown('public')", {"unknown": LocalTool("unknown", lambda text: calls.append(text))}, policy=LocalPolicy())
    assert calls == []


def test_private_control_dependency_denies_even_public_arguments():
    calls = []
    with pytest.raises(sp.SecurityPolicyDeniedError):
        run("if secret:\n    emit('public')", {"secret": private_text(), "emit": LocalTool("emit", lambda text: calls.append(text))},
            policy=LocalPolicy([("emit", lambda *_: sp.Allowed())]))
    assert calls == []


def test_builtin_can_execute_without_external_tool_policy():
    evaluated = run("len([1, 2])", policy=LocalPolicy())
    assert isinstance(evaluated.result, result.Ok)
    assert evaluated.result.value.raw == 2


@pytest.mark.parametrize("code", ["import os", "while False:\n    pass", "f = lambda x: x", "eval('1 + 1')"])
def test_unsupported_language_rejected(code):
    evaluated = run(code)
    assert isinstance(evaluated.result, result.Error)


def test_first_matching_policy_wins():
    engine = LocalPolicy([("emit", lambda *_: sp.Denied("first")), ("emit", lambda *_: sp.Allowed())])
    assert engine.check_policy("emit", {}, ()) == sp.Denied("first")
