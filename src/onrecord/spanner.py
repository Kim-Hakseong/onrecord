"""Span pointing -- the one and only place a model is used.

The model is not allowed to produce a value. It points at a span of the
transcript it believes commits to a field, and copies that span verbatim. The
adjudicator then checks that the span is really there. If the model paraphrases,
hallucinates, or points at nothing, the claim dies at rule 1 and the field falls
to UNRESOLVED -- which is why `tests/test_verdict_without_model.py` can run the
whole pipeline with the spanner switched off and still get a working ledger.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from .schema import CallSchema, FieldSpec
from .verdict import UNKNOWN_ROLE, Claim

DEFAULT_MODEL = "claude-haiku-4-5"
SOURCE = "spanner"

#: Set ONRECORD_NO_SPANNER=1 to run the pipeline with span pointing disabled.
DISABLE_ENV = "ONRECORD_NO_SPANNER"

SYSTEM_PROMPT = """\
You locate evidence in a phone-call transcript. You never decide anything.

For each requested field, find the single stretch of the transcript in which the
person being called commits to a value for it, and copy that stretch out
character for character. Copying is the whole job: a paraphrase, a translation,
a tidied-up version, or a span you assembled from two places is worse than
returning nothing, because a downstream check will search the transcript for
your text and throw the whole claim away when it is not found.

Rules you must follow:
- Quote verbatim from the transcript, including punctuation and spelling.
- Quote the callee, never the agent. The agent proposing a date is not a commitment.
- If the callee hedged ("probably", "let me check", "I think so"), that is not a
  commitment. Leave the field out.
- If a field never came up, leave it out. An empty answer is a correct answer.
- `value` is a normalized reading of the span you quoted, not your own inference.
- `respondent_role` is the role the callee stated or clearly identified as. Use
  "unknown" when nobody established it, and quote the words where they said it.
"""


class SpanPointer(Protocol):
    """Anything that can turn a transcript into claims."""

    def point(
        self, schema: CallSchema, fields: tuple[FieldSpec, ...], transcript: str
    ) -> "SpanResult": ...


@dataclass
class SpanResult:
    claims: list[Claim]
    respondent_role: str = UNKNOWN_ROLE
    respondent_quote: str = ""
    used_model: bool = False
    error: str = ""


class NullSpanner:
    """Points at nothing. The system stays correct, just uninformed."""

    def point(
        self, schema: CallSchema, fields: tuple[FieldSpec, ...], transcript: str
    ) -> SpanResult:
        return SpanResult(claims=[], used_model=False)


class HaikuSpanner:
    """Span pointing via the Anthropic Messages API with a forced JSON schema."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.max_tokens = max_tokens
        self._client: Any = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic  # imported at call time so --replay needs no key

            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def point(
        self, schema: CallSchema, fields: tuple[FieldSpec, ...], transcript: str
    ) -> SpanResult:
        """One call per transcript. Any failure degrades to zero claims."""
        if not transcript.strip() or not fields:
            return SpanResult(claims=[], used_model=False)
        try:
            response = self._get_client().messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                output_config={"format": {"type": "json_schema", "schema": output_schema(schema, fields)}},
                messages=[{"role": "user", "content": _prompt(schema, fields, transcript)}],
            )
        except Exception as exc:  # noqa: BLE001 - a dead model must not stop the pipeline
            return SpanResult(claims=[], used_model=False, error=f"{type(exc).__name__}: {exc}")

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return SpanResult(claims=[], used_model=True, error=f"unparseable output: {exc}")
        return result_from_payload(payload, fields)


def output_schema(schema: CallSchema, fields: tuple[FieldSpec, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "respondent_role": {
                "type": "string",
                "enum": [*(schema.roles or ()), UNKNOWN_ROLE],
                "description": "Role the callee stated for themselves.",
            },
            "respondent_quote": {
                "type": "string",
                "description": "Verbatim span where the callee identified their role. Empty if none.",
            },
            "fields": {
                "type": "array",
                "description": "One entry per field that was actually committed to. Omit the rest.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": [spec.name for spec in fields],
                        },
                        "value": {
                            "type": "string",
                            "description": "Normalized reading of the quoted span.",
                        },
                        "quote": {
                            "type": "string",
                            "description": "Verbatim transcript span. Copied, never rewritten.",
                        },
                    },
                    "required": ["name", "value", "quote"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["respondent_role", "respondent_quote", "fields"],
        "additionalProperties": False,
    }


def result_from_payload(payload: dict[str, Any], fields: tuple[FieldSpec, ...]) -> SpanResult:
    """Pure -- shared by the live spanner and the fixture tests."""
    known = {spec.name for spec in fields}
    claims: list[Claim] = []
    for entry in payload.get("fields") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", ""))
        if name not in known:
            continue
        claims.append(
            Claim(
                field=name,
                raw_value=str(entry.get("value", "")),
                quote=str(entry.get("quote", "")) or None,
                source=SOURCE,
            )
        )
    return SpanResult(
        claims=claims,
        respondent_role=str(payload.get("respondent_role", UNKNOWN_ROLE) or UNKNOWN_ROLE),
        respondent_quote=str(payload.get("respondent_quote", "") or ""),
        used_model=True,
    )


def _prompt(schema: CallSchema, fields: tuple[FieldSpec, ...], transcript: str) -> str:
    lines = ["Fields to locate:"]
    for spec in fields:
        detail = spec.description or spec.question_hint or spec.name
        line = f"- {spec.name} ({spec.type}): {' '.join(detail.split())}"
        if spec.type == "enum":
            line += f" Allowed values: {', '.join(spec.values)}."
        lines.append(line)
    lines.append("")
    lines.append(f"Roles that exist in this domain: {', '.join(schema.roles) or 'unknown'}")
    lines.append("")
    lines.append("Transcript:")
    lines.append("<transcript>")
    lines.append(transcript)
    lines.append("</transcript>")
    return "\n".join(lines)


class RecordedSpanner:
    """Replays a span-pointing result captured from a previous live call.

    This is what makes `--replay` work with no credentials: the recorded model
    output is checked against the transcript by exactly the same rules a live
    result would face, so a fixture whose quotes drifted fails the same way.
    """

    def __init__(self, payload: dict[str, Any] | None) -> None:
        self.payload = payload or {}

    def point(
        self, schema: CallSchema, fields: tuple[FieldSpec, ...], transcript: str
    ) -> SpanResult:
        if not self.payload:
            return SpanResult(claims=[], used_model=False)
        return result_from_payload(self.payload, fields)


def default_spanner() -> SpanPointer:
    """`NullSpanner` when disabled or unconfigured -- never a hard failure."""
    if os.environ.get(DISABLE_ENV) == "1":
        return NullSpanner()
    spanner = HaikuSpanner()
    return spanner if spanner.configured else NullSpanner()
