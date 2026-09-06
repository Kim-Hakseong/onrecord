"""Rendering an adjudication back as the five rules that produced it.

The point of showing all five, always, is that the reader can see which rule the
field stopped at. A screen that only shows the verdict is asking to be trusted;
a screen that shows the rule trace is showing its work.
"""

from __future__ import annotations

from typing import Any

from .constants import RULE_COUNT
from .valuetypes import normalize
from .verdict import REASON_TEXT, LedgerRow, Reason, Verdict

RULE_NAMES: tuple[str, ...] = ("quote", "type", "authority", "compare", "verdict")

PASSED = "passed"
FAILED = "failed"
NOT_REACHED = "not_reached"


def rule_trace(row: LedgerRow) -> list[dict[str, Any]]:
    """Five entries, always. Never four, never six.

    `decided` marks the rule that actually produced the verdict. Without it a
    CONTRADICTED field — settled at rule 4, so rule 5 never runs — renders as a
    row of ticks followed by a dash, which reads like the last step failed.
    """
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
        trace.append(
            {
                "index": index,
                "rule": name,
                "status": status,
                "detail": detail,
                "decided": index == decided_at,
            }
        )

    assert len(trace) == RULE_COUNT  # noqa: S101 - the contract this module exists for
    return trace


def transcript_lines(
    transcript: str,
    turns: list[dict[str, Any]],
    spans: list[tuple[int, int, str]] | None = None,
) -> list[dict[str, Any]]:
    """Rebuild the speaker-per-line view of a stored transcript.

    ONRECORD stores a transcript whitespace-normalised onto a single line,
    because that is the string quote offsets are measured against and the
    adjudicator must not have to care about layout. A screen does have to care:
    a wall of `agent: … callee: … agent: …` is unreadable, and the transcript is
    the evidence the whole product rests on.

    So the line structure is recovered here rather than stored twice. Each turn
    is located in the normalised string, and each turn's body is cut into
    segments against the confirmed quote spans, so the highlight the reader sees
    is the exact range the verdict was based on -- not a re-search of the text
    that might land somewhere else.

    Never raises. A turn that cannot be located still renders; it just carries
    no offsets and no highlight.
    """
    haystack = normalize(transcript)
    spans = sorted(spans or [])
    lines: list[dict[str, Any]] = []
    cursor = 0

    for turn in turns:
        speaker = str(turn.get("speaker", "unknown"))
        body = normalize(str(turn.get("text", "")))
        label = f"{speaker}:"
        rendered = f"{label} {body}" if body else label

        start = haystack.find(rendered, cursor)
        if start == -1:  # cursor drifted; try from the top before giving up
            start = haystack.find(rendered)
        if start == -1:
            lines.append(
                {
                    "speaker": speaker,
                    "text": body,
                    "offset_seconds": turn.get("offset_seconds"),
                    "start": -1,
                    "end": -1,
                    "segments": [{"text": body, "field": None}] if body else [],
                }
            )
            continue

        body_start = start + len(label) + 1
        body_end = body_start + len(body)
        cursor = start + len(rendered)
        lines.append(
            {
                "speaker": speaker,
                "text": body,
                "offset_seconds": turn.get("offset_seconds"),
                "start": start,
                "end": cursor,
                "segments": _segment(body, body_start, body_end, spans),
            }
        )

    return lines


def _segment(
    body: str, body_start: int, body_end: int, spans: list[tuple[int, int, str]]
) -> list[dict[str, Any]]:
    """Cut one turn's body into plain and quoted runs."""
    if not body:
        return []
    pieces: list[dict[str, Any]] = []
    cursor = body_start
    for start, end, field in spans:
        start, end = max(start, body_start), min(end, body_end)
        if start >= end or start < cursor:
            continue  # outside this turn, or overlapping one already emitted
        if start > cursor:
            pieces.append({"text": body[cursor - body_start : start - body_start], "field": None})
        pieces.append({"text": body[start - body_start : end - body_start], "field": field})
        cursor = end
    if cursor < body_end:
        pieces.append({"text": body[cursor - body_start :], "field": None})
    return pieces


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


def group_by_subject(
    rows: list[dict[str, Any]], subjects: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """One block per subject, most urgent subject first.

    Sorting the whole ledger by verdict alone puts the same order twice on the
    screen -- a subject appears at the top for its contradiction and again in the
    middle for what is still open, and the reader has to reassemble it. Grouping
    keeps a subject in one place; ranking the groups by their worst verdict keeps
    the action-first ordering the flat list was there for.
    """
    by_id = {entry["id"]: entry for entry in (subjects or [])}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("subject_id", "")), []).append(row)

    blocks: list[dict[str, Any]] = []
    for subject_id, subject_rows in grouped.items():
        ordered = sorted(subject_rows, key=sort_key)
        subject = by_id.get(subject_id, {})
        blocks.append(
            {
                "subject_id": subject_id,
                "label": subject.get("label", ""),
                "contact_name": subject.get("contact_name", ""),
                "contact_org": subject.get("contact_org", ""),
                "known_values": subject.get("known_values", {}),
                "rows": ordered,
                "counts": verdict_counts(ordered),
                "urgency": min(
                    (VERDICT_ORDER.get(r["verdict"], 9) for r in ordered), default=9
                ),
                "open_count": sum(
                    1
                    for r in ordered
                    if r["verdict"] in (Verdict.UNRESOLVED.value, Verdict.NO_AUTHORITY.value)
                ),
            }
        )

    blocks.sort(key=lambda block: (block["urgency"], block["subject_id"]))
    return blocks


def verdict_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """All four, always -- a zero is a fact worth showing."""
    counts = {v.value: 0 for v in Verdict}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    return counts
