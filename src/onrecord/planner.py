"""Turns the set of still-open fields into a CALL-E task instruction.

No domain vocabulary lives here. Every noun the callee will hear comes from the
schema YAML; this module only decides *which* fields are still worth asking
about and arranges them into a numbered list.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import CallSchema, FieldSpec
from .verdict import SETTLED_VERDICTS, LedgerRow


@dataclass(frozen=True)
class Contact:
    phone: str
    name: str = ""
    org: str = ""
    role_hint: str = ""

    def describe(self) -> str:
        parts = [p for p in (self.name, self.org) if p]
        return " at ".join(parts) if parts else self.phone


@dataclass(frozen=True)
class CallPlan:
    schema_name: str
    subject_id: str
    contact: Contact
    fields: tuple[FieldSpec, ...]
    task: str
    attempt: int

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)


def settled_fields(rows: list[LedgerRow]) -> set[str]:
    """Field names that a previous call already settled."""
    return {row.field for row in rows if row.verdict in SETTLED_VERDICTS}


def open_fields(
    schema: CallSchema,
    prior_rows: list[LedgerRow] | None = None,
    *,
    only: tuple[str, ...] | None = None,
) -> tuple[FieldSpec, ...]:
    """Fields the next call still has to settle.

    A field that a prior call settled is dropped from the goal -- that is what
    makes the follow-up call shorter, and a shorter call is call budget back.
    """
    done = settled_fields(prior_rows or [])
    wanted = set(only) if only is not None else None
    return tuple(
        spec
        for spec in schema.fields
        if spec.name not in done and (wanted is None or spec.name in wanted)
    )


def build_task(
    schema: CallSchema,
    contact: Contact,
    fields: tuple[FieldSpec, ...],
    *,
    subject_id: str,
    known_values: dict[str, str] | None = None,
    attempt: int = 1,
) -> str:
    known_values = known_values or {}
    lines: list[str] = []
    if schema.call_opening:
        lines.append(" ".join(schema.call_opening.split()))
    lines.append(
        f"Call {contact.phone} about {schema.subject_label} {subject_id}"
        + (f" ({contact.describe()})." if contact.describe() != contact.phone else ".")
    )
    if attempt > 1:
        lines.append(
            "This is a follow-up call. Everything already settled has been removed "
            "from the list below -- ask only what remains, then end the call."
        )
    lines.append("")
    lines.append(
        "Before anything else, ask who you are speaking with and what their role is, "
        "and say their role back so it is captured on the line."
    )
    lines.append("")
    lines.append("Information to collect, in order:")
    for index, spec in enumerate(fields, start=1):
        hint = " ".join(spec.question_hint.split()) or spec.description or spec.name
        line = f"{index}. {spec.name} -- {hint}"
        label = schema.known_value_labels.get(spec.name)
        if label and known_values.get(spec.name):
            line += (
                f" Do not read the {label} out loud; ask them for their own number "
                "and only compare afterwards."
            )
        lines.append(line)
    lines.append("")
    lines.append(
        "Do not accept a vague answer as an answer. If they will not commit, say "
        "that is fine, record it as unresolved and move on to the next item."
    )
    return "\n".join(lines)


def plan_call(
    schema: CallSchema,
    contact: Contact,
    *,
    subject_id: str,
    prior_rows: list[LedgerRow] | None = None,
    known_values: dict[str, str] | None = None,
    only: tuple[str, ...] | None = None,
    attempt: int = 1,
) -> CallPlan:
    fields = open_fields(schema, prior_rows, only=only)
    return CallPlan(
        schema_name=schema.name,
        subject_id=subject_id,
        contact=contact,
        fields=fields,
        task=build_task(
            schema,
            contact,
            fields,
            subject_id=subject_id,
            known_values=known_values,
            attempt=attempt,
        ),
        attempt=attempt,
    )
