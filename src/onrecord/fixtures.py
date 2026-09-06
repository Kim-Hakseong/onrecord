"""Recorded calls.

A fixture bundles three things: the CALL-E payload for one call, the span
pointing result recorded alongside it, and the metadata needed to replay it
against the right schema and subject. Everything a reviewer needs to reproduce
an adjudication end to end lives in the file -- no API key, no network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .calle_client import CallOutcome, outcome_from_payload
from .paths import fixture_dir
from .spanner import RecordedSpanner


@dataclass(frozen=True)
class Fixture:
    name: str
    schema_name: str
    subject_id: str
    note: str
    call: dict[str, Any]
    spans: dict[str, Any]
    path: Path

    @property
    def outcome(self) -> CallOutcome:
        return outcome_from_payload(self.call)

    @property
    def spanner(self) -> RecordedSpanner:
        return RecordedSpanner(self.spans)


def load_fixture(path: str | Path) -> Fixture:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    meta = raw.get("meta", {})
    return Fixture(
        name=str(meta.get("scenario", path.stem)),
        schema_name=str(meta.get("schema", "")),
        subject_id=str(meta.get("subject_id", "")),
        note=str(meta.get("note", "")),
        call=raw.get("call", {}),
        spans=raw.get("spans", {}),
        path=path,
    )


def load_all(directory: str | Path | None = None) -> list[Fixture]:
    directory = Path(directory) if directory else fixture_dir()
    return [load_fixture(p) for p in sorted(directory.glob("*.json"))]


def by_name(name: str, directory: str | Path | None = None) -> Fixture:
    for fixture in load_all(directory):
        if fixture.name == name:
            return fixture
    raise KeyError(f"no fixture named {name!r} in {directory or fixture_dir()}")
