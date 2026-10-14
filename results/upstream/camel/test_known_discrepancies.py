"""Expected semantics probes for issues noticed during review. Failures are retained.

The workspace-policy probe executes the exact extracted method body because the
full AgentDojo package is deliberately not installed. It is NOT integration coverage.
"""
import ast
from pathlib import Path

from camel import security_policy as sp
from camel.capabilities import Capabilities, is_trusted, sources
from camel.interpreter.value import CaMeLStr
from camel.capabilities import get_all_readers
from camel.interpreter import interpreter as ip, namespace as ns, result
import pytest


def test_base_policy_should_allow_public_argument():
    public = CaMeLStr.from_raw("public", Capabilities.default(), ())
    assert isinstance(sp.base_security_policy("emit", {"text": public}, set()), sp.Allowed)


def test_trusted_set_argument_should_limit_trusted_sources():
    user_value = CaMeLStr.from_raw("user input", Capabilities.default(), ())
    assert not is_trusted(user_value, trusted_set={sources.SourceEnum.CaMeL})


@pytest.mark.parametrize("mode", [ip.MetadataEvalMode.NORMAL, ip.MetadataEvalMode.STRICT])
def test_list_should_preserve_direct_private_member_readers(mode):
    secret = CaMeLStr.from_raw("MOCK_SECRET", Capabilities(
        frozenset({sources.Tool("mock_document")}), frozenset({"alice@example.test"})), ())
    evaluated = ip.camel_eval(ast.parse("[secret]"), ns.Namespace.with_builtins({"secret": secret}), [], (),
        ip.EvalArgs(sp.NoSecurityPolicyEngine(), mode))
    assert isinstance(evaluated.result, result.Ok)
    assert get_all_readers(evaluated.result.value)[0] == frozenset({"alice@example.test"})


def test_delete_email_policy_should_allow_user_supplied_identifier():
    path = Path("src/camel/pipeline_elements/security_policies/workspace.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "WorkspaceSecurityPolicyEngine")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "delete_email_policy")
    method.returns = None
    for arg in method.args.args:
        arg.annotation = None
    scope = {"is_trusted": is_trusted, "Allowed": sp.Allowed, "Denied": sp.Denied}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), scope)
    identifier = CaMeLStr.from_raw("mock-email-1", Capabilities.default(), ())
    decision = scope["delete_email_policy"](None, "delete_email", {"email_id": identifier})
    assert isinstance(decision, sp.Allowed)
