"""Where the schemas and recorded calls live.

This exists because the same code ships in two shapes: this repository, where
schemas sit in `schemas/` and recorded calls in `fixtures/`, and the packaged
plugin, where the contribution template puts both under `examples/`. Rather
than maintain a second copy of either, the lookup handles both layouts and takes
an environment override for anything else.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_ENV = "ONRECORD_SCHEMA_DIR"
FIXTURE_ENV = "ONRECORD_FIXTURE_DIR"

_SCHEMA_CANDIDATES = ("schemas", "examples")
_FIXTURE_CANDIDATES = ("fixtures", "examples/recorded-calls")


def _resolve(env_var: str, candidates: tuple[str, ...], default: str) -> Path:
    override = os.environ.get(env_var)
    if override:
        return Path(override)
    for root in (Path.cwd(), PACKAGE_ROOT):
        for candidate in candidates:
            path = root / candidate
            if path.is_dir():
                return path
    return PACKAGE_ROOT / default


def schema_dir() -> Path:
    return _resolve(SCHEMA_ENV, _SCHEMA_CANDIDATES, "schemas")


def fixture_dir() -> Path:
    return _resolve(FIXTURE_ENV, _FIXTURE_CANDIDATES, "fixtures")
