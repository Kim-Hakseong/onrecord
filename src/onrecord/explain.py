"""Rendering an adjudication back as the five rules that produced it.

The point of showing all five, always, is that the reader can see which rule the
field stopped at. A screen that only shows the verdict is asking to be trusted;
a screen that shows the rule trace is showing its work.
"""

from __future__ import annotations

from typing import Any

from .constants import RULE_COUNT
from .verdict import REASON_TEXT, LedgerRow, Reason, Verdict

RULE_NAMES: tuple[str, ...] = ("quote", "type", "authority", "compare", "verdict")

PASSED = "passed"
FAILED = "failed"
NOT_REACHED = "not_reached"


def rule_trace(row: LedgerRow) -> list[dict[str, Any]]:
    """Five entries, always. Never four, never six."""
    decided_at = row.rule if 1 <= row.rule <= RULE_COUNT else 1
    settled = row.verdict in (Verdict.CONFIRMED, Verdict.CONTRADICTED)

    trace: list[dict[str, Any]] = []
    for index, name in enumerate(RULE_NAMES, start=1):
        if index < decided_at:
            status, detail = PASSED, ""
        elif index == decided_at:
            status = PASSED if settled else FAILED
            detail = REASON_TEXT.get(row.reason, "")
        else:
            status, detail = NOT_REACHED, ""
        trace.append({"index": index, "rule": name, "status": status, "detail": detail})

    assert len(trace) == RULE_COUNT  # noqa: S101 - the contract this module exists for
    return trace


def rejected_span(row: LedgerRow) -> dict[str, Any] | None:
    """The discarded-claim line, when there is one to show."""
    if row.reason is not Reason.QUOTE_NOT_IN_TRANSCRIPT or not row.quote:
        return None
    return {
        "field": row.field,
        "claimed_quote": row.quote,
        "claimed_value": row.raw_value,
        "source": row.source,
        "detail": "not present in the transcript, so the value was discarded",
    }


def explain_row(row: LedgerRow) -> dict[str, Any]:
    data = row.as_dict()
    data["rule_trace"] = rule_trace(row)
    data["rejected_span"] = rejected_span(row)
    return data


def explain_stored_row(row: dict[str, Any]) -> dict[str, Any]:
    """Same, for a row read back out of SQLite."""
    from .store import _to_ledger_row

    ledger_row = _to_ledger_row(row)
    data = explain_row(ledger_row)
    data.update(
        {
            "seq": row.get("seq"),
            "call_id": row.get("call_id"),
            "subject_id": row.get("subject_id"),
            "schema_name": row.get("schema_name"),
            "created_at": row.get("created_at"),
        }
    )
    return data


#: Action-first ordering: what needs a human comes above what is settled.
VERDICT_ORDER = {
    Verdict.CONTRADICTED.value: 0,
    Verdict.NO_AUTHORITY.value: 1,
    Verdict.UNRESOLVED.value: 2,
    Verdict.CONFIRMED.value: 3,
}


def sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
    return (
        VERDICT_ORDER.get(row["verdict"], 9),
        str(row.get("subject_id", "")),
        str(row.get("field", "")),
    )


def verdict_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """All four, always -- a zero is a fact worth showing."""
    counts = {v.value: 0 for v in Verdict}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    return counts
