"""MCP wrapper.

The same pipeline the CLI drives, exposed as tools so an agent can use it
directly: plan a call, replay a recorded one, read the ledger, read the requeue,
and -- deliberately separate from everything else -- place a real call.

    uv run onrecord-mcp

Built against mcp 2.x (`MCPServer`). Placing a call is the only tool that spends
budget, and it refuses below the reserve rather than asking the caller to check.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import fixtures as fixture_lib
from .calle_client import CalleNotConfigured
from .constants import CALL_BUDGET, LIVE_CALL_FLOOR, TAGLINE
from .explain import explain_row, explain_stored_row, sort_key, verdict_counts
from .paths import schema_dir
from .pipeline import MODE_LIVE, MODE_REPLAY, CallBudgetExhausted, run
from .planner import plan_call
from .schema import load_schema
from .seed import SUBJECTS, seed_store, subject as seed_subject
from .spanner import default_spanner
from .store import DEFAULT_DB_PATH, Store

SCHEMA_DIR = schema_dir()

server = MCPServer(
    name="onrecord",
    instructions=(
        f"{TAGLINE}\n\n"
        "Adjudicates CALL-E phone calls field by field. Every field comes back as "
        "CONFIRMED, CONTRADICTED, UNRESOLVED or NO_AUTHORITY with the transcript "
        "span it came from. There is no call-level success flag; a call that "
        "settled nothing is a normal, representable outcome.\n\n"
        "Start with `plan_call_goal` or `replay_recorded_call` -- neither needs "
        "credentials. `place_call` spends real call budget and is the only tool "
        "that dials."
    ),
)


def _schema(name: str):
    path = SCHEMA_DIR / f"{name}.yaml"
    if not path.exists():
        # A ToolError reaches the model as a readable message it can act on.
        raise ToolError(f"unknown schema {name!r}; available: {list_schemas()}")
    return load_schema(path)


def _subject(subject_id: str):
    try:
        return seed_subject(subject_id)
    except KeyError as exc:
        raise ToolError(
            f"unknown subject {subject_id!r}; available: "
            f"{[entry.id for entry in SUBJECTS]}"
        ) from exc


def list_schemas() -> list[str]:
    return sorted(p.stem for p in SCHEMA_DIR.glob("*.yaml"))


@server.tool(
    description=(
        "List the domain packs and the subjects seeded for each. Call this first "
        "to find valid schema names and subject ids."
    )
)
def list_domains() -> dict[str, Any]:
    return {
        "schemas": list_schemas(),
        "subjects": [
            {
                "id": entry.id,
                "schema": entry.schema_name,
                "label": entry.label,
                "known_values": entry.known_values,
            }
            for entry in SUBJECTS
        ],
        "recorded_calls": [f.name for f in fixture_lib.load_all()],
    }


@server.tool(
    description=(
        "Show the exact task text CALL-E would be given for a subject, and which "
        "fields are still open. Places no call and needs no credentials."
    )
)
def plan_call_goal(schema_name: str, subject_id: str, db: str = str(DEFAULT_DB_PATH)) -> dict[str, Any]:
    call_schema = _schema(schema_name)
    entry = _subject(subject_id)
    with Store(db) as store:
        prior = store.current_ledger_rows(subject_id)
    plan = plan_call(
        call_schema,
        entry.contact,
        subject_id=subject_id,
        prior_rows=prior,
        known_values=entry.known_values,
    )
    return {
        "subject_id": subject_id,
        "open_fields": list(plan.field_names),
        "already_settled": [r.field for r in prior if not r.is_open],
        "task": plan.task,
    }


@server.tool(
    description=(
        "Adjudicate a recorded call by name and return one verdict per field with "
        "its quote and five-rule trace. No credentials, no call placed. This is "
        "the tool to use to understand what the adjudicator does."
    )
)
def replay_recorded_call(fixture_name: str, db: str = str(DEFAULT_DB_PATH)) -> dict[str, Any]:
    fixture = fixture_lib.by_name(fixture_name)
    call_schema = _schema(fixture.schema_name)
    entry = _subject(fixture.subject_id)
    with Store(db) as store:
        seed_store(store)
        delta = run(
            call_schema,
            entry.contact,
            subject_id=fixture.subject_id,
            known_values=entry.known_values,
            store=store,
            mode=MODE_REPLAY,
            outcome=fixture.outcome,
            spanner=fixture.spanner,
            reference_date=_dt.date(2026, 9, 1),
        )
    return {
        "summary": delta.summary(),
        "note": fixture.note,
        "transcript": delta.transcript,
        "rows": [explain_row(row) for row in delta.rows],
        "values_settled_without_a_quote": len(delta.confirmed_without_quote),
    }


@server.tool(
    description=(
        "Read the current verdict for every field of every subject, plus the "
        "count of each of the four verdicts."
    )
)
def read_ledger(subject_id: str | None = None, db: str = str(DEFAULT_DB_PATH)) -> dict[str, Any]:
    with Store(db) as store:
        rows = [explain_stored_row(r) for r in store.ledger(subject_id)]
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        latest[(row["subject_id"], row["field"])] = row
    current = sorted(latest.values(), key=sort_key)
    return {"rows": current, "counts": verdict_counts(current), "history_rows": len(rows)}


@server.tool(
    description=(
        "List the fields that did not settle and are waiting for another call, "
        "with the ones that are out of attempts marked EXHAUSTED."
    )
)
def read_requeue(subject_id: str | None = None, db: str = str(DEFAULT_DB_PATH)) -> list[dict[str, Any]]:
    with Store(db) as store:
        return store.requeue(subject_id)


@server.tool(
    description=(
        "Place a real phone call through CALL-E and adjudicate the result. "
        "SPENDS CALL BUDGET and requires CALLE_API_KEY. Refuses when fewer than "
        f"{LIVE_CALL_FLOOR} of the {CALL_BUDGET} calls remain."
    )
)
def place_call(schema_name: str, subject_id: str, db: str = str(DEFAULT_DB_PATH)) -> dict[str, Any]:
    call_schema = _schema(schema_name)
    entry = _subject(subject_id)
    with Store(db) as store:
        seed_store(store)
        try:
            delta = run(
                call_schema,
                entry.contact,
                subject_id=subject_id,
                known_values=entry.known_values,
                store=store,
                mode=MODE_LIVE,
                spanner=default_spanner(),
            )
        except CallBudgetExhausted as exc:
            return {"error": "call_budget_low", "detail": str(exc)}
        except CalleNotConfigured as exc:
            return {"error": "not_configured", "detail": str(exc)}
    return {
        "summary": delta.summary(),
        "rows": [explain_row(row) for row in delta.rows],
        "values_settled_without_a_quote": len(delta.confirmed_without_quote),
    }


@server.tool(description="How many of the free calls are left, and how many are reserved.")
def calls_remaining(db: str = str(DEFAULT_DB_PATH)) -> dict[str, int]:
    with Store(db) as store:
        return {
            "used": store.calls_used(),
            "remaining": store.calls_remaining(),
            "budget": CALL_BUDGET,
            "reserved": LIVE_CALL_FLOOR,
        }


def main() -> None:
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
