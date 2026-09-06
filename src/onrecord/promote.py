"""The requeue.

Every open field becomes a row here. There is no branch in this module that
drops a field on the floor -- if a field did not settle, it is either queued for
another attempt or explicitly marked EXHAUSTED, and both states are visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .constants import MAX_ATTEMPTS
from .verdict import LedgerRow, Verdict


class RequeueState(str, Enum):
    QUEUED = "QUEUED"
    EXHAUSTED = "EXHAUSTED"


@dataclass(frozen=True)
class RequeueItem:
    schema_name: str
    subject_id: str
    field: str
    state: RequeueState
    attempts: int
    reason: str
    verdict: str
    needs_different_respondent: bool = False
    source_call_id: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.state is RequeueState.QUEUED


def promote(
    rows: list[LedgerRow],
    *,
    schema_name: str,
    subject_id: str,
    attempts_so_far: dict[str, int] | None = None,
    source_call_id: str = "",
    max_attempts: int = MAX_ATTEMPTS,
) -> list[RequeueItem]:
    """Turn the open rows of one call into requeue items.

    `attempts_so_far` counts how many calls have already asked about each field,
    including the one that produced `rows`.
    """
    attempts_so_far = attempts_so_far or {}
    items: list[RequeueItem] = []
    for row in rows:
        if not row.is_open:
            continue
        attempts = attempts_so_far.get(row.field, 1)
        exhausted = attempts >= max_attempts
        items.append(
            RequeueItem(
                schema_name=schema_name,
                subject_id=subject_id,
                field=row.field,
                state=RequeueState.EXHAUSTED if exhausted else RequeueState.QUEUED,
                attempts=attempts,
                reason=row.reason.value,
                verdict=row.verdict.value,
                needs_different_respondent=row.verdict is Verdict.NO_AUTHORITY,
                source_call_id=source_call_id,
            )
        )
    return items


def next_attempt_fields(items: list[RequeueItem]) -> tuple[str, ...]:
    """Fields a follow-up call should ask about, in ledger order."""
    seen: dict[str, None] = {}
    for item in items:
        if item.is_actionable:
            seen.setdefault(item.field, None)
    return tuple(seen)


def requires_new_respondent(items: list[RequeueItem]) -> bool:
    """True when redialling the same person cannot possibly help."""
    actionable = [i for i in items if i.is_actionable]
    return bool(actionable) and all(i.needs_different_respondent for i in actionable)
