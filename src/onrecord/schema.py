"""Domain packs.

Every piece of domain knowledge ONRECORD has lives in a YAML file loaded here.
The adjudicator, the planner and the requeue never import this module's data --
they only receive `FieldSpec` objects. Swapping the YAML swaps the domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

import yaml

VALUE_TYPES = frozenset({"date", "bool", "enum", "int", "text"})


class SchemaError(ValueError):
    """Raised at load time only. Never raised during adjudication."""


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    required: bool = False
    authority: tuple[str, ...] = ()
    values: tuple[str, ...] = ()
    question_hint: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if self.type not in VALUE_TYPES:
            raise SchemaError(
                f"field {self.name!r}: unknown type {self.type!r} "
                f"(expected one of {sorted(VALUE_TYPES)})"
            )
        if self.type == "enum" and not self.values:
            raise SchemaError(f"field {self.name!r}: enum type requires 'values'")
        if not self.authority:
            raise SchemaError(
                f"field {self.name!r}: 'authority' is required -- a field nobody is "
                "allowed to commit to can never be confirmed"
            )


@dataclass(frozen=True)
class CallSchema:
    name: str
    title: str
    subject_label: str
    fields: tuple[FieldSpec, ...]
    roles: tuple[str, ...] = ()
    locale: str = "ko-KR"
    call_opening: str = ""
    source_path: Path | None = None
    known_value_labels: dict[str, str] = dataclass_field(default_factory=dict)

    def field(self, name: str) -> FieldSpec | None:
        for spec in self.fields:
            if spec.name == name:
                return spec
        return None

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(spec.name for spec in self.fields)


def load_schema(path: str | Path) -> CallSchema:
    path = Path(path)
    if not path.exists():
        raise SchemaError(f"schema not found: {path}")
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SchemaError(f"schema {path} must be a YAML mapping")
    return parse_schema(raw, source_path=path)


def parse_schema(raw: dict[str, Any], *, source_path: Path | None = None) -> CallSchema:
    try:
        raw_fields = raw["fields"]
    except KeyError as exc:  # pragma: no cover - defensive
        raise SchemaError("schema is missing 'fields'") from exc
    if not isinstance(raw_fields, list) or not raw_fields:
        raise SchemaError("'fields' must be a non-empty list")

    specs: list[FieldSpec] = []
    for entry in raw_fields:
        if not isinstance(entry, dict) or "name" not in entry:
            raise SchemaError(f"bad field entry: {entry!r}")
        specs.append(
            FieldSpec(
                name=str(entry["name"]),
                type=str(entry.get("type", "text")),
                required=bool(entry.get("required", False)),
                authority=tuple(str(r) for r in entry.get("authority", ()) or ()),
                values=tuple(str(v) for v in entry.get("values", ()) or ()),
                question_hint=str(entry.get("question_hint", "")),
                description=str(entry.get("description", "")),
            )
        )

    declared_roles = tuple(str(r) for r in raw.get("roles", ()) or ())
    if declared_roles:
        for spec in specs:
            unknown = [r for r in spec.authority if r not in declared_roles]
            if unknown:
                raise SchemaError(
                    f"field {spec.name!r}: authority roles {unknown} are not in "
                    f"the schema 'roles' list"
                )

    return CallSchema(
        name=str(raw.get("name") or (source_path.stem if source_path else "unnamed")),
        title=str(raw.get("title", "")),
        subject_label=str(raw.get("subject_label", "record")),
        fields=tuple(specs),
        roles=declared_roles,
        locale=str(raw.get("locale", "ko-KR")),
        call_opening=str(raw.get("call_opening", "")),
        source_path=source_path,
        known_value_labels={
            str(k): str(v) for k, v in (raw.get("known_value_labels") or {}).items()
        },
    )


def result_schema_for(schema: CallSchema, fields: tuple[FieldSpec, ...]) -> dict[str, Any]:
    """Build the JSON Schema handed to CALL-E's own extractor.

    CALL-E's output is treated as an untrusted claim source: it still has to
    survive the substring check before it can settle anything, so every field is
    optional and every enum carries an explicit `unknown` member.
    """
    properties: dict[str, Any] = {}
    for spec in fields:
        if spec.type == "enum":
            prop = {"type": "string", "enum": [*spec.values, "unknown"]}
        elif spec.type == "bool":
            prop = {"type": "string", "enum": ["yes", "no", "unknown"]}
        else:
            prop = {"type": "string"}
        prop["description"] = (
            spec.description or spec.question_hint or spec.name
        ) + " Use 'unknown' when the call did not settle this."
        properties[spec.name] = prop
    properties["respondent_role"] = {
        "type": "string",
        "enum": [*(schema.roles or ()), "unknown"],
        "description": "Role of the person who actually answered the call.",
    }
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
