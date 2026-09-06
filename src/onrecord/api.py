"""Read model for the three screens, plus the one button that places a call.

The API returns exactly what the screens render and nothing else. In particular
it never returns a call-level success flag, because there isn't one: the state of
a call is the set of verdicts it produced.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .calle_client import CalleNotConfigured
from .constants import (
    CALL_BUDGET,
    FIELD_COUNT,
    LIVE_CALL_FLOOR,
    PROJECT_NAME,
    RULE_COUNT,
    SCREEN_COUNT,
    TAGLINE,
    VERDICT_COUNT,
)
from .explain import explain_stored_row, sort_key, verdict_counts
from .paths import schema_dir
from .pipeline import MODE_LIVE, CallBudgetExhausted, run
from .planner import plan_call
from .promote import MAX_ATTEMPTS
from .schema import load_schema
from .seed import seed_store, subject as seed_subject
from .spanner import default_spanner
from .store import DEFAULT_DB_PATH, Store

SCHEMA_DIR = schema_dir()


class RunRequest(BaseModel):
    subject_id: str
    schema_name: str


def create_app(db_path: str | Path = DEFAULT_DB_PATH, schema_dir: str | Path = SCHEMA_DIR) -> FastAPI:
    db_path, schema_dir = Path(db_path), Path(schema_dir)
    app = FastAPI(title=f"{PROJECT_NAME} API", description=TAGLINE)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def store() -> Store:
        return Store(db_path)

    def schemas() -> list[str]:
        return sorted(p.stem for p in schema_dir.glob("*.yaml"))

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        with store() as s:
            used, remaining = s.calls_used(), s.calls_remaining()
        return {
            "project": PROJECT_NAME,
            "tagline": TAGLINE,
            "schemas": schemas(),
            "call_budget": CALL_BUDGET,
            "calls_used": used,
            "calls_remaining": remaining,
            "live_call_floor": LIVE_CALL_FLOOR,
            "verdict_count": VERDICT_COUNT,
            "screen_count": SCREEN_COUNT,
            "field_count": FIELD_COUNT,
            "rule_count": RULE_COUNT,
            "max_attempts": MAX_ATTEMPTS,
        }

    @app.get("/api/ledger")
    def ledger(schema: str | None = None, subject: str | None = None) -> dict[str, Any]:
        with store() as s:
            subjects = s.subjects(schema)
            wanted = {entry["id"] for entry in subjects}
            rows = [
                explain_stored_row(row)
                for row in s.ledger(subject)
                if row["subject_id"] in wanted
            ]
        current: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            current[(row["subject_id"], row["field"])] = row
        latest = sorted(current.values(), key=sort_key)
        return {
            "schema": schema,
            "subjects": subjects,
            "rows": latest,
            "history": rows,
            "counts": verdict_counts(latest),
        }

    @app.get("/api/calls")
    def calls(subject: str | None = None) -> list[dict[str, Any]]:
        with store() as s:
            return [
                {
                    "id": call["id"],
                    "subject_id": call["subject_id"],
                    "schema_name": call["schema_name"],
                    "attempt": call["attempt"],
                    "mode": call["mode"],
                    "asked_fields": call["asked_fields"],
                    "duration_seconds": call["duration_seconds"],
                    "end_reason": call["end_reason"],
                    "respondent_role": call["respondent_role"],
                    "created_at": call["created_at"],
                }
                for call in s.calls(subject)
            ]

    @app.get("/api/calls/{call_id}")
    def call_detail(call_id: str) -> dict[str, Any]:
        with store() as s:
            call = s.call(call_id)
            if call is None:
                raise HTTPException(status_code=404, detail=f"no such call: {call_id}")
            rows = [explain_stored_row(row) for row in s.ledger(call_id=call_id)]
        return {
            "call": call,
            "rows": sorted(rows, key=sort_key),
            "counts": verdict_counts(rows),
            "rejected_spans": [r["rejected_span"] for r in rows if r["rejected_span"]],
        }

    @app.get("/api/requeue")
    def requeue(schema: str | None = None) -> list[dict[str, Any]]:
        with store() as s:
            items = s.requeue()
            out: list[dict[str, Any]] = []
            grouped: dict[str, list[dict[str, Any]]] = {}
            for item in items:
                if schema and item["schema_name"] != schema:
                    continue
                grouped.setdefault(item["subject_id"], []).append(item)

            for subject_id, entries in sorted(grouped.items()):
                schema_name = entries[0]["schema_name"]
                try:
                    call_schema = load_schema(schema_dir / f"{schema_name}.yaml")
                    seeded = seed_subject(subject_id)
                except (FileNotFoundError, KeyError, OSError):
                    continue
                prior = s.current_ledger_rows(subject_id)
                actionable = [e for e in entries if e["state"] == "QUEUED"]
                plan = plan_call(
                    call_schema,
                    seeded.contact,
                    subject_id=subject_id,
                    prior_rows=prior,
                    known_values=seeded.known_values,
                    only=tuple(e["field"] for e in actionable) or None,
                    attempt=max(e["attempts"] for e in entries) + 1,
                )
                out.append(
                    {
                        "subject_id": subject_id,
                        "schema_name": schema_name,
                        "label": seeded.label,
                        "open": entries,
                        "dropped_from_goal": [
                            {
                                "field": row.field,
                                "verdict": row.verdict.value,
                                "value": row.value,
                            }
                            for row in prior
                            if not row.is_open
                        ],
                        "next_goal": plan.task,
                        "next_fields": list(plan.field_names),
                        "attempts": max(e["attempts"] for e in entries),
                        "max_attempts": MAX_ATTEMPTS,
                        "actionable": bool(actionable) and bool(plan.fields),
                        "needs_different_respondent": all(
                            e["needs_different_respondent"] for e in actionable
                        )
                        if actionable
                        else False,
                    }
                )
            return out

    @app.post("/api/requeue/run")
    def run_requeue(request: RunRequest) -> dict[str, Any]:
        """Place the follow-up call. Deliberate, because calls cost budget."""
        try:
            call_schema = load_schema(schema_dir / f"{request.schema_name}.yaml")
            seeded = seed_subject(request.subject_id)
        except (FileNotFoundError, KeyError, OSError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        with store() as s:
            seed_store(s)
            try:
                delta = run(
                    call_schema,
                    seeded.contact,
                    subject_id=request.subject_id,
                    known_values=seeded.known_values,
                    store=s,
                    mode=MODE_LIVE,
                    spanner=default_spanner(),
                )
            except CallBudgetExhausted as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except CalleNotConfigured as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return delta.summary()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
