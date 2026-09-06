from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from onrecord.paths import schema_dir
from onrecord.schema import CallSchema, FieldSpec, load_schema

REPO_ROOT = Path(__file__).resolve().parents[1]
# Resolved rather than hardcoded so the suite runs from the packaged plugin too,
# where the schemas live under examples/.
SCHEMA_DIR = schema_dir()
REFERENCE_DATE = _dt.date(2026, 9, 1)


@pytest.fixture
def supplier_schema() -> CallSchema:
    return load_schema(SCHEMA_DIR / "supplier_delivery.yaml")


@pytest.fixture
def reference_schema() -> CallSchema:
    return load_schema(SCHEMA_DIR / "reference_check.yaml")


@pytest.fixture
def date_field() -> FieldSpec:
    return FieldSpec(
        name="promised_ship_date",
        type="date",
        required=True,
        authority=("sales_rep", "account_manager"),
    )


@pytest.fixture
def transcript() -> str:
    """English, like the demo corpus: a reviewer has to be able to check that a
    highlighted quote really is in the transcript."""
    return (
        "agent: What date can you ship?\n"
        "callee: Yes, this is the sales rep. It ships on September 24th.\n"
        "agent: Thank you."
    )
