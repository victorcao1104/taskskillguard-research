"""Independent, non-enforcing AST reference for the finite Skill language.

Authored from design.md/plan.md without inspecting the production adapter or
runtime.  This module never executes Python source, opens a source-selected
host path, imports a source-selected module, or contacts a destination.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any


MAX_STEPS = 100


class ReferenceError(Exception):
    """A typed failure in the deliberately restricted reference language."""


def _fail(kind: str, detail: str) -> None:
    raise ReferenceError(f"{kind}: {detail}")


def _plain_call(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name


def _effect(node: ast.AST) -> str | None:
    if _plain_call(node, "emit"):
        return "emit"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if _plain_call(node.func.value, "Path"):
            return {"read_text": "read", "write_text": "write", "unlink": "delete"}.get(node.func.attr)
    return None


class _Language:
    def __init__(self, source: str, file: str):
        self.file = file
        try:
            self.tree = ast.parse(source, filename=file)
        except SyntaxError as exc:
            _fail("Unsupported", f"syntax at line {exc.lineno}: {exc.msg}")
        for node in ast.walk(self.tree):
            identifier = (node.id if isinstance(node, ast.Name)
                          else node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                          else node.arg if isinstance(node, ast.arg) else None)
            if identifier is not None and identifier.startswith("__tsg_"):
                _fail("Unsupported", "source identifiers beginning __tsg_ are reserved")
        self.functions: dict[str, ast.FunctionDef] = {}
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.name in self.functions or node.name in {"Path", "emit", "range"}:
                    _fail("Unsupported", f"duplicate or reserved helper name {node.name}")
                self.functions[node.name] = node
        last_declaration = max((index for index, node in enumerate(self.tree.body)
                                if isinstance(node, ast.FunctionDef)), default=-1)
        for node in self.tree.body[:last_declaration]:
            if not isinstance(node, ast.FunctionDef):
                if any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                       and child.func.id in self.functions for child in ast.walk(node)):
                    _fail("Unsupported", "module helper calls must follow all helper declarations")
        self.reserved = {"Path", "emit", "range", *self.functions}
        self.loop_variables = {node.target.id for node in ast.walk(self.tree)
                               if isinstance(node, ast.For) and isinstance(node.target, ast.Name)}
        self._statements(self.tree.body, top=True)
        edges = {name: {n.func.id for n in ast.walk(fn)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        and n.func.id in self.functions}
                 for name, fn in self.functions.items()}
        done: set[str] = set()

        def visit(name: str, visiting: set[str]) -> None:
            if name in visiting:
                _fail("Unsupported", "recursive helper call")
            if name not in done:
                for child in edges[name]:
                    visit(child, visiting | {name})
                done.add(name)

        for name in edges:
            visit(name, set())

    def _binding(self, target: ast.AST) -> None:
        if not isinstance(target, ast.Name) or target.id in self.reserved:
            _fail("Unsupported", "assignment target must be an unreserved variable")

    def _statements(self, nodes: list[ast.stmt], top: bool = False) -> None:
        for node in nodes:
            if isinstance(node, ast.ImportFrom):
                valid = top and node.level == 0 and len(node.names) == 1
                valid = valid and (node.module, node.names[0].name) in {
                    ("pathlib", "Path"), ("mock_tools", "emit")}
                valid = valid and node.names[0].asname is None
                if not valid:
                    _fail("Unsupported", "import outside the two declared mock APIs")
            elif isinstance(node, ast.FunctionDef):
                args = node.args
                if (not top or args.posonlyargs or args.args or args.kwonlyargs
                        or args.vararg or args.kwarg or args.defaults or args.kw_defaults
                        or node.decorator_list or node.returns or node.type_comment
                        or getattr(node, "type_params", [])):
                    _fail("Unsupported", "helpers must be top-level, zero-argument functions")
                self._statements(node.body)
            elif isinstance(node, ast.Assign):
                if len(node.targets) != 1 or node.type_comment:
                    _fail("Unsupported", "only single variable assignment is supported")
                self._binding(node.targets[0])
                self._expression(node.value)
            elif isinstance(node, ast.Expr):
                if not isinstance(node.value, ast.Call):
                    _fail("Unsupported", "expression statement must be a supported call")
                self._expression(node.value, helper_allowed=True)
            elif isinstance(node, ast.If):
                test = node.test
                if not (isinstance(test, ast.Compare) and len(test.ops) == 1
                        and isinstance(test.ops[0], ast.Eq) and len(test.comparators) == 1):
                    _fail("Unsupported", "conditions must compare two expressions with ==")
                self._expression(test.left)
                self._expression(test.comparators[0])
                self._statements(node.body)
                self._statements(node.orelse)
            elif isinstance(node, ast.For):
                self._binding(node.target)
                it = node.iter
                if (not _plain_call(it, "range") or len(it.args) != 1 or it.keywords
                        or not isinstance(it.args[0], ast.Constant)
                        or type(it.args[0].value) is not int or not 0 <= it.args[0].value <= 3
                        or node.orelse or node.type_comment):
                    _fail("Unsupported", "loops require range of one literal integer from 0 to 3")
                self._statements(node.body)
            else:
                _fail("Unsupported", f"statement {type(node).__name__} at line {node.lineno}")

    def _expression(self, node: ast.AST, helper_allowed: bool = False) -> None:
        if isinstance(node, ast.Constant) and type(node.value) in (str, int, bool):
            return
        if (isinstance(node, ast.Name) and node.id not in self.reserved
                and node.id not in self.loop_variables):
            return
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            self._expression(node.left)
            self._expression(node.right)
            return
        if isinstance(node, ast.Call) and not node.keywords:
            if isinstance(node.func, ast.Name):
                if node.func.id == "emit" and len(node.args) == 2:
                    for arg in node.args:
                        self._expression(arg)
                    return
                if helper_allowed and node.func.id in self.functions and not node.args:
                    return
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "upper" and not node.args:
                    self._expression(node.func.value)
                    return
                path = node.func.value
                op = _effect(node)
                if op and _plain_call(path, "Path") and len(path.args) == 1 and not path.keywords:
                    expected = 1 if op == "write" else 0
                    if len(node.args) == expected:
                        self._expression(path.args[0])
                        for arg in node.args:
                            self._expression(arg)
                        return
        _fail("Unsupported", f"expression {type(node).__name__} at line {getattr(node, 'lineno', '?')}")


@dataclass(frozen=True)
class _Value:
    data: str | int | bool
    origins: frozenset[str] = frozenset()

    def under(self, pc: frozenset[str]) -> "_Value":
        return _Value(self.data, self.origins | pc)


def _string(value: _Value, purpose: str) -> str:
    if type(value.data) is not str:
        _fail("TypeError", f"{purpose} requires a string")
    return value.data


class _Machine:
    def __init__(self, language: _Language, world: dict[str, Any], suppress: str | None):
        self.language = language
        self.files = dict(world.get("files", {}))
        self.initial = dict(self.files)
        self.readers = {key: frozenset(value) for key, value in world.get("readers", {}).items()}
        self.provenance = {key: frozenset({key}) if key in self.readers else frozenset()
                           for key in self.files}
        self.grants = {tuple(grant) for grant in world.get("grants", [])}
        self.limits = dict(world.get("limits", {}))
        self.attempts: dict[str, int] = {}
        self.suppress = suppress
        self.module: dict[str, _Value] = {}
        self.trace: list[dict[str, Any]] = []
        self.emits: list[dict[str, str]] = []
        self.steps = 0

    def _lookup(self, name: str, env: dict[str, _Value], locals_: set[str] | None) -> _Value:
        if name in env:
            return env[name]
        if locals_ is not None and name in locals_:
            _fail("UnboundLocalError", name)
        if name in self.module:
            return self.module[name]
        _fail("NameError", name)

    def block(self, nodes: list[ast.stmt], env: dict[str, _Value], pc: frozenset[str],
              locals_: set[str] | None = None) -> None:
        for node in nodes:
            if isinstance(node, (ast.ImportFrom, ast.FunctionDef)):
                continue
            self.steps += 1
            if self.steps > MAX_STEPS:
                _fail("StepLimit", f"more than {MAX_STEPS} executed statements")
            if isinstance(node, ast.Assign):
                env[node.targets[0].id] = self.expr(node.value, env, pc, locals_).under(pc)
            elif isinstance(node, ast.Expr):
                self.expr(node.value, env, pc, locals_)
            elif isinstance(node, ast.If):
                left = self.expr(node.test.left, env, pc, locals_)
                right = self.expr(node.test.comparators[0], env, pc, locals_)
                branch_pc = pc | left.origins | right.origins
                self.block(node.body if left.data == right.data else node.orelse,
                           env, branch_pc, locals_)
            elif isinstance(node, ast.For):
                for i in range(node.iter.args[0].value):
                    env[node.target.id] = _Value(i, pc)
                    self.block(node.body, env, pc, locals_)

    def expr(self, node: ast.AST, env: dict[str, _Value], pc: frozenset[str],
             locals_: set[str] | None) -> _Value:
        if isinstance(node, ast.Constant):
            return _Value(node.value)
        if isinstance(node, ast.Name):
            return self._lookup(node.id, env, locals_)
        if isinstance(node, ast.BinOp):
            left = self.expr(node.left, env, pc, locals_)
            right = self.expr(node.right, env, pc, locals_)
            return _Value(_string(left, "concatenation") + _string(right, "concatenation"),
                          left.origins | right.origins)
        if isinstance(node.func, ast.Name) and node.func.id in self.language.functions:
            fn = self.language.functions[node.func.id]
            bound = {n.targets[0].id for n in ast.walk(fn) if isinstance(n, ast.Assign)}
            bound |= {n.target.id for n in ast.walk(fn) if isinstance(n, ast.For)}
            self.block(fn.body, {}, pc, bound)
            return _Value("", pc)
        op = _effect(node)
        if op:
            site_id = f"{self.language.file}:{node.lineno}"
            # Suppression skips argument evaluation too: it is an intervention
            # on this effect site, not a dispatched operation or a new origin.
            if site_id == self.suppress:
                return _Value("", pc)
            if op == "emit":
                resource = self.expr(node.args[0], env, pc, locals_)
                value = self.expr(node.args[1], env, pc, locals_)
            else:
                resource = self.expr(node.func.value.args[0], env, pc, locals_)
                value = self.expr(node.args[0], env, pc, locals_) if op == "write" else _Value("")
            target = _string(resource, "resource")
            grant_key = f"{op}|{target}"
            self.attempts[grant_key] = self.attempts.get(grant_key, 0) + 1
            within_limit = (grant_key not in self.limits
                            or self.attempts[grant_key] <= self.limits[grant_key])
            origins = resource.origins | value.origins | pc
            if op == "read":
                if target not in self.files:
                    _fail("MissingFile", target)
                value = _Value(self.files[target],
                               self.provenance.get(target, frozenset()) | resource.origins | pc)
                origins = value.origins
            elif op == "write":
                self.files[target] = _string(value, "file value")
                self.provenance[target] = origins
            elif op == "delete":
                if target not in self.files:
                    _fail("MissingFile", target)
                del self.files[target]
                self.provenance.pop(target, None)
            elif op == "emit":
                self.emits.append({"resource": target, "value": _string(value, "emitted value")})
            flow_allowed = op != "emit" or all(target in self.readers[origin] for origin in origins)
            self.trace.append({"id": site_id, "op": op, "resource": target, "value": value.data,
                               "authorized": (op, target) in self.grants and within_limit,
                               "flow_allowed": flow_allowed, "origins": sorted(origins)})
            return value if op == "read" else _Value("", pc)
        # The validator has proved this is the one supported pure method.
        base = self.expr(node.func.value, env, pc, locals_)
        return _Value(_string(base, "upper").upper(), base.origins)


def _goal_satisfied(files: dict[str, str], emits: list[dict[str, str]],
                    initial: dict[str, str], goal: dict[str, Any]) -> bool:
    if any(files.get(path) != value for path, value in goal.get("files", {}).items()):
        return False
    if any(path in files for path in goal.get("absent", [])):
        return False
    if any(path not in initial or path not in files or files[path] != initial[path]
           for path in goal.get("preserve", [])):
        return False
    for requested in goal.get("emits", []):
        count = sum(event["resource"] == requested["resource"] and event["value"] == requested["value"]
                    for event in emits)
        if count != requested.get("count", 1):
            return False
    return True


def run(source: str, file: str, world: dict[str, Any], goal: dict[str, Any],
        suppress: str | None = None) -> dict[str, Any]:
    """Interpret source directly; unsafe effects remain visible in the trace.

    ``goal`` is the postcondition (not an assertion that prior effects were safe).
    The caller must separately inspect trace scope/flow labels. ``suppress`` is
    one ``file:line`` site: every visit to that site returns an empty string.
    Resource and payload values must be strings; integer/boolean constants do
    not imply Python's broader coercions or arithmetic. Comparisons with the
    reused Phase 6 language are eligible only when their value types agree.
    """
    machine: _Machine | None = None
    error = None
    try:
        language = _Language(source, file)
        machine = _Machine(language, world, suppress)
        machine.block(language.tree.body, machine.module, frozenset())
    except ReferenceError as exc:
        error = str(exc)
    initial = dict(world.get("files", {}))
    files = machine.files if machine else initial.copy()
    emits = machine.emits if machine else []
    trace = machine.trace if machine else []
    return {"files": files, "emits": emits, "trace": trace,
            "goal": error is None and _goal_satisfied(files, emits, initial, goal), "error": error}


def static_sites(source: str, file: str) -> list[dict[str, Any]]:
    """Return all syntactic effects, including unreachable helper/branch sites.

    Raises ReferenceError for unsupported source; it never invents a safe label
    for code outside this reference language.
    """
    language = _Language(source, file)
    return sorted(({"id": f"{file}:{node.lineno}", "op": _effect(node), "line": node.lineno,
                    "column": node.col_offset}
                   for node in ast.walk(language.tree) if _effect(node)),
                  key=lambda site: (site["line"], site["column"]))
