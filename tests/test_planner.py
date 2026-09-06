from __future__ import annotations

from onrecord.planner import Contact, build_task, open_fields, plan_call, settled_fields
from onrecord.schema import result_schema_for
from onrecord.verdict import LedgerRow, Reason, Verdict

CONTACT = Contact(phone="+821000001041", name="Kim Min-su", org="Hanseong Precision")


def _settled(field: str) -> LedgerRow:
    return LedgerRow(field=field, verdict=Verdict.CONFIRMED, reason=Reason.QUOTED_AND_AUTHORIZED)


def _open(field: str) -> LedgerRow:
    return LedgerRow(field=field, verdict=Verdict.UNRESOLVED, reason=Reason.NO_CLAIM)


def test_settled_fields_drop_out_of_the_next_goal(supplier_schema):
    prior = [_settled("blocking_reason"), _open("promised_ship_date")]
    assert settled_fields(prior) == {"blocking_reason"}
    remaining = open_fields(supplier_schema, prior)
    assert "blocking_reason" not in [f.name for f in remaining]
    assert len(remaining) == len(supplier_schema.fields) - 1


def test_the_follow_up_task_text_does_not_mention_settled_fields(supplier_schema):
    prior = [_settled("blocking_reason")]
    plan = plan_call(
        supplier_schema, CONTACT, subject_id="PO-1041", prior_rows=prior, attempt=2
    )
    assert "blocking_reason" not in plan.task
    assert "promised_ship_date" in plan.task
    assert "follow-up" in plan.task


def test_the_task_never_reads_the_erp_value_out_loud(supplier_schema):
    plan = plan_call(
        supplier_schema,
        CONTACT,
        subject_id="PO-1042",
        known_values={"promised_ship_date": "2026-09-20"},
    )
    assert "2026-09-20" not in plan.task
    assert "do not read" in plan.task.lower()


def test_the_task_establishes_the_respondent_before_anything_else(supplier_schema):
    task = build_task(
        supplier_schema, CONTACT, supplier_schema.fields, subject_id="PO-1041"
    )
    assert task.index("role") < task.index("promised_ship_date")


def test_the_planner_holds_no_domain_vocabulary():
    """Every noun the callee hears comes from the YAML, not from planner.py."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "src" / "onrecord" / "planner.py").read_text(
        encoding="utf-8"
    )
    for word in ("supplier", "purchase order", "ship date", "PO-", "candidate", "납기"):
        assert word not in source


def test_result_schema_offers_calle_an_unknown_for_every_field(supplier_schema):
    built = result_schema_for(supplier_schema, supplier_schema.fields)
    assert built["additionalProperties"] is False
    assert "unknown" in built["properties"]["blocking_reason"]["enum"]
    assert built["properties"]["partial_shipment_ok"]["enum"] == ["yes", "no", "unknown"]
    assert "unknown" in built["properties"]["respondent_role"]["enum"]
    # Nothing is required: a call that settles nothing is a valid result.
    assert "required" not in built
