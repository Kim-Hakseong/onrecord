"""The five rules, in order, one test class each."""

from __future__ import annotations

import datetime as _dt

from onrecord.schema import FieldSpec
from onrecord.verdict import (
    Claim,
    Reason,
    Respondent,
    Verdict,
    adjudicate,
    adjudicate_field,
    establish_respondent,
)

REF = _dt.date(2026, 9, 1)
SALES = Respondent(role="sales_rep", quote="네, 영업 담당입니다.")


def adjudicate_one(spec, claim, transcript, respondent=SALES, known_value=""):
    return adjudicate_field(
        spec,
        [claim],
        transcript=transcript,
        respondent=respondent,
        known_value=known_value,
        reference_date=REF,
    )


class TestRule1Quote:
    def test_no_claim_at_all_is_unresolved(self, date_field, transcript):
        row = adjudicate_field(date_field, [], transcript=transcript, respondent=SALES)
        assert row.verdict is Verdict.UNRESOLVED
        assert row.reason is Reason.NO_CLAIM

    def test_value_without_a_quote_is_unresolved(self, date_field, transcript):
        claim = Claim(field=date_field.name, raw_value="2026-09-24", quote=None, source="calle")
        row = adjudicate_one(date_field, claim, transcript)
        assert row.verdict is Verdict.UNRESOLVED
        assert row.reason is Reason.QUOTE_MISSING

    def test_paraphrased_quote_is_thrown_away(self, date_field, transcript):
        claim = Claim(
            field=date_field.name,
            raw_value="2026-09-24",
            quote="9월 24일에 보내드리겠습니다.",  # plausible, and not in the transcript
            source="spanner",
        )
        row = adjudicate_one(date_field, claim, transcript)
        assert row.verdict is Verdict.UNRESOLVED
        assert row.reason is Reason.QUOTE_NOT_IN_TRANSCRIPT
        assert row.value == ""

    def test_verbatim_quote_survives(self, date_field, transcript):
        claim = Claim(
            field=date_field.name,
            raw_value="2026-09-24",
            quote="9월 24일에 출고됩니다.",
            source="spanner",
        )
        row = adjudicate_one(date_field, claim, transcript)
        assert row.verdict is Verdict.CONFIRMED
        assert row.quote_start >= 0


class TestRule2Type:
    def test_unparseable_date_is_unresolved_not_an_exception(self, date_field, transcript):
        claim = Claim(
            field=date_field.name,
            raw_value="조만간",
            quote="9월 24일에 출고됩니다.",
            source="spanner",
        )
        row = adjudicate_one(date_field, claim, transcript)
        assert row.verdict is Verdict.UNRESOLVED
        assert row.reason is Reason.TYPE_PARSE_FAILED

    def test_enum_outside_the_declared_values_is_unresolved(self, transcript):
        spec = FieldSpec(
            name="blocking_reason",
            type="enum",
            values=("material_shortage", "none"),
            authority=("sales_rep",),
        )
        claim = Claim(
            field=spec.name, raw_value="사장님 기분", quote="감사합니다.", source="spanner"
        )
        row = adjudicate_one(spec, claim, transcript)
        assert row.verdict is Verdict.UNRESOLVED
        assert row.reason is Reason.TYPE_PARSE_FAILED

    def test_bool_and_int_parse(self, transcript):
        flag = FieldSpec(name="partial_shipment_ok", type="bool", authority=("sales_rep",))
        row = adjudicate_one(
            flag, Claim(field=flag.name, raw_value="네", quote="감사합니다.", source="spanner"), transcript
        )
        assert row.verdict is Verdict.CONFIRMED and row.value == "true"

        count = FieldSpec(name="quantity_committed", type="int", authority=("sales_rep",))
        row = adjudicate_one(
            count, Claim(field=count.name, raw_value="1,200개", quote="감사합니다.", source="spanner"), transcript
        )
        assert row.verdict is Verdict.CONFIRMED and row.value == "1200"


class TestRule3Authority:
    def test_a_clear_answer_from_the_wrong_person_does_not_settle(self, date_field, transcript):
        claim = Claim(
            field=date_field.name,
            raw_value="2026-09-24",
            quote="9월 24일에 출고됩니다.",
            source="spanner",
        )
        row = adjudicate_one(
            date_field, claim, transcript, respondent=Respondent(role="assistant")
        )
        assert row.verdict is Verdict.NO_AUTHORITY
        assert row.value == "2026-09-24"  # the value is kept, it just does not count

    def test_unestablished_respondent_has_no_authority(self, date_field, transcript):
        claim = Claim(
            field=date_field.name,
            raw_value="2026-09-24",
            quote="9월 24일에 출고됩니다.",
            source="spanner",
        )
        row = adjudicate_one(date_field, claim, transcript, respondent=Respondent())
        assert row.verdict is Verdict.NO_AUTHORITY

    def test_role_must_be_quoted_to_count(self, transcript):
        declared = ("sales_rep", "assistant")
        established = establish_respondent(
            declared, "sales_rep", "네, 영업 담당입니다.", transcript=transcript
        )
        assert established.role == "sales_rep"

        unquoted = establish_respondent(
            declared, "sales_rep", "제가 영업 팀장입니다.", transcript=transcript
        )
        assert unquoted.role == "unknown"

        undeclared = establish_respondent(
            declared, "ceo", "네, 영업 담당입니다.", transcript=transcript
        )
        assert undeclared.role == "unknown"


class TestRule4Contradiction:
    def test_a_settled_value_that_differs_is_contradicted(self, date_field, transcript):
        claim = Claim(
            field=date_field.name,
            raw_value="2026-09-24",
            quote="9월 24일에 출고됩니다.",
            source="spanner",
        )
        row = adjudicate_one(date_field, claim, transcript, known_value="2026-09-20")
        assert row.verdict is Verdict.CONTRADICTED
        assert row.value == "2026-09-24"
        assert row.known_value == "2026-09-20"

    def test_a_matching_value_is_merely_confirmed(self, date_field, transcript):
        claim = Claim(
            field=date_field.name,
            raw_value="2026-09-24",
            quote="9월 24일에 출고됩니다.",
            source="spanner",
        )
        row = adjudicate_one(date_field, claim, transcript, known_value="2026-09-24")
        assert row.verdict is Verdict.CONFIRMED

    def test_authority_is_checked_before_contradiction(self, date_field, transcript):
        claim = Claim(
            field=date_field.name,
            raw_value="2026-09-24",
            quote="9월 24일에 출고됩니다.",
            source="spanner",
        )
        row = adjudicate_one(
            date_field,
            claim,
            transcript,
            respondent=Respondent(role="assistant"),
            known_value="2026-09-20",
        )
        assert row.verdict is Verdict.NO_AUTHORITY


class TestRule5Confirm:
    def test_all_five_rules_passed(self, date_field, transcript):
        claim = Claim(
            field=date_field.name,
            raw_value="9월 24일",
            quote="9월 24일에 출고됩니다.",
            source="spanner",
        )
        row = adjudicate_one(date_field, claim, transcript)
        assert row.verdict is Verdict.CONFIRMED
        assert row.value == "2026-09-24"
        assert row.rule == 5
        assert transcript.replace("\n", " ").find(row.quote) != -1


class TestAdjudicatorContract:
    def test_every_field_gets_exactly_one_row(self, supplier_schema, transcript):
        rows = adjudicate(
            supplier_schema.fields, [], transcript=transcript, respondent=SALES
        )
        assert [r.field for r in rows] == list(supplier_schema.field_names)

    def test_conflicting_settled_claims_do_not_settle(self, date_field, transcript):
        rows = adjudicate_field(
            date_field,
            [
                Claim(field=date_field.name, raw_value="2026-09-24", quote="9월 24일에 출고됩니다.", source="spanner"),
                Claim(field=date_field.name, raw_value="2026-09-30", quote="9월 24일에 출고됩니다.", source="calle"),
            ],
            transcript=transcript,
            respondent=SALES,
            reference_date=REF,
        )
        assert rows.verdict is Verdict.UNRESOLVED
        assert rows.reason is Reason.CONFLICTING_CLAIMS

    def test_adjudication_never_raises_on_garbage(self, date_field):
        row = adjudicate_field(
            date_field,
            [Claim(field=date_field.name, raw_value="", quote="", source="")],
            transcript="",
            respondent=None,
        )
        assert row.verdict is Verdict.UNRESOLVED
