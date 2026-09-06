"""Storage invariants: the ledger is append-only and corrections are new rows."""

from __future__ import annotations

import re
from pathlib import Path

from onrecord.promote import RequeueItem, RequeueState
from onrecord.store import Store
from onrecord.verdict import LedgerRow, Reason, Verdict

STORE_PY = Path(__file__).resolve().parents[1] / "src" / "onrecord" / "store.py"


def test_no_sql_statement_updates_or_deletes_the_ledger():
    source = STORE_PY.read_text(encoding="utf-8")
    assert not re.search(r"UPDATE\s+ledger", source, re.IGNORECASE)
    assert not re.search(r"DELETE\s+FROM\s+ledger", source, re.IGNORECASE)
    assert not re.search(r"UPDATE\s+requeue", source, re.IGNORECASE)


def test_a_correction_is_a_new_row_and_the_old_one_survives(tmp_path):
    with Store(tmp_path / "db.sqlite") as store:
        store.upsert_subject("PO-1", schema_name="s", known_values={})
        store.append_rows(
            [LedgerRow(field="d", verdict=Verdict.UNRESOLVED, reason=Reason.NO_CLAIM)],
            call_id="c1",
            schema_name="s",
            subject_id="PO-1",
        )
        store.append_rows(
            [
                LedgerRow(
                    field="d",
                    verdict=Verdict.CONFIRMED,
                    reason=Reason.QUOTED_AND_AUTHORIZED,
                    value="2026-09-24",
                    quote="9월 24일에 출고됩니다.",
                )
            ],
            call_id="c2",
            schema_name="s",
            subject_id="PO-1",
        )

        history = store.ledger("PO-1")
        assert len(history) == 2
        assert history[0]["verdict"] == "UNRESOLVED"
        assert history[0]["call_id"] == "c1"

        current = store.current_rows("PO-1")
        assert len(current) == 1
        assert current[0]["verdict"] == "CONFIRMED"
        assert current[0]["call_id"] == "c2"


def test_only_live_calls_spend_budget(tmp_path):
    from onrecord.store import CallRecord

    with Store(tmp_path / "db.sqlite") as store:
        assert store.calls_remaining() == 20
        store.save_call(CallRecord(id="r1", schema_name="s", subject_id="PO-1", mode="replay"))
        assert store.calls_remaining() == 20
        store.save_call(CallRecord(id="l1", schema_name="s", subject_id="PO-1", mode="live"))
        assert store.calls_used() == 1
        assert store.calls_remaining() == 19


def test_a_settled_field_leaves_the_requeue(tmp_path):
    with Store(tmp_path / "db.sqlite") as store:
        store.append_requeue(
            [
                RequeueItem(
                    schema_name="s",
                    subject_id="PO-1",
                    field="d",
                    state=RequeueState.QUEUED,
                    attempts=1,
                    reason="no_claim",
                    verdict="UNRESOLVED",
                )
            ]
        )
        store.append_rows(
            [LedgerRow(field="d", verdict=Verdict.UNRESOLVED, reason=Reason.NO_CLAIM)],
            call_id="c1",
            schema_name="s",
            subject_id="PO-1",
        )
        assert len(store.open_requeue("PO-1")) == 1

        store.append_rows(
            [
                LedgerRow(
                    field="d",
                    verdict=Verdict.CONFIRMED,
                    reason=Reason.QUOTED_AND_AUTHORIZED,
                    value="2026-09-24",
                )
            ],
            call_id="c2",
            schema_name="s",
            subject_id="PO-1",
        )
        assert store.requeue("PO-1") == []
