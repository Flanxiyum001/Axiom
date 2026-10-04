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

# Names of obviously dangerous callables that have no legitimate role in
# AXIOM experiments. Detected via AST inspection rather than string matching.
_DANGEROUS_NAMES: frozenset[str] = frozenset(
    {
        "system",
        "Popen",
        "run",
        "call",
        "check_call",
        "check_output",
        "rmtree",
        "eval",
        "exec",
        "__import__",
    }
)

# Subprocess module attribute names we flag.
_SUBPROCESS_ATTRS: frozenset[str] = frozenset(
    {"system", "Popen", "run", "call", "check_call", "check_output"}
)

# os / shutil module names we flag.
_OS_MODULE: str = "os"
_SHUTIL_MODULE: str = "shutil"


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
    """Walk the AST and return human-readable descriptions of dangerous calls."""
    findings: list[str] = []

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            self._check_call(node)
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            self.generic_visit(node)

        def _check_call(self, node: ast.Call) -> None:
            func = node.func

            # Direct name calls: eval(...), exec(...), __import__(...)
            if isinstance(func, ast.Name):
                if func.id in _DANGEROUS_NAMES:
                    findings.append(f"{func.id}() called directly")
                return

            # Attribute calls: os.system(...), subprocess.Popen(...), shutil.rmtree(...)
            if isinstance(func, ast.Attribute):
                value = func.value
                attr = func.attr
                # Resolve the base module name(s).
                base_names = _base_names(value)
                for base in base_names:
                    if base == _OS_MODULE and attr in _SUBPROCESS_ATTRS:
                        findings.append(f"os.{attr}() called")
                    elif base == _SHUTIL_MODULE and attr in _DANGEROUS_NAMES:
                        findings.append(f"shutil.{attr}() called")
                    elif base == "subprocess" and attr in _SUBPROCESS_ATTRS:
                        findings.append(f"subprocess.{attr}() called")
                    elif attr in _DANGEROUS_NAMES and base in {
                        "builtins",
                        "__builtin__",
                        "builtins",
                    }:
                        findings.append(f"{base}.{attr}() called")

    _Visitor().visit(tree)
    return findings


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