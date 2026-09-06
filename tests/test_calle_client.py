"""The CALL-E adapter. Measured against calle-ai 0.7.0, exercised without it."""

from __future__ import annotations

import json

import pytest

from onrecord.paths import fixture_dir
from onrecord.calle_client import (
    SPEAKER_AGENT,
    SPEAKER_CALLEE,
    CalleClient,
    CalleNotConfigured,
    outcome_from_payload,
    render_transcript,
)

FIXTURE_DIR = fixture_dir()


def _payload(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))["call"]


def test_a_call_task_flattens_into_one_outcome():
    outcome = outcome_from_payload(_payload("02_supplier_followup_confirmed.json"))
    assert outcome.call_id == "call_onrecord_0002"
    assert outcome.status == "completed"
    assert outcome.turns[0]["speaker"] == SPEAKER_AGENT
    assert outcome.turns[1]["speaker"] == SPEAKER_CALLEE
    assert "9월 24일에 출고됩니다." in outcome.transcript
    assert outcome.structured_result["promised_ship_date"] == "2026-09-24"
    assert outcome.duration_seconds == 31
    assert outcome.reached_someone


def test_an_unanswered_call_is_still_a_well_formed_outcome():
    outcome = outcome_from_payload(_payload("03_supplier_voicemail.json"))
    assert outcome.end_reason == "no_answer"
    assert outcome.reached_someone is False
    assert outcome.structured_result == {}


def test_a_payload_missing_everything_does_not_raise():
    outcome = outcome_from_payload({})
    assert outcome.call_id == ""
    assert outcome.transcript == ""
    assert outcome.turns == []


def test_unknown_speakers_are_labelled_not_dropped():
    turns = outcome_from_payload(_payload("03_supplier_voicemail.json")).turns
    assert turns[0]["speaker"] == "unknown"
    assert "지금은 전화를 받을 수 없습니다" in render_transcript(turns)


def test_a_live_call_without_credentials_fails_loudly_and_early():
    client = CalleClient(api_key="")
    assert client.configured is False
    with pytest.raises(CalleNotConfigured):
        client.place_call(task="t", phone="+821000000000")


def test_the_installed_sdk_still_has_the_signature_this_wrapper_assumes():
    """If CALL-E changes its SDK, this is the test that says so."""
    import inspect

    from calle import CalleClient as SDKClient
    from calle.calls import CalleCalls

    params = inspect.signature(SDKClient.__init__).parameters
    assert {"api_key", "base_url", "timeout"} <= set(params)

    create = inspect.signature(CalleCalls.create).parameters
    assert {"task", "recipient", "result_schema", "metadata"} <= set(create)
    assert "create_and_wait" in dir(CalleCalls)
