"""The adjudicator.

There is no model in this file and there never will be. It imports the standard
library and `onrecord.valuetypes`, nothing else. `tests/test_no_model_in_verdict.py`
walks this module's AST and fails the build if that changes.

Five rules, in a fixed order. The first one that fires decides the field:

    1. quote      -- the cited span must exist verbatim in the transcript
    2. type       -- the cited value must parse against the declared type
    3. authority  -- the respondent must be allowed to commit to this field
    4. contrast   -- a settled value that differs from what we believed is CONTRADICTED
    5. confirm    -- everything else that got this far is CONFIRMED

Rules 1 and 2 fall to UNRESOLVED, rule 3 falls to NO_AUTHORITY. No rule raises.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from .valuetypes import normalize, parse, render

if TYPE_CHECKING:  # pragma: no cover - keeps this module import-light at runtime
    from .schema import FieldSpec

UNKNOWN_ROLE = "unknown"


class Verdict(str, Enum):
    CONFIRMED = "CONFIRMED"
    CONTRADICTED = "CONTRADICTED"
    UNRESOLVED = "UNRESOLVED"
    NO_AUTHORITY = "NO_AUTHORITY"


#: Verdicts that leave the field open and therefore feed the requeue.
OPEN_VERDICTS: frozenset[Verdict] = frozenset({Verdict.UNRESOLVED, Verdict.NO_AUTHORITY})
#: Verdicts that settle the field and remove it from later call goals.
SETTLED_VERDICTS: frozenset[Verdict] = frozenset({Verdict.CONFIRMED, Verdict.CONTRADICTED})


class Reason(str, Enum):
    NO_CLAIM = "no_claim"
    QUOTE_MISSING = "quote_missing"
    QUOTE_NOT_IN_TRANSCRIPT = "quote_not_in_transcript"
    TYPE_PARSE_FAILED = "type_parse_failed"
    RESPONDENT_LACKS_AUTHORITY = "respondent_lacks_authority"
    CONFLICTING_CLAIMS = "conflicting_claims"
    DIFFERS_FROM_KNOWN_VALUE = "differs_from_known_value"
    QUOTED_AND_AUTHORIZED = "quoted_and_authorized"


REASON_TEXT: dict[Reason, str] = {
    Reason.NO_CLAIM: "No candidate span was offered for this field.",
    Reason.QUOTE_MISSING: "A value was offered with no supporting quote.",
    Reason.QUOTE_NOT_IN_TRANSCRIPT: "The cited span is not present in the transcript.",
    Reason.TYPE_PARSE_FAILED: "The cited span does not parse as the declared type.",
    Reason.RESPONDENT_LACKS_AUTHORITY: "The respondent is not allowed to commit to this field.",
    Reason.CONFLICTING_CLAIMS: "Two settled spans disagree on the value.",
    Reason.DIFFERS_FROM_KNOWN_VALUE: "Confirmed, and different from the value on record.",
    Reason.QUOTED_AND_AUTHORIZED: "Quoted verbatim and spoken by an authorized respondent.",
}


@dataclass(frozen=True)
class Claim:
    """A candidate value pointed at by some upstream extractor.

    `quote` is the extractor's assertion that this text appears in the
    transcript. The adjudicator checks that assertion; it does not trust it.
    """

    field: str
    raw_value: str
    quote: str | None = None
    source: str = "unknown"


@dataclass(frozen=True)
class Respondent:
    """Who actually answered. `role` is UNKNOWN_ROLE until proven otherwise."""

    role: str = UNKNOWN_ROLE
    quote: str | None = None


@dataclass(frozen=True)
class LedgerRow:
    field: str
    verdict: Verdict
    reason: Reason
    value: str = ""
    raw_value: str = ""
    quote: str = ""
    quote_start: int = -1
    quote_end: int = -1
    source: str = ""
    respondent_role: str = UNKNOWN_ROLE
    rule: int = 0
    known_value: str = ""

    @property
    def is_open(self) -> bool:
        return self.verdict in OPEN_VERDICTS

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "verdict": self.verdict.value,
            "reason": self.reason.value,
            "reason_text": REASON_TEXT[self.reason],
            "value": self.value,
            "raw_value": self.raw_value,
            "quote": self.quote,
            "quote_start": self.quote_start,
            "quote_end": self.quote_end,
            "source": self.source,
            "respondent_role": self.respondent_role,
            "rule": self.rule,
            "known_value": self.known_value,
        }


@dataclass
class _Evaluated:
    row: LedgerRow
    settled: bool = False


def locate_quote(transcript: str, quote: str | None) -> tuple[int, int]:
    """Return the span of `quote` inside `transcript`, or (-1, -1).

    Both sides are whitespace-normalized first, so the indices are valid against
    `valuetypes.normalize(transcript)` -- which is the form ONRECORD stores and
    the form the UI highlights.
    """
    if not quote:
        return -1, -1
    haystack = normalize(transcript)
    needle = normalize(quote)
    if not needle:
        return -1, -1
    start = haystack.find(needle)
    if start == -1:
        return -1, -1
    return start, start + len(needle)


def adjudicate_field(
    spec: "FieldSpec",
    claims: list[Claim],
    *,
    transcript: str,
    respondent: Respondent | None = None,
    known_value: str = "",
    reference_date: _dt.date | None = None,
) -> LedgerRow:
    """Adjudicate one field. Never raises."""
    respondent = respondent or Respondent()
    mine = [c for c in claims if c.field == spec.name]
    if not mine:
        return LedgerRow(
            field=spec.name,
            verdict=Verdict.UNRESOLVED,
            reason=Reason.NO_CLAIM,
            respondent_role=respondent.role,
            rule=1,
            known_value=known_value,
        )

    evaluated = [
        _evaluate_claim(
            spec,
            claim,
            transcript=transcript,
            respondent=respondent,
            known_value=known_value,
            reference_date=reference_date,
        )
        for claim in mine
    ]

    settled = [e for e in evaluated if e.settled]
    if settled:
        distinct = {e.row.value for e in settled}
        if len(distinct) > 1:
            first = settled[0].row
            return LedgerRow(
                field=spec.name,
                verdict=Verdict.UNRESOLVED,
                reason=Reason.CONFLICTING_CLAIMS,
                raw_value=first.raw_value,
                source=",".join(sorted({e.row.source for e in settled})),
                respondent_role=respondent.role,
                rule=4,
                known_value=known_value,
            )
        return settled[0].row

    for wanted in (Verdict.NO_AUTHORITY, Verdict.UNRESOLVED):
        for item in evaluated:
            if item.row.verdict is wanted:
                return item.row
    return evaluated[0].row  # pragma: no cover - the loop above is exhaustive


def _evaluate_claim(
    spec: "FieldSpec",
    claim: Claim,
    *,
    transcript: str,
    respondent: Respondent,
    known_value: str,
    reference_date: _dt.date | None,
) -> _Evaluated:
    base = {
        "field": spec.name,
        "raw_value": claim.raw_value,
        "source": claim.source,
        "respondent_role": respondent.role,
        "known_value": known_value,
    }

    # Rule 1 -- the quote must exist verbatim in the transcript.
    if not claim.quote:
        return _Evaluated(
            LedgerRow(verdict=Verdict.UNRESOLVED, reason=Reason.QUOTE_MISSING, rule=1, **base)
        )
    start, end = locate_quote(transcript, claim.quote)
    if start == -1:
        return _Evaluated(
            LedgerRow(
                verdict=Verdict.UNRESOLVED,
                reason=Reason.QUOTE_NOT_IN_TRANSCRIPT,
                quote=claim.quote,
                rule=1,
                **base,
            )
        )
    quoted = {"quote": normalize(claim.quote), "quote_start": start, "quote_end": end}

    # Rule 2 -- the value must parse against the declared type.
    ok, parsed = parse(
        spec.type, claim.raw_value, values=spec.values, reference=reference_date
    )
    if not ok:
        return _Evaluated(
            LedgerRow(
                verdict=Verdict.UNRESOLVED,
                reason=Reason.TYPE_PARSE_FAILED,
                rule=2,
                **quoted,
                **base,
            )
        )
    value = render(parsed)

    # Rule 3 -- authority beats a clear answer.
    if respondent.role not in spec.authority:
        return _Evaluated(
            LedgerRow(
                verdict=Verdict.NO_AUTHORITY,
                reason=Reason.RESPONDENT_LACKS_AUTHORITY,
                value=value,
                rule=3,
                **quoted,
                **base,
            )
        )

    # Rule 4 -- a settled value that differs from the record is CONTRADICTED.
    if known_value and normalize(known_value) != value:
        return _Evaluated(
            LedgerRow(
                verdict=Verdict.CONTRADICTED,
                reason=Reason.DIFFERS_FROM_KNOWN_VALUE,
                value=value,
                rule=4,
                **quoted,
                **base,
            ),
            settled=True,
        )

    # Rule 5 -- confirmed.
    return _Evaluated(
        LedgerRow(
            verdict=Verdict.CONFIRMED,
            reason=Reason.QUOTED_AND_AUTHORIZED,
            value=value,
            rule=5,
            **quoted,
            **base,
        ),
        settled=True,
    )


def adjudicate(
    fields: "tuple[FieldSpec, ...] | list[FieldSpec]",
    claims: list[Claim],
    *,
    transcript: str,
    respondent: Respondent | None = None,
    known_values: dict[str, str] | None = None,
    reference_date: _dt.date | None = None,
) -> list[LedgerRow]:
    """Adjudicate every field. One row per field, always. Nothing is dropped."""
    known_values = known_values or {}
    return [
        adjudicate_field(
            spec,
            claims,
            transcript=transcript,
            respondent=respondent,
            known_value=known_values.get(spec.name, "") or "",
            reference_date=reference_date,
        )
        for spec in fields
    ]


def establish_respondent(
    declared_roles: "tuple[str, ...] | list[str]",
    claimed_role: str | None,
    quote: str | None,
    *,
    transcript: str,
) -> Respondent:
    """A role only counts if it is declared by the schema and quoted in the call."""
    role = normalize(claimed_role or "").lower()
    if not role or role == UNKNOWN_ROLE or role not in {r.lower() for r in declared_roles}:
        return Respondent(role=UNKNOWN_ROLE, quote=None)
    start, _ = locate_quote(transcript, quote)
    if start == -1:
        return Respondent(role=UNKNOWN_ROLE, quote=None)
    return Respondent(role=role, quote=normalize(quote or ""))


__all__ = [
    "Claim",
    "LedgerRow",
    "OPEN_VERDICTS",
    "REASON_TEXT",
    "Reason",
    "Respondent",
    "SETTLED_VERDICTS",
    "UNKNOWN_ROLE",
    "Verdict",
    "adjudicate",
    "adjudicate_field",
    "establish_respondent",
    "locate_quote",
]
