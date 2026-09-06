"""Regression over the recorded call corpus.

Each fixture declares the verdict it expects per field. These are the six
scenarios the README reports on, and the false-positive count they produce is
the number quoted there.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from onrecord.fixtures import load_all
from onrecord.pipeline import MODE_REPLAY, run
from onrecord.paths import schema_dir
from onrecord.schema import load_schema
from onrecord.seed import seed_store, subject
from onrecord.store import Store
from onrecord.verdict import Verdict

SCHEMA_DIR = schema_dir()
REFERENCE_DATE = _dt.date(2026, 9, 1)
FIXTURES = load_all()


def _schema(name: str):
    return load_schema(SCHEMA_DIR / f"{name}.yaml")


def _replay(fixture, tmp_path):
    schema = _schema(fixture.schema_name)
    entry = subject(fixture.subject_id)
    with Store(tmp_path / f"{fixture.name}.sqlite") as store:
        seed_store(store)
        return run(
            schema,
            entry.contact,
            subject_id=fixture.subject_id,
            known_values=entry.known_values,
            store=store,
            mode=MODE_REPLAY,
            outcome=fixture.outcome,
            spanner=fixture.spanner,
            reference_date=REFERENCE_DATE,
        )


def test_the_corpus_is_not_empty():
    assert len(FIXTURES) >= 6


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
def test_recorded_call_produces_the_recorded_verdicts(fixture, tmp_path):
    delta = _replay(fixture, tmp_path)
    actual = {row.field: row.verdict.value for row in delta.rows}
    for field, want in _expected(fixture).items():
        assert actual[field] == want, f"{fixture.name}: {field} -> {actual[field]}, expected {want}"


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
def test_no_value_settles_without_a_verbatim_quote(fixture, tmp_path):
    """The false-positive check. This is the number that has to stay zero."""
    delta = _replay(fixture, tmp_path)
    assert delta.confirmed_without_quote == []
    for row in delta.rows:
        if row.verdict in (Verdict.CONFIRMED, Verdict.CONTRADICTED):
            assert row.quote in delta.transcript


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
def test_every_open_field_is_requeued_or_exhausted(fixture, tmp_path):
    delta = _replay(fixture, tmp_path)
    assert {r.field for r in delta.open} == {i.field for i in delta.requeue}


def test_a_paraphrased_span_is_visibly_discarded(tmp_path):
    """The demo's 1:20 moment: a plausible value with nowhere to point."""
    fixture = next(f for f in FIXTURES if f.name == "supplier_span_rejected")
    delta = _replay(fixture, tmp_path)
    row = next(r for r in delta.rows if r.field == "promised_ship_date")
    assert row.verdict is Verdict.UNRESOLVED
    assert row.reason.value == "quote_not_in_transcript"
    assert row.quote == "We'll ship on October 15th."  # what the model claimed
    assert row.quote not in delta.transcript  # and what the transcript says


def test_the_second_domain_pack_needs_no_code_change(tmp_path):
    fixture = next(f for f in FIXTURES if f.schema_name == "reference_check")
    delta = _replay(fixture, tmp_path)
    verdicts = {row.field: row.verdict for row in delta.rows}
    assert verdicts["employment_end_date"] is Verdict.CONFIRMED
    # Only HR may answer this one, and HR was not on the phone.
    assert verdicts["eligible_for_rehire"] is Verdict.NO_AUTHORITY


def test_the_seeded_corpus_contains_a_contradiction(tmp_path):
    fixture = next(f for f in FIXTURES if f.name == "supplier_contradicted")
    delta = _replay(fixture, tmp_path)
    row = next(r for r in delta.rows if r.field == "promised_ship_date")
    assert row.verdict is Verdict.CONTRADICTED
    assert row.known_value == "2026-09-20"
    assert row.value == "2026-10-02"


def _expected(fixture) -> dict[str, str]:
    import json

    return json.loads(fixture.path.read_text(encoding="utf-8"))["meta"]["expected"]


def test_the_seeded_corpus_leaves_all_four_verdicts_standing(tmp_path):
    """Replaying the whole corpus in order must end with every verdict visible.

    The ledger shows the latest row per field, so a later call can supersede an
    earlier verdict -- correct behaviour, but it once left NO_AUTHORITY at zero
    across the whole supplier pack because the voicemail attempt landed after
    the stand-in call. The fixtures are ordered so that does not happen, and
    this is the test that keeps them that way.
    """
    from onrecord.explain import verdict_counts
    from onrecord.store import Store

    supplier = [f for f in FIXTURES if f.schema_name == "supplier_delivery"]
    with Store(tmp_path / "corpus.sqlite") as store:
        seed_store(store)
        for fixture in supplier:
            entry = subject(fixture.subject_id)
            run(
                _schema(fixture.schema_name),
                entry.contact,
                subject_id=fixture.subject_id,
                known_values=entry.known_values,
                store=store,
                mode=MODE_REPLAY,
                outcome=fixture.outcome,
                spanner=fixture.spanner,
                reference_date=REFERENCE_DATE,
            )
        current = [
            row
            for sub in {f.subject_id for f in supplier}
            for row in store.current_rows(sub)
        ]

    counts = verdict_counts(current)
    for verdict, count in counts.items():
        assert count > 0, f"{verdict} is not visible anywhere in the ledger: {counts}"
