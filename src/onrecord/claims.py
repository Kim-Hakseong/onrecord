"""CALL-E's own extraction, treated as an untrusted claim source.

CALL-E returns a `structured_result` for the schema we hand it. That output is a
value with no provenance -- nothing ties it to a sentence anyone said. ONRECORD
does not throw it away and does not trust it either: it becomes a claim, and the
claim has to find its own quote.

These claims are built with no quote, deliberately. An extracted value with no
span behind it cannot settle a field, so a platform value only ever survives
when the span pointer independently found the sentence that supports it. What it
does earn is a row: the ledger shows the value CALL-E returned and says, in the
reason column, that nothing in the call backs it up. That row is the concrete
thing this project has to say about trusting platform extraction.

An earlier version tried to corroborate a platform value by searching the
transcript for its literal text. It was dropped: the match that fired in
practice was a bare `500` inside an unrelated sentence, which is a coincidence
dressed up as evidence.
"""

from __future__ import annotations

from typing import Any

from .schema import FieldSpec
from .valuetypes import is_unknown, normalize
from .verdict import Claim

SOURCE = "calle"
RESPONDENT_KEY = "respondent_role"


def claims_from_structured_result(
    structured_result: dict[str, Any] | None,
    fields: tuple[FieldSpec, ...],
) -> list[Claim]:
    structured_result = structured_result or {}
    claims: list[Claim] = []
    for spec in fields:
        if spec.name not in structured_result:
            continue
        raw = structured_result[spec.name]
        if raw is None or is_unknown(str(raw)):
            continue
        claims.append(Claim(field=spec.name, raw_value=str(raw), quote=None, source=SOURCE))
    return claims


def respondent_role_from_structured_result(
    structured_result: dict[str, Any] | None,
) -> str:
    value = (structured_result or {}).get(RESPONDENT_KEY)
    return normalize(str(value)).lower() if value else ""
