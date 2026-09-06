"""The read model behind the three screens."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from onrecord.api import create_app
from onrecord.constants import RULE_COUNT, VERDICT_COUNT
from onrecord.fixtures import load_all
from onrecord.pipeline import MODE_REPLAY, run
from onrecord.paths import schema_dir
from onrecord.schema import load_schema
from onrecord.seed import seed_store, subject
from onrecord.store import Store

SCHEMA_DIR = schema_dir()


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "api.sqlite"
    with Store(db) as store:
        seed_store(store)
        for fixture in load_all():
            entry = subject(fixture.subject_id)
            run(
                load_schema(SCHEMA_DIR / f"{fixture.schema_name}.yaml"),
                entry.contact,
                subject_id=fixture.subject_id,
                known_values=entry.known_values,
                store=store,
                mode=MODE_REPLAY,
                outcome=fixture.outcome,
                spanner=fixture.spanner,
                reference_date=_dt.date(2026, 9, 1),
            )
    return TestClient(create_app(db, SCHEMA_DIR))


def test_meta_reads_its_numbers_from_constants(client):
    meta = client.get("/api/meta").json()
    assert meta["call_budget"] == 20
    assert meta["verdict_count"] == VERDICT_COUNT == 4
    assert meta["screen_count"] == 3
    assert meta["rule_count"] == RULE_COUNT == 5
    assert set(meta["schemas"]) == {"supplier_delivery", "reference_check"}
    # Replayed calls are free; the counter has to say so.
    assert meta["calls_used"] == 0


def test_the_ledger_shows_all_four_counts_even_when_one_is_zero(client):
    body = client.get("/api/ledger", params={"schema": "reference_check"}).json()
    assert set(body["counts"]) == {
        "CONFIRMED",
        "CONTRADICTED",
        "UNRESOLVED",
        "NO_AUTHORITY",
    }
    assert body["counts"]["CONTRADICTED"] == 0
    assert body["counts"]["NO_AUTHORITY"] == 1


def test_the_ledger_puts_what_needs_action_on_top(client):
    rows = client.get("/api/ledger", params={"schema": "supplier_delivery"}).json()["rows"]
    order = [row["verdict"] for row in rows]
    assert order[0] == "CONTRADICTED"
    assert order == sorted(
        order,
        key=lambda v: ["CONTRADICTED", "NO_AUTHORITY", "UNRESOLVED", "CONFIRMED"].index(v),
    )


def test_every_row_carries_a_reason_a_screen_can_render(client):
    rows = client.get("/api/ledger").json()["rows"]
    assert rows
    for row in rows:
        assert row["reason_text"]
        if row["verdict"] in ("CONFIRMED", "CONTRADICTED"):
            assert row["quote"]
        if row["verdict"] == "CONTRADICTED":
            assert row["known_value"]


def test_call_detail_returns_the_full_five_rule_trace(client):
    call_id = client.get("/api/calls").json()[0]["id"]
    body = client.get(f"/api/calls/{call_id}").json()
    assert body["call"]["transcript"]
    for row in body["rows"]:
        trace = row["rule_trace"]
        assert len(trace) == RULE_COUNT
        assert [t["rule"] for t in trace] == [
            "quote",
            "type",
            "authority",
            "compare",
            "verdict",
        ]
        stopped = [t for t in trace if t["status"] == "failed"]
        assert len(stopped) <= 1


def test_a_rejected_span_is_surfaced_not_hidden(client):
    calls = client.get("/api/calls", params={"subject": "PO-1044"}).json()
    body = client.get(f"/api/calls/{calls[0]['id']}").json()
    assert body["rejected_spans"], "the discarded claim must be visible in the API"
    rejected = body["rejected_spans"][0]
    assert rejected["claimed_quote"] == "10월 15일에 출고하겠습니다."
    assert rejected["claimed_quote"] not in body["call"]["transcript"]


def test_a_confirmed_quote_can_be_located_in_the_transcript(client):
    calls = client.get("/api/calls", params={"subject": "PO-1042"}).json()
    body = client.get(f"/api/calls/{calls[0]['id']}").json()
    for row in body["rows"]:
        if row["verdict"] in ("CONFIRMED", "CONTRADICTED"):
            transcript = body["call"]["transcript"]
            assert transcript[row["quote_start"] : row["quote_end"]] == row["quote"]


def test_requeue_shows_what_the_next_call_will_not_ask_again(client):
    cards = client.get("/api/requeue", params={"schema": "supplier_delivery"}).json()
    assert cards
    card = next(c for c in cards if c["subject_id"] == "PO-1042")
    dropped = {d["field"] for d in card["dropped_from_goal"]}
    assert "promised_ship_date" in dropped
    assert "promised_ship_date" not in card["next_fields"]
    assert card["next_fields"] == ["partial_shipment_ok"]
    assert "partial_shipment_ok" in card["next_goal"]


def test_an_exhausted_subject_is_kept_but_not_actionable(client):
    cards = client.get("/api/requeue").json()
    card = next(c for c in cards if c["subject_id"] == "PO-1043")
    assert card["attempts"] >= card["max_attempts"]
    assert card["actionable"] is False


def test_no_endpoint_reports_a_call_level_success_flag(client):
    payloads = [
        client.get("/api/meta").json(),
        client.get("/api/ledger").json(),
        client.get("/api/requeue").json(),
    ]
    call_id = client.get("/api/calls").json()[0]["id"]
    payloads.append(client.get(f"/api/calls/{call_id}").json())
    blob = repr(payloads)
    assert "'success'" not in blob and '"success"' not in blob


def test_running_a_follow_up_without_credentials_fails_with_a_clear_status(client):
    response = client.post(
        "/api/requeue/run",
        json={"subject_id": "PO-1042", "schema_name": "supplier_delivery"},
    )
    assert response.status_code in (503, 409)
    assert "CALLE_API_KEY" in response.json()["detail"] or "budget" in response.json()["detail"].lower()


def test_call_detail_returns_a_speaker_per_line_transcript(client):
    """The stored transcript is one line; the screen needs the turns back."""
    calls = client.get("/api/calls", params={"subject": "PO-1042"}).json()
    body = client.get(f"/api/calls/{calls[0]['id']}").json()
    lines = body["lines"]
    assert len(lines) == len(body["call"]["turns"])
    assert [line["speaker"] for line in lines][:2] == ["agent", "callee"]
    for line in lines:
        assert "".join(piece["text"] for piece in line["segments"]) == line["text"]


def test_a_confirmed_quote_is_highlighted_in_the_speaker_who_said_it(client):
    calls = client.get("/api/calls", params={"subject": "PO-1042"}).json()
    body = client.get(f"/api/calls/{calls[0]['id']}").json()
    highlighted = [
        (line["speaker"], piece)
        for line in body["lines"]
        for piece in line["segments"]
        if piece["field"]
    ]
    assert highlighted, "confirmed values must be visible in the transcript"
    # The agent proposing a date is not evidence; only the callee's words are.
    assert {speaker for speaker, _ in highlighted} == {"callee"}


def test_the_ledger_groups_each_subject_into_one_block(client):
    body = client.get("/api/ledger", params={"schema": "supplier_delivery"}).json()
    groups = body["groups"]
    ids = [group["subject_id"] for group in groups]
    assert len(ids) == len(set(ids)), "a subject must not appear in two blocks"
    assert sum(len(group["rows"]) for group in groups) == len(body["rows"])
    # Action-first ordering survives grouping: the contradiction leads.
    assert groups[0]["counts"]["CONTRADICTED"] == 1
