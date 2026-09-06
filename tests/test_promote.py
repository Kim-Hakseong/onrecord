"""The requeue, and the two-call chain it drives."""

from __future__ import annotations

from onrecord.fixtures import by_name
from onrecord.pipeline import MODE_REPLAY, run
from onrecord.promote import (
    MAX_ATTEMPTS,
    RequeueState,
    next_attempt_fields,
    promote,
    requires_new_respondent,
)
from onrecord.seed import seed_store, subject
from onrecord.store import Store
from onrecord.verdict import LedgerRow, Reason, Verdict


def _row(field: str, verdict: Verdict, reason: Reason) -> LedgerRow:
    return LedgerRow(field=field, verdict=verdict, reason=reason)


class TestPromote:
    def test_every_open_field_becomes_a_row_and_settled_ones_do_not(self):
        rows = [
            _row("a", Verdict.CONFIRMED, Reason.QUOTED_AND_AUTHORIZED),
            _row("b", Verdict.CONTRADICTED, Reason.DIFFERS_FROM_KNOWN_VALUE),
            _row("c", Verdict.UNRESOLVED, Reason.NO_CLAIM),
            _row("d", Verdict.NO_AUTHORITY, Reason.RESPONDENT_LACKS_AUTHORITY),
        ]
        items = promote(rows, schema_name="s", subject_id="X-1")
        assert {i.field for i in items} == {"c", "d"}

    def test_no_open_field_is_silently_dropped(self):
        rows = [_row(name, Verdict.UNRESOLVED, Reason.NO_CLAIM) for name in "abcdef"]
        items = promote(rows, schema_name="s", subject_id="X-1")
        assert len(items) == len(rows)

    def test_attempt_cap_marks_exhausted_instead_of_dropping(self):
        rows = [_row("c", Verdict.UNRESOLVED, Reason.NO_CLAIM)]
        first = promote(rows, schema_name="s", subject_id="X-1", attempts_so_far={"c": 1})
        assert first[0].state is RequeueState.QUEUED

        capped = promote(
            rows, schema_name="s", subject_id="X-1", attempts_so_far={"c": MAX_ATTEMPTS}
        )
        assert capped[0].state is RequeueState.EXHAUSTED
        assert not capped[0].is_actionable
        assert next_attempt_fields(capped) == ()

    def test_no_authority_asks_for_a_different_respondent(self):
        rows = [_row("d", Verdict.NO_AUTHORITY, Reason.RESPONDENT_LACKS_AUTHORITY)]
        items = promote(rows, schema_name="s", subject_id="X-1")
        assert items[0].needs_different_respondent
        assert requires_new_respondent(items)


class TestTwoStageChain:
    def test_the_second_call_asks_only_what_is_still_open(self, supplier_schema, tmp_path):
        first_fixture = by_name("supplier_evasive")
        second_fixture = by_name("supplier_followup_confirmed")
        entry = subject("PO-1041")

        with Store(tmp_path / "db.sqlite") as store:
            seed_store(store)
            first = run(
                supplier_schema,
                entry.contact,
                subject_id="PO-1041",
                known_values=entry.known_values,
                store=store,
                mode=MODE_REPLAY,
                outcome=first_fixture.outcome,
                spanner=first_fixture.spanner,
            )
            # The evasive call settled the blocking reason and nothing else.
            assert first.attempt == 1
            assert set(first.asked_fields) == set(supplier_schema.field_names)
            settled_first = {r.field for r in first.settled}
            assert settled_first == {"blocking_reason"}
            assert "blocking_reason" not in {i.field for i in first.requeue}

            second = run(
                supplier_schema,
                entry.contact,
                subject_id="PO-1041",
                known_values=entry.known_values,
                store=store,
                mode=MODE_REPLAY,
                outcome=second_fixture.outcome,
                spanner=second_fixture.spanner,
            )

        assert second.attempt == 2
        # The chain ran automatically, and the goal shrank by exactly the settled field.
        assert "blocking_reason" not in second.asked_fields
        assert len(second.asked_fields) == len(first.asked_fields) - 1
        assert {r.field for r in second.settled} == set(second.asked_fields)
        assert second.requeue == []
        assert not second.confirmed_without_quote

    def test_the_shorter_second_call_is_visible_in_the_recorded_duration(self):
        first = by_name("supplier_evasive").outcome
        second = by_name("supplier_followup_confirmed").outcome
        assert second.duration_seconds < first.duration_seconds
