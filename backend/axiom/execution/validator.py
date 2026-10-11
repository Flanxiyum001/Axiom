"""Experiment validator: deterministic pre-execution safety gate.

Rejects malformed or obviously dangerous ExperimentSpecs before they reach
the executor. This is a lightweight, AST-based validator - not a security
sandbox. Runtime containment remains the responsibility of LocalExecutor.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field

from axiom.domain.models import ExperimentSpec

logger = logging.getLogger("axiom.execution")

# Direct calls are checked only for dangerous builtins. Generic function names
# such as run() and call() are common in harmless experiment code.
_DANGEROUS_BUILTINS: frozenset[str] = frozenset(
    {"eval", "exec", "__import__", "compile"}
)

# Process-launching / filesystem modules are blocked at import time. This avoids
# simple import aliases bypassing attribute checks; this AST gate is not a sandbox.
_FORBIDDEN_MODULES: frozenset[str] = frozenset({"subprocess", "shutil"})
_SUBPROCESS_ATTRS: frozenset[str] = frozenset(
    {"Popen", "run", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}
)
_SHUTIL_DANGEROUS_ATTRS: frozenset[str] = frozenset({"rmtree"})
_OS_DANGEROUS_ATTRS: frozenset[str] = frozenset(
    {
        "system", "popen", "fork", "forkpty", "kill", "killpg", "startfile",
        "remove", "unlink", "rmdir", "removedirs", "rename", "replace",
        "truncate", "chmod", "chown",
    }
)
_BUILTINS_MODULE: str = "builtins"


@dataclass
class ValidationResult:
    """Explicit validation outcome - never a bare bool."""

    valid: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        """Single-line summary of the first rejection reason (or empty)."""
        return self.reasons[0] if self.reasons else ""


class ExperimentValidator:
    """Deterministic ExperimentSpec validator. No LLM calls."""

    def validate(self, spec: ExperimentSpec) -> ValidationResult:
        reasons: list[str] = []

        # --- Required fields ---
        if not spec.code or not spec.code.strip():
            reasons.append("code is empty or blank")
        if not spec.name or not spec.name.strip():
            reasons.append("name is empty or blank")
        if not isinstance(spec.parameters, dict):
            reasons.append(
                f"parameters must be a dict, got {type(spec.parameters).__name__}"
            )
        if not isinstance(spec.environment, dict):
            reasons.append(
                f"environment must be a dict, got {type(spec.environment).__name__}"
            )

        # If required fields are already broken, skip AST checks.
        if reasons:
            return ValidationResult(valid=False, reasons=reasons)

        # --- Code sanity: AST parse ---
        try:
            tree = ast.parse(spec.code, mode="exec")
        except SyntaxError as exc:
            msg = exc.msg or "syntax error"
            reasons.append(
                f"invalid Python source: {msg} (line {exc.lineno}, col {exc.offset})"
            )
            return ValidationResult(valid=False, reasons=reasons)

        # --- Dangerous execution patterns via AST ---
        dangerous = _scan_dangerous_calls(tree)
        if dangerous:
            for item in dangerous:
                reasons.append(
                    f"dangerous execution pattern detected: {item}"
                )

        if reasons:
            return ValidationResult(valid=False, reasons=reasons)

        return ValidationResult(valid=True)


def _scan_dangerous_calls(tree: ast.AST) -> list[str]:
    """Walk the AST and report dangerous calls and disallowed module imports.

    Import aliases are tracked so common alias forms do not evade checks. This
    is a defense-in-depth gate only; generated code must still run in a contained
    executor.
    """
    findings: list[str] = []
    # Collect aliases in a first pass so calls inside functions defined before
    # their imports are checked against the same module-level aliases.
    module_aliases: dict[str, str] = {}
    callable_aliases: dict[str, str] = {}
    for imported_node in ast.walk(tree):
        if isinstance(imported_node, ast.Import):
            for alias in imported_node.names:
                root_module = alias.name.split(".", 1)[0]
                module_aliases[alias.asname or root_module] = root_module
        elif isinstance(imported_node, ast.ImportFrom):
            root_module = (imported_node.module or "").split(".", 1)[0]
            if root_module in {"os", _BUILTINS_MODULE}:
                for alias in imported_node.names:
                    if alias.name == "*":
                        continue
                    local_name = alias.asname or alias.name
                    if root_module == "os" and _is_dangerous_os_attr(alias.name):
                        callable_aliases[local_name] = f"os.{alias.name}"
                    elif root_module == _BUILTINS_MODULE and alias.name in _DANGEROUS_BUILTINS:
                        callable_aliases[local_name] = f"{_BUILTINS_MODULE}.{alias.name}"

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.module_aliases: dict[str, str] = dict(module_aliases)
            self.callable_aliases: dict[str, str] = dict(callable_aliases)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                root_module = alias.name.split(".", 1)[0]
                local_name = alias.asname or root_module
                self.module_aliases[local_name] = root_module
                if root_module in _FORBIDDEN_MODULES:
                    example = "run" if root_module == "subprocess" else "rmtree"
                    findings.append(
                        f"{root_module} module import is blocked (for example {root_module}.{example})"
                    )
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            module = node.module or ""
            root_module = module.split(".", 1)[0]
            if root_module in _FORBIDDEN_MODULES:
                example = "run" if root_module == "subprocess" else "rmtree"
                findings.append(
                    f"{root_module} imports are blocked (for example {root_module}.{example})"
                )
            elif root_module in {"os", _BUILTINS_MODULE}:
                for alias in node.names:
                    if alias.name == "*":
                        findings.append(f"wildcard import from {root_module} is blocked")
                        continue
                    local_name = alias.asname or alias.name
                    if root_module == "os" and _is_dangerous_os_attr(alias.name):
                        self.callable_aliases[local_name] = f"os.{alias.name}"
                    elif root_module == _BUILTINS_MODULE and alias.name in _DANGEROUS_BUILTINS:
                        self.callable_aliases[local_name] = f"{_BUILTINS_MODULE}.{alias.name}"
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            self._check_call(node)
            self.generic_visit(node)

        def _resolve_module_name(self, base_name: str) -> str:
            return self.module_aliases.get(base_name, base_name)

        def _check_getattr(self, node: ast.Call) -> None:
            if len(node.args) < 2:
                return
            target, attribute = node.args[0], node.args[1]
            if not isinstance(attribute, ast.Constant) or not isinstance(attribute.value, str):
                return
            attr = attribute.value
            for base in _base_names(target):
                module = self._resolve_module_name(base)
                if module == "os" and _is_dangerous_os_attr(attr):
                    findings.append(f"getattr(os, {attr!r}) targets a dangerous function")
                elif module == "subprocess" and attr in _SUBPROCESS_ATTRS:
                    findings.append(f"getattr(subprocess, {attr!r}) targets a dangerous function")
                elif module == "shutil" and attr in _SHUTIL_DANGEROUS_ATTRS:
                    findings.append(f"getattr(shutil, {attr!r}) targets a dangerous function")
                elif module == _BUILTINS_MODULE and attr in _DANGEROUS_BUILTINS:
                    findings.append(f"getattr(builtins, {attr!r}) targets a dangerous function")

        def _check_call(self, node: ast.Call) -> None:
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in _DANGEROUS_BUILTINS:
                    findings.append(f"{func.id}() called directly")
                elif func.id in self.callable_aliases:
                    findings.append(f"{self.callable_aliases[func.id]}() called through an import alias")
                elif func.id == "getattr":
                    self._check_getattr(node)
                return

            if isinstance(func, ast.Attribute):
                attr = func.attr
                for base in _base_names(func.value):
                    module = self._resolve_module_name(base)
                    if module == "os" and _is_dangerous_os_attr(attr):
                        findings.append(f"os.{attr}() called")
                    elif module == "subprocess" and attr in _SUBPROCESS_ATTRS:
                        findings.append(f"subprocess.{attr}() called")
                    elif module == "shutil" and attr in _SHUTIL_DANGEROUS_ATTRS:
                        findings.append(f"shutil.{attr}() called")
                    elif module == _BUILTINS_MODULE and attr in _DANGEROUS_BUILTINS:
                        findings.append(f"builtins.{attr}() called")

    _Visitor().visit(tree)
    return list(dict.fromkeys(findings))


def _is_dangerous_os_attr(attr: str) -> bool:
    """Return whether an os attribute can launch processes or mutate files."""
    return (
        attr in _OS_DANGEROUS_ATTRS
        or attr.startswith("exec")
        or attr.startswith("spawn")
    )


def _base_names(node: ast.AST) -> list[str]:
    """Return the dotted module base names for an attribute chain.

    e.g. ``os.path.join`` -> ["os", "os.path"]
    """
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    names: list[str] = []
    acc = ""
    for p in reversed(parts):
        acc = p if not acc else f"{p}.{acc}"
        names.append(acc)
    return names