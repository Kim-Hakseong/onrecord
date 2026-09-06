"""Single source of truth for the numbers that appear in docs, UI and tests.

`tests/test_doc_consistency.py` asserts the README repeats these exact values,
so changing a number here is the only way to change it anywhere.
"""

from __future__ import annotations

# Free call allowance on a new CALL-E account. The whole sprint plan is sized
# against this number, and the dashboard shows the remaining count at all times.
CALL_BUDGET: int = 20

# CONFIRMED / CONTRADICTED / UNRESOLVED / NO_AUTHORITY. Never three.
VERDICT_COUNT: int = 4

# Ledger, Call Detail, Requeue. Never four.
SCREEN_COUNT: int = 3

# Fields declared by the primary demo schema (supplier_delivery).
FIELD_COUNT: int = 4

# Adjudication rules, applied in a fixed order.
RULE_COUNT: int = 5

# A field is retried at most this many times before it is EXHAUSTED.
MAX_ATTEMPTS: int = 2

# `--live` refuses to dial when fewer than this many calls remain; the
# remainder is reserved for demo-day filming.
LIVE_CALL_FLOOR: int = 3

PROJECT_NAME: str = "ONRECORD"
TAGLINE: str = "Phone calls that end in records, not summaries."
