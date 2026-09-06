"""The numbers in the README must be the numbers in the code.

A README that drifts from `constants.py` is the cheapest way to lose a
reviewer's trust, so the drift is a test failure rather than a proofreading
task.
"""

from __future__ import annotations

import re
from pathlib import Path

from onrecord.constants import (
    CALL_BUDGET,
    FIELD_COUNT,
    LIVE_CALL_FLOOR,
    RULE_COUNT,
    SCREEN_COUNT,
    VERDICT_COUNT,
)
from onrecord.schema import load_schema
from onrecord.verdict import Verdict

REPO_ROOT = Path(__file__).resolve().parents[1]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
# Line wrapping is a formatting choice; the numbers are not.
FLAT = re.sub(r"\s+", " ", README)


def test_readme_quotes_the_constants_verbatim():
    assert f"**{CALL_BUDGET}** free calls" in FLAT
    assert f"**{VERDICT_COUNT}** verdicts" in FLAT
    assert f"**{RULE_COUNT}** rules" in FLAT
    assert f"**{SCREEN_COUNT}**, no more" in FLAT
    assert f"Calls used: N / {CALL_BUDGET}" in FLAT
    assert f"The last {LIVE_CALL_FLOOR} are reserved" in FLAT


def test_the_readme_names_all_four_verdicts():
    for verdict in Verdict:
        assert f"`{verdict.value}`" in README


def test_the_primary_schema_declares_the_documented_field_count():
    schema = load_schema(REPO_ROOT / "schemas" / "supplier_delivery.yaml")
    assert len(schema.fields) == FIELD_COUNT


def test_the_readme_keeps_its_honesty_sections():
    assert "## What does not work yet" in README
    assert "re-enacted" in README.lower()
    assert "scripted, not captured from live calls" in README


def test_the_readme_claims_no_accuracy_percentage():
    """We report a false-positive count, never an accuracy rate."""
    body = README.split("## What does not work yet")[0]
    percentages = re.findall(r"\b\d{1,3}(?:\.\d+)?\s*%", body)
    assert percentages == ["100%"], percentages  # only the success-rate critique
    assert "Values that settled without a verbatim quote: 0" in README


def test_the_reproduction_commands_are_the_ones_that_exist():
    for command in (
        "uv sync",
        "uv run pytest -q",
        "uv run onrecord --replay --schema schemas/supplier_delivery.yaml",
        "uv run onrecord calls-remaining",
    ):
        assert command in README


def test_the_demo_script_states_the_re_enactment():
    script = (REPO_ROOT / "docs" / "demo-script.md").read_text(encoding="utf-8")
    assert "re-enacted" in script.lower()
    assert "Counterpart calls are re-enacted" in script
