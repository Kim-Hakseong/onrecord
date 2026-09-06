"""The adjudicator must not be able to call a model, by construction.

This is checked with the AST rather than by reading the file, so that a model
client cannot sneak in via an alias, a conditional import, or a lazy import
inside a function.
"""

from __future__ import annotations

import ast
from pathlib import Path

VERDICT_PY = Path(__file__).resolve().parents[1] / "src" / "onrecord" / "verdict.py"

FORBIDDEN_ROOTS = {
    "anthropic",
    "openai",
    "httpx",
    "requests",
    "urllib",
    "http",
    "socket",
    "aiohttp",
    "google",
    "boto3",
    "onrecord.spanner",
    "onrecord.calle_client",
}

ALLOWED_ROOTS = {
    "__future__",
    "datetime",
    "dataclasses",
    "enum",
    "typing",
    "onrecord.valuetypes",
    "onrecord.schema",
}


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            roots.add(f"onrecord.{module.lstrip('.')}" if node.level else module)
    return roots


def _is_forbidden(module: str) -> bool:
    return any(module == f or module.startswith(f + ".") for f in FORBIDDEN_ROOTS)


def test_verdict_imports_no_model_or_network_client():
    roots = _imported_roots(ast.parse(VERDICT_PY.read_text(encoding="utf-8")))
    offenders = sorted(r for r in roots if _is_forbidden(r))
    assert not offenders, f"verdict.py must not import {offenders}"


def test_verdict_imports_nothing_unexpected():
    """An allowlist, so a new dependency has to be a deliberate edit to this test."""
    roots = _imported_roots(ast.parse(VERDICT_PY.read_text(encoding="utf-8")))
    assert roots <= ALLOWED_ROOTS, f"unexpected imports in verdict.py: {sorted(roots - ALLOWED_ROOTS)}"


def test_verdict_makes_no_inference_looking_calls():
    """`str.find` and `dict.get` are fine; `.messages.create(...)` is not.

    Only dotted chains are checked, because a bare `get`/`find` on a local is a
    standard-library call and flagging it would make this test noise.
    """
    tree = ast.parse(VERDICT_PY.read_text(encoding="utf-8"))
    chains: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = node.func.value
            if isinstance(base, ast.Attribute):
                chains.add(f"{base.attr}.{node.func.attr}")
            elif isinstance(base, ast.Name):
                chains.add(f"{base.id}.{node.func.attr}")
    forbidden = {
        "messages.create",
        "completions.create",
        "chat.create",
        "client.post",
        "client.request",
    }
    assert not chains & forbidden, f"verdict.py must not call {sorted(chains & forbidden)}"
