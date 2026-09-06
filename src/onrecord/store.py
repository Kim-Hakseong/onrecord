"""SQLite persistence.

The ledger is append-only. There is no UPDATE statement against it anywhere in
this file, and `tests/test_ledger_append_only.py` greps the module to keep it
that way. A correction is a new row with a later sequence number, so the
provenance of a value you act on stays traceable to a call and a sentence.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .constants import CALL_BUDGET
from .promote import RequeueItem, RequeueState
from .verdict import LedgerRow, Reason, Verdict

DEFAULT_DB_PATH = Path("data/onrecord.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS subjects (
    id            TEXT PRIMARY KEY,
    schema_name   TEXT NOT NULL,
    label         TEXT NOT NULL DEFAULT '',
    contact_name  TEXT NOT NULL DEFAULT '',
    contact_phone TEXT NOT NULL DEFAULT '',
    contact_org   TEXT NOT NULL DEFAULT '',
    known_values  TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calls (
    id                TEXT PRIMARY KEY,
    schema_name       TEXT NOT NULL,
    subject_id        TEXT NOT NULL,
    attempt           INTEGER NOT NULL DEFAULT 1,
    mode              TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT '',
    task              TEXT NOT NULL DEFAULT '',
    asked_fields      TEXT NOT NULL DEFAULT '[]',
    transcript        TEXT NOT NULL DEFAULT '',
    turns             TEXT NOT NULL DEFAULT '[]',
    structured_result TEXT NOT NULL DEFAULT '{}',
    respondent_role   TEXT NOT NULL DEFAULT 'unknown',
    respondent_quote  TEXT NOT NULL DEFAULT '',
    duration_seconds  INTEGER NOT NULL DEFAULT 0,
    end_reason        TEXT NOT NULL DEFAULT '',
    provider_call_id  TEXT NOT NULL DEFAULT '',
    spanner_used      INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id         TEXT NOT NULL,
    schema_name     TEXT NOT NULL,
    subject_id      TEXT NOT NULL,
    field           TEXT NOT NULL,
    verdict         TEXT NOT NULL,
    reason          TEXT NOT NULL,
    value           TEXT NOT NULL DEFAULT '',
    raw_value       TEXT NOT NULL DEFAULT '',
    quote           TEXT NOT NULL DEFAULT '',
    quote_start     INTEGER NOT NULL DEFAULT -1,
    quote_end       INTEGER NOT NULL DEFAULT -1,
    source          TEXT NOT NULL DEFAULT '',
    respondent_role TEXT NOT NULL DEFAULT 'unknown',
    rule            INTEGER NOT NULL DEFAULT 0,
    known_value     TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requeue (
    seq                       INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_name               TEXT NOT NULL,
    subject_id                TEXT NOT NULL,
    field                     TEXT NOT NULL,
    state                     TEXT NOT NULL,
    attempts                  INTEGER NOT NULL DEFAULT 1,
    reason                    TEXT NOT NULL DEFAULT '',
    verdict                   TEXT NOT NULL DEFAULT '',
    needs_different_respondent INTEGER NOT NULL DEFAULT 0,
    source_call_id            TEXT NOT NULL DEFAULT '',
    created_at                TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ledger_subject_idx ON ledger (subject_id, field, seq);
CREATE INDEX IF NOT EXISTS requeue_subject_idx ON requeue (subject_id, field, seq);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CallRecord:
    id: str
    schema_name: str
    subject_id: str
    attempt: int = 1
    mode: str = "replay"
    status: str = ""
    task: str = ""
    asked_fields: tuple[str, ...] = ()
    transcript: str = ""
    turns: list[dict[str, Any]] | None = None
    structured_result: dict[str, Any] | None = None
    respondent_role: str = "unknown"
    respondent_quote: str = ""
    duration_seconds: int = 0
    end_reason: str = ""
    provider_call_id: str = ""
    spanner_used: bool = False


class Store:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- subjects ------------------------------------------------------------

    def upsert_subject(
        self,
        subject_id: str,
        *,
        schema_name: str,
        label: str = "",
        contact_name: str = "",
        contact_phone: str = "",
        contact_org: str = "",
        known_values: dict[str, str] | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO subjects (id, schema_name, label, contact_name, contact_phone,"
            " contact_org, known_values, created_at) VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET schema_name=excluded.schema_name,"
            " label=excluded.label, contact_name=excluded.contact_name,"
            " contact_phone=excluded.contact_phone, contact_org=excluded.contact_org,"
            " known_values=excluded.known_values",
            (
                subject_id,
                schema_name,
                label,
                contact_name,
                contact_phone,
                contact_org,
                json.dumps(known_values or {}, ensure_ascii=False),
                _now(),
            ),
        )
        self._conn.commit()

    def subject(self, subject_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM subjects WHERE id = ?", (subject_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["known_values"] = json.loads(data["known_values"])
        return data

    def subjects(self, schema_name: str | None = None) -> list[dict[str, Any]]:
        if schema_name:
            rows = self._conn.execute(
                "SELECT * FROM subjects WHERE schema_name = ? ORDER BY id", (schema_name,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM subjects ORDER BY id").fetchall()
        out = []
        for row in rows:
            data = dict(row)
            data["known_values"] = json.loads(data["known_values"])
            out.append(data)
        return out

    def known_values(self, subject_id: str) -> dict[str, str]:
        subject = self.subject(subject_id)
        return dict(subject["known_values"]) if subject else {}

    # -- calls ---------------------------------------------------------------

    def save_call(self, record: CallRecord) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO calls (id, schema_name, subject_id, attempt, mode,"
            " status, task, asked_fields, transcript, turns, structured_result,"
            " respondent_role, respondent_quote, duration_seconds, end_reason,"
            " provider_call_id, spanner_used, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                record.id,
                record.schema_name,
                record.subject_id,
                record.attempt,
                record.mode,
                record.status,
                record.task,
                json.dumps(list(record.asked_fields), ensure_ascii=False),
                record.transcript,
                json.dumps(record.turns or [], ensure_ascii=False),
                json.dumps(record.structured_result or {}, ensure_ascii=False),
                record.respondent_role,
                record.respondent_quote,
                record.duration_seconds,
                record.end_reason,
                record.provider_call_id,
                int(record.spanner_used),
                _now(),
            ),
        )
        self._conn.commit()

    def call(self, call_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        return _decode_call(row) if row else None

    def calls(self, subject_id: str | None = None) -> list[dict[str, Any]]:
        if subject_id:
            rows = self._conn.execute(
                "SELECT * FROM calls WHERE subject_id = ? ORDER BY created_at, rowid",
                (subject_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM calls ORDER BY created_at, rowid"
            ).fetchall()
        return [_decode_call(row) for row in rows]

    def calls_used(self) -> int:
        """Only live calls spend budget. Replayed calls are free."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM calls WHERE mode = 'live'"
        ).fetchone()
        return int(row["n"])

    def calls_remaining(self, budget: int = CALL_BUDGET) -> int:
        return max(0, budget - self.calls_used())

    def attempts_for(self, subject_id: str) -> dict[str, int]:
        """How many calls have asked about each field of this subject."""
        counts: dict[str, int] = {}
        for call in self.calls(subject_id):
            for name in call["asked_fields"]:
                counts[name] = counts.get(name, 0) + 1
        return counts

    # -- ledger (append-only) ------------------------------------------------

    def append_rows(
        self,
        rows: Iterable[LedgerRow],
        *,
        call_id: str,
        schema_name: str,
        subject_id: str,
    ) -> None:
        stamp = _now()
        self._conn.executemany(
            "INSERT INTO ledger (call_id, schema_name, subject_id, field, verdict, reason,"
            " value, raw_value, quote, quote_start, quote_end, source, respondent_role,"
            " rule, known_value, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    call_id,
                    schema_name,
                    subject_id,
                    row.field,
                    row.verdict.value,
                    row.reason.value,
                    row.value,
                    row.raw_value,
                    row.quote,
                    row.quote_start,
                    row.quote_end,
                    row.source,
                    row.respondent_role,
                    row.rule,
                    row.known_value,
                    stamp,
                )
                for row in rows
            ],
        )
        self._conn.commit()

    def ledger(
        self, subject_id: str | None = None, call_id: str | None = None
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        if subject_id:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        if call_id:
            clauses.append("call_id = ?")
            params.append(call_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM ledger{where} ORDER BY seq", params
        ).fetchall()
        return [dict(row) for row in rows]

    def current_rows(self, subject_id: str) -> list[dict[str, Any]]:
        """Latest ledger row per field. Earlier rows stay readable as history."""
        latest: dict[str, dict[str, Any]] = {}
        for row in self.ledger(subject_id):
            latest[row["field"]] = row
        return list(latest.values())

    def current_ledger_rows(self, subject_id: str) -> list[LedgerRow]:
        return [_to_ledger_row(row) for row in self.current_rows(subject_id)]

    # -- requeue -------------------------------------------------------------

    def append_requeue(self, items: Iterable[RequeueItem]) -> None:
        stamp = _now()
        self._conn.executemany(
            "INSERT INTO requeue (schema_name, subject_id, field, state, attempts, reason,"
            " verdict, needs_different_respondent, source_call_id, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    item.schema_name,
                    item.subject_id,
                    item.field,
                    item.state.value,
                    item.attempts,
                    item.reason,
                    item.verdict,
                    int(item.needs_different_respondent),
                    item.source_call_id,
                    stamp,
                )
                for item in items
            ],
        )
        self._conn.commit()

    def requeue(self, subject_id: str | None = None) -> list[dict[str, Any]]:
        """Current requeue state: the latest row per (subject, field).

        A field that a later call settled is dropped, because a settled field has
        no open row to answer for it.
        """
        if subject_id:
            rows = self._conn.execute(
                "SELECT * FROM requeue WHERE subject_id = ? ORDER BY seq", (subject_id,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM requeue ORDER BY seq").fetchall()
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            latest[(row["subject_id"], row["field"])] = dict(row)
        settled: set[tuple[str, str]] = set()
        for subject in {key[0] for key in latest}:
            for row in self.current_rows(subject):
                if row["verdict"] in (Verdict.CONFIRMED.value, Verdict.CONTRADICTED.value):
                    settled.add((subject, row["field"]))
        out = [item for key, item in latest.items() if key not in settled]
        out.sort(key=lambda r: (r["subject_id"], r["field"]))
        return out

    def open_requeue(self, subject_id: str | None = None) -> list[dict[str, Any]]:
        return [
            row
            for row in self.requeue(subject_id)
            if row["state"] == RequeueState.QUEUED.value
        ]


def _decode_call(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["asked_fields"] = json.loads(data["asked_fields"])
    data["turns"] = json.loads(data["turns"])
    data["structured_result"] = json.loads(data["structured_result"])
    data["spanner_used"] = bool(data["spanner_used"])
    return data


def _to_ledger_row(row: dict[str, Any]) -> LedgerRow:
    return LedgerRow(
        field=row["field"],
        verdict=Verdict(row["verdict"]),
        reason=Reason(row["reason"]),
        value=row["value"],
        raw_value=row["raw_value"],
        quote=row["quote"],
        quote_start=row["quote_start"],
        quote_end=row["quote_end"],
        source=row["source"],
        respondent_role=row["respondent_role"],
        rule=row["rule"],
        known_value=row["known_value"],
    )
