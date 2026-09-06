"""Turn the model off entirely and the product still works.

Not "degrades gracefully" -- keeps its state machine. Every field falls to
UNRESOLVED, every UNRESOLVED field lands in the requeue, and the follow-up call
is planned from what the requeue says. That is the whole system minus the model.
"""

from __future__ import annotations

from onrecord.fixtures import by_name
from onrecord.pipeline import MODE_REPLAY, run
from onrecord.seed import seed_store, subject
from onrecord.spanner import NullSpanner
from onrecord.store import Store
from onrecord.verdict import Verdict


def test_pipeline_without_a_span_pointer_leaves_everything_unresolved(supplier_schema, tmp_path):
    fixture = by_name("supplier_followup_confirmed")  # the call that settles everything
    entry = subject(fixture.subject_id)

    with Store(tmp_path / "db.sqlite") as store:
        seed_store(store)
        delta = run(
            supplier_schema,
            entry.contact,
            subject_id=fixture.subject_id,
            known_values=entry.known_values,
            store=store,
            mode=MODE_REPLAY,
            outcome=fixture.outcome,
            spanner=NullSpanner(),
        )

        assert delta.spanner_used is False
        assert {r.verdict for r in delta.rows} == {Verdict.UNRESOLVED}
        assert len(delta.rows) == len(supplier_schema.fields)
        # Nothing is dropped: every open field has a requeue row.
        assert {i.field for i in delta.requeue} == {r.field for r in delta.rows}
        assert store.ledger(fixture.subject_id)


def test_calle_structured_result_alone_cannot_confirm(supplier_schema, tmp_path):
    """CALL-E returned a date. Without a quote it is a suggestion, not a record."""
    fixture = by_name("supplier_followup_confirmed")
    assert fixture.call["structured_result"]["promised_ship_date"] == "2026-09-24"
    entry = subject(fixture.subject_id)

    with Store(tmp_path / "db.sqlite") as store:
        seed_store(store)
        delta = run(
            supplier_schema,
            entry.contact,
            subject_id=fixture.subject_id,
            known_values=entry.known_values,
            store=store,
            mode=MODE_REPLAY,
            outcome=fixture.outcome,
            spanner=NullSpanner(),
        )
    row = next(r for r in delta.rows if r.field == "promised_ship_date")
    assert row.verdict is Verdict.UNRESOLVED
    assert not delta.confirmed_without_quote
