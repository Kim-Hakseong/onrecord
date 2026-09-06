from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from onrecord.schema import CallSchema, FieldSpec, load_schema

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DATE = _dt.date(2026, 9, 1)


@pytest.fixture
def supplier_schema() -> CallSchema:
    return load_schema(REPO_ROOT / "schemas" / "supplier_delivery.yaml")


@pytest.fixture
def reference_schema() -> CallSchema:
    return load_schema(REPO_ROOT / "schemas" / "reference_check.yaml")


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
    return (
        "agent: 출고 날짜를 알려주시겠습니까?\n"
        "callee: 네, 영업 담당입니다. 9월 24일에 출고됩니다.\n"
        "agent: 감사합니다."
    )
