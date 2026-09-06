"""The public surface: `onrecord.run(...) -> LedgerDelta`.

Declare a schema, name a contact, say what you already believe. You get back one
verdict per field, the sentence each verdict came from, and the requeue rows for
everything that did not settle.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from dataclasses import dataclass, field as _field
from pathlib import Path
from typing import Any

from .calle_client import CalleClient, CallOutcome, outcome_from_payload
from .claims import (
    claims_from_structured_result,
    respondent_role_from_structured_result,
)
from .constants import CALL_BUDGET, LIVE_CALL_FLOOR
from .planner import CallPlan, Contact, plan_call
from .promote import RequeueItem, promote
from .schema import CallSchema, FieldSpec, result_schema_for
from .spanner import NullSpanner, SpanPointer, SpanResult, default_spanner
from .store import CallRecord, Store
from .valuetypes import normalize
from .verdict import (
    Claim,
    LedgerRow,
    Respondent,
    Verdict,
    adjudicate,
    establish_respondent,
)

MODE_LIVE = "live"
MODE_REPLAY = "replay"


class CallBudgetExhausted(RuntimeError):
    """Raised instead of dialing when the reserve would be spent."""


@dataclass
class LedgerDelta:
    """Everything one call changed."""

    call_id: str
    schema_name: str
    subject_id: str
    attempt: int
    mode: str
    asked_fields: tuple[str, ...]
    rows: list[LedgerRow] = _field(default_factory=list)
    requeue: list[RequeueItem] = _field(default_factory=list)
    respondent_role: str = "unknown"
    transcript: str = ""
    duration_seconds: int = 0
    end_reason: str = ""
    spanner_used: bool = False
    spanner_error: str = ""
    calls_remaining: int = CALL_BUDGET
    task: str = ""

    @property
    def settled(self) -> list[LedgerRow]:
        return [r for r in self.rows if not r.is_open]

    @property
    def open(self) -> list[LedgerRow]:
        return [r for r in self.rows if r.is_open]

    @property
    def confirmed_without_quote(self) -> list[LedgerRow]:
        """The false-positive counter. This list must always be empty."""
        return [
            r
            for r in self.rows
            if r.verdict in (Verdict.CONFIRMED, Verdict.CONTRADICTED) and not r.quote
        ]

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for row in self.rows:
            counts[row.verdict.value] = counts.get(row.verdict.value, 0) + 1
        return {
            "call_id": self.call_id,
            "subject_id": self.subject_id,
            "attempt": self.attempt,
            "mode": self.mode,
            "asked": list(self.asked_fields),
            "verdicts": counts,
            "requeued": [i.field for i in self.requeue if i.is_actionable],
            "exhausted": [i.field for i in self.requeue if not i.is_actionable],
            "calls_remaining": self.calls_remaining,
        }


def adjudicate_outcome(
    schema: CallSchema,
    fields: tuple[FieldSpec, ...],
    outcome: CallOutcome,
    *,
    known_values: dict[str, str] | None = None,
    spanner: SpanPointer | None = None,
    reference_date: _dt.date | None = None,
) -> tuple[list[LedgerRow], Respondent, SpanResult]:
    """Transcript in, verdicts out. No storage, no network beyond the spanner."""
    spanner = spanner or NullSpanner()
    transcript = normalize(outcome.transcript)
    span = spanner.point(schema, fields, transcript)

    claims: list[Claim] = list(span.claims)
    claims.extend(claims_from_structured_result(outcome.structured_result, fields))

    claimed_role = span.respondent_role or respondent_role_from_structured_result(
        outcome.structured_result
    )
    respondent = establish_respondent(
        schema.roles, claimed_role, span.respondent_quote, transcript=transcript
    )

    rows = adjudicate(
        fields,
        claims,
        transcript=transcript,
        respondent=respondent,
        known_values=known_values,
        reference_date=reference_date,
    )
    return rows, respondent, span


def run(
    schema: CallSchema,
    contact: Contact,
    *,
    subject_id: str,
    known_values: dict[str, str] | None = None,
    store: Store | None = None,
    mode: str = MODE_LIVE,
    outcome: CallOutcome | None = None,
    spanner: SpanPointer | None = None,
    calle: CalleClient | None = None,
    only: tuple[str, ...] | None = None,
    reference_date: _dt.date | None = None,
    call_budget: int = CALL_BUDGET,
) -> LedgerDelta:
    """Place (or replay) one call and record what it settled.

    `mode="live"` dials through CALL-E. `mode="replay"` takes a `CallOutcome` you
    already have and needs no credentials at all -- that is the mode a reviewer
    runs.
    """
    prior_rows = store.current_ledger_rows(subject_id) if store else []
    attempts = store.attempts_for(subject_id) if store else {}
    attempt = max(attempts.values(), default=0) + 1

    plan = plan_call(
        schema,
        contact,
        subject_id=subject_id,
        prior_rows=prior_rows,
        known_values=known_values,
        only=only,
        attempt=attempt,
    )

    if not plan.fields:
        return LedgerDelta(
            call_id="",
            schema_name=schema.name,
            subject_id=subject_id,
            attempt=attempt,
            mode=mode,
            asked_fields=(),
            calls_remaining=store.calls_remaining(call_budget) if store else call_budget,
            task=plan.task,
        )

    if mode == MODE_LIVE:
        outcome = _place(plan, schema, store, calle, call_budget)
    elif outcome is None:
        raise ValueError("replay mode needs a CallOutcome to replay")

    assert outcome is not None
    fields_asked = plan.fields
    rows, respondent, span = adjudicate_outcome(
        schema,
        fields_asked,
        outcome,
        known_values=known_values,
        spanner=spanner if spanner is not None else (default_spanner() if mode == MODE_LIVE else NullSpanner()),
        reference_date=reference_date,
    )

    call_id = outcome.call_id or f"local-{uuid.uuid4().hex[:12]}"
    attempts_after = dict(attempts)
    for name in plan.field_names:
        attempts_after[name] = attempts_after.get(name, 0) + 1

    items = promote(
        rows,
        schema_name=schema.name,
        subject_id=subject_id,
        attempts_so_far=attempts_after,
        source_call_id=call_id,
    )

    if store is not None:
        store.save_call(
            CallRecord(
                id=call_id,
                schema_name=schema.name,
                subject_id=subject_id,
                attempt=attempt,
                mode=mode,
                status=outcome.status,
                task=plan.task,
                asked_fields=plan.field_names,
                transcript=normalize(outcome.transcript),
                turns=outcome.turns,
                structured_result=outcome.structured_result,
                respondent_role=respondent.role,
                respondent_quote=respondent.quote or "",
                duration_seconds=outcome.duration_seconds,
                end_reason=outcome.end_reason,
                provider_call_id=outcome.provider_call_id,
                spanner_used=span.used_model,
            )
        )
        store.append_rows(
            rows, call_id=call_id, schema_name=schema.name, subject_id=subject_id
        )
        store.append_requeue(items)

    return LedgerDelta(
        call_id=call_id,
        schema_name=schema.name,
        subject_id=subject_id,
        attempt=attempt,
        mode=mode,
        asked_fields=plan.field_names,
        rows=rows,
        requeue=items,
        respondent_role=respondent.role,
        transcript=normalize(outcome.transcript),
        duration_seconds=outcome.duration_seconds,
        end_reason=outcome.end_reason,
        spanner_used=span.used_model,
        spanner_error=span.error,
        calls_remaining=store.calls_remaining(call_budget) if store else call_budget,
        task=plan.task,
    )


def _place(
    plan: CallPlan,
    schema: CallSchema,
    store: Store | None,
    calle: CalleClient | None,
    call_budget: int,
) -> CallOutcome:
    remaining = store.calls_remaining(call_budget) if store else call_budget
    if remaining <= LIVE_CALL_FLOOR:
        raise CallBudgetExhausted(
            f"CALL_BUDGET_LOW: {remaining} of {call_budget} calls left; "
            f"the last {LIVE_CALL_FLOOR} are reserved for demo day."
        )
    client = calle or CalleClient()
    return client.place_call(
        task=plan.task,
        phone=plan.contact.phone,
        result_schema=result_schema_for(schema, plan.fields),
        metadata={
            "onrecord_schema": schema.name,
            "onrecord_subject": plan.subject_id,
            "onrecord_attempt": str(plan.attempt),
        },
        locale=schema.locale,
    )


def load_outcome(path: str | Path) -> CallOutcome:
    """Read a stored CALL-E payload from disk. No key, no network."""
    import json

    return outcome_from_payload(json.loads(Path(path).read_text(encoding="utf-8")))


def outcome_from_call_row(row: dict[str, Any]) -> CallOutcome:
    """Rebuild an outcome from a `calls` row so stored calls can be re-adjudicated."""
    return CallOutcome(
        call_id=row["id"],
        status=row["status"],
        transcript=row["transcript"],
        turns=row["turns"],
        structured_result=row["structured_result"],
        duration_seconds=row["duration_seconds"],
        end_reason=row["end_reason"],
        provider_call_id=row["provider_call_id"],
    )
