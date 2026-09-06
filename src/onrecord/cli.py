"""Command line entry point."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from . import fixtures as fixture_lib
from .calle_client import CalleClient, CalleNotConfigured
from .constants import CALL_BUDGET, LIVE_CALL_FLOOR
from .pipeline import MODE_LIVE, MODE_REPLAY, CallBudgetExhausted, LedgerDelta, run
from .planner import Contact, plan_call
from .schema import load_schema
from .seed import SUBJECTS, seed_store, subject as seed_subject
from .spanner import NullSpanner, default_spanner
from .store import DEFAULT_DB_PATH, Store
from .verdict import REASON_TEXT, Reason, Verdict

BADGE = {
    Verdict.CONFIRMED.value: "\033[32mCONFIRMED   \033[0m",
    Verdict.CONTRADICTED.value: "\033[35mCONTRADICTED\033[0m",
    Verdict.UNRESOLVED.value: "\033[33mUNRESOLVED  \033[0m",
    Verdict.NO_AUTHORITY.value: "\033[31mNO_AUTHORITY\033[0m",
}

DEFAULT_SCHEMA = Path("schemas/supplier_delivery.yaml")
REPLAY_DB = Path("data/replay.db")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="onrecord",
        description="Field-level adjudication for CALL-E calls.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["calls-remaining", "seed", "ledger", "requeue", "dump-fixture", "serve"],
        help="optional subcommand; omit it and use --replay / --dry-run / --live",
    )
    parser.add_argument("args", nargs="*", help="arguments for the subcommand")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="path to a schema YAML")
    parser.add_argument("--db", default=None, help="SQLite path (default data/onrecord.db)")
    parser.add_argument("--subject", default=None, help="subject id, e.g. PO-1041")
    parser.add_argument("--replay", action="store_true", help="adjudicate recorded calls; no credentials needed")
    parser.add_argument("--dry-run", action="store_true", help="print the CALL-E task text and stop")
    parser.add_argument("--live", action="store_true", help="place a real call through CALL-E")
    parser.add_argument("--phone", default=None, help="override the contact phone for --live")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--demo", action="store_true", help="seed: load the demo subjects")
    parser.add_argument("--reset", action="store_true", help="delete the database before running")
    parser.add_argument("--host", default="127.0.0.1", help="serve: bind host")
    parser.add_argument("--port", type=int, default=8787, help="serve: bind port")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "serve":
        return _serve(args)
    if args.command == "calls-remaining":
        return _calls_remaining(args)
    if args.command == "seed":
        return _seed(args)
    if args.command == "ledger":
        return _ledger(args)
    if args.command == "requeue":
        return _requeue(args)
    if args.command == "dump-fixture":
        return _dump_fixture(args)

    if args.dry_run:
        return _dry_run(args)
    if args.replay:
        return _replay(args)
    if args.live:
        return _live(args)

    build_parser().print_help()
    print("\nStart here:  uv run onrecord --replay --schema schemas/supplier_delivery.yaml")
    return 0


# -- modes -------------------------------------------------------------------


def _dry_run(args: argparse.Namespace) -> int:
    schema = load_schema(args.schema)
    subject_id = args.subject or _first_subject_for(schema.name)
    entry = seed_subject(subject_id)
    contact = entry.contact if args.phone is None else Contact(phone=args.phone, name=entry.contact.name, org=entry.contact.org)
    plan = plan_call(
        schema,
        contact,
        subject_id=subject_id,
        known_values=entry.known_values,
    )
    if args.json:
        print(json.dumps({"subject": subject_id, "fields": list(plan.field_names), "task": plan.task}, ensure_ascii=False, indent=2))
        return 0
    print(f"schema   : {schema.name} ({schema.title})")
    print(f"subject  : {subject_id} -- {entry.label}")
    print(f"contact  : {contact.describe()} {contact.phone}")
    print(f"asking   : {', '.join(plan.field_names)}")
    print("\n--- CALL-E task ---")
    print(plan.task)
    print("--- end ---\nNo call was placed.")
    return 0


def _replay(args: argparse.Namespace) -> int:
    schema = load_schema(args.schema)
    db_path = Path(args.db) if args.db else REPLAY_DB
    if db_path.exists() and (args.reset or args.db is None):
        db_path.unlink()

    selected = [f for f in fixture_lib.load_all() if f.schema_name == schema.name]
    if args.subject:
        selected = [f for f in selected if f.subject_id == args.subject]
    if not selected:
        print(f"no recorded calls for schema {schema.name!r}", file=sys.stderr)
        return 1

    deltas: list[LedgerDelta] = []
    with Store(db_path) as store:
        seed_store(store)
        for fixture in selected:
            entry = seed_subject(fixture.subject_id)
            delta = run(
                schema,
                entry.contact,
                subject_id=fixture.subject_id,
                known_values=entry.known_values,
                store=store,
                mode=MODE_REPLAY,
                outcome=fixture.outcome,
                spanner=fixture.spanner,
                reference_date=_dt.date(2026, 9, 1),
            )
            deltas.append(delta)
            if not args.json:
                _print_delta(fixture.name, fixture.note, delta)

    leaks = [row for d in deltas for row in d.confirmed_without_quote]
    if args.json:
        print(json.dumps([d.summary() for d in deltas], ensure_ascii=False, indent=2))
    else:
        print(f"\n{len(selected)} recorded calls replayed with no credentials.")
        print(f"values settled without a verbatim quote: {len(leaks)}")
    return 1 if leaks else 0


def _live(args: argparse.Namespace) -> int:
    schema = load_schema(args.schema)
    subject_id = args.subject or _first_subject_for(schema.name)
    entry = seed_subject(subject_id)
    contact = entry.contact if args.phone is None else Contact(phone=args.phone, name=entry.contact.name, org=entry.contact.org)
    with Store(args.db or DEFAULT_DB_PATH) as store:
        seed_store(store)
        remaining = store.calls_remaining()
        if remaining <= LIVE_CALL_FLOOR:
            print(f"CALL_BUDGET_LOW: {remaining}", file=sys.stderr)
            return 2
        try:
            delta = run(
                schema,
                contact,
                subject_id=subject_id,
                known_values=entry.known_values,
                store=store,
                mode=MODE_LIVE,
                spanner=default_spanner(),
            )
        except CalleNotConfigured as exc:
            print(f"{exc}\nTry:  uv run onrecord --replay --schema {args.schema}", file=sys.stderr)
            return 2
        except CallBudgetExhausted as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if args.json:
        print(json.dumps(delta.summary(), ensure_ascii=False, indent=2))
    else:
        _print_delta("live", "", delta)
    return 0


# -- subcommands -------------------------------------------------------------


def _calls_remaining(args: argparse.Namespace) -> int:
    with Store(args.db or DEFAULT_DB_PATH) as store:
        used, remaining = store.calls_used(), store.calls_remaining()
    if args.json:
        print(json.dumps({"used": used, "remaining": remaining, "budget": CALL_BUDGET}))
    else:
        print(f"Calls used: {used} / {CALL_BUDGET}   (remaining {remaining}, reserve {LIVE_CALL_FLOOR})")
    return 0


def _seed(args: argparse.Namespace) -> int:
    path = Path(args.db or DEFAULT_DB_PATH)
    if args.reset and path.exists():
        path.unlink()
    with Store(path) as store:
        count = seed_store(store)
    print(f"seeded {count} subjects into {path}")
    return 0


def _ledger(args: argparse.Namespace) -> int:
    with Store(args.db or DEFAULT_DB_PATH) as store:
        rows = store.ledger(args.subject)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("ledger is empty; run `onrecord --replay` first")
        return 0
    for row in rows:
        badge = BADGE.get(row["verdict"], row["verdict"])
        # Only a span that was actually found in the call reads as evidence.
        quote = f'  "{row["quote"]}"' if row["quote_start"] >= 0 else ""
        print(f'{row["subject_id"]:<10} {row["field"]:<22} {badge} {row["value"] or "-":<14}{quote}')
    return 0


def _requeue(args: argparse.Namespace) -> int:
    with Store(args.db or DEFAULT_DB_PATH) as store:
        rows = store.requeue(args.subject)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("requeue is empty")
        return 0
    for row in rows:
        marker = "->" if row["state"] == "QUEUED" else "x "
        extra = " (needs a different respondent)" if row["needs_different_respondent"] else ""
        reason = REASON_TEXT.get(Reason(row["reason"]), row["reason"])
        print(f'{marker} {row["subject_id"]:<10} {row["field"]:<22} {row["state"]:<10} attempt {row["attempts"]}  {reason}{extra}')
    return 0


def _dump_fixture(args: argparse.Namespace) -> int:
    """Write a stored call back out as a fixture bundle."""
    if not args.args:
        print("usage: onrecord dump-fixture <call_id> [out.json]", file=sys.stderr)
        return 2
    call_id = args.args[0]
    out = Path(args.args[1]) if len(args.args) > 1 else Path(f"fixtures/{call_id}.json")
    with Store(args.db or DEFAULT_DB_PATH) as store:
        call = store.call(call_id)
    if call is None:
        print(f"no such call: {call_id}", file=sys.stderr)
        return 1
    bundle = {
        "meta": {
            "scenario": call_id,
            "schema": call["schema_name"],
            "subject_id": call["subject_id"],
            "note": "Dumped from a stored call.",
        },
        "call": {
            "id": call["id"],
            "object": "call_task",
            "status": call["status"],
            "task": call["task"],
            "structured_result": call["structured_result"],
            "recipients": [
                {
                    "id": f"rcp_{call_id}",
                    "phones": [],
                    "status": "completed",
                    "attempts": [
                        {
                            "id": f"att_{call_id}",
                            "status": "completed",
                            "provider_call_id": call["provider_call_id"],
                            "failure_code": call["end_reason"] or None,
                            "transcript_turns": [
                                {
                                    "offset_seconds": t.get("offset_seconds"),
                                    "speaker": {"agent": "bot", "callee": "user"}.get(t.get("speaker", ""), "unknown"),
                                    "text": t.get("text", ""),
                                }
                                for t in call["turns"]
                            ],
                        }
                    ],
                }
            ],
        },
        "spans": {},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    return 0


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app(args.db or DEFAULT_DB_PATH), host=args.host, port=args.port)
    return 0


# -- helpers -----------------------------------------------------------------


def _first_subject_for(schema_name: str) -> str:
    for entry in SUBJECTS:
        if entry.schema_name == schema_name:
            return entry.id
    raise SystemExit(f"no seeded subject for schema {schema_name!r}; pass --subject")


def _print_delta(title: str, note: str, delta: LedgerDelta) -> None:
    print(f"\n=== {title} -- {delta.subject_id} (attempt {delta.attempt}) ===")
    if note:
        print(f"    {note}")
    print(f"    asked: {', '.join(delta.asked_fields) or '(nothing left to ask)'}")
    print(f"    respondent: {delta.respondent_role}")
    for row in delta.rows:
        badge = BADGE.get(row.verdict.value, row.verdict.value)
        # A quote only reads as evidence when it was actually found in the call.
        located = row.quote_start >= 0
        detail = f'"{row.quote}"' if located else REASON_TEXT[row.reason]
        print(f"    {row.field:<22} {badge} {row.value or '-':<14} {detail}")
        if row.quote and not located:
            print(f"    {'':<22} {'':<12} discarded claim: {row.quote!r}")
        if row.verdict is Verdict.CONTRADICTED:
            print(f"    {'':<22} {'':<12} was {row.known_value!r} on record")
    queued = [i.field for i in delta.requeue if i.is_actionable]
    done = [i.field for i in delta.requeue if not i.is_actionable]
    if queued:
        print(f"    requeued: {', '.join(queued)}")
    if done:
        print(f"    exhausted: {', '.join(done)}")
    print(f"    Calls used: {CALL_BUDGET - delta.calls_remaining} / {CALL_BUDGET}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
