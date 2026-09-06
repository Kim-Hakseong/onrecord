"""Rule 2 in isolation.

These parsers are the only place a spoken value becomes a typed one, and they
are the reason a garbled answer is UNRESOLVED rather than an exception. Nothing
here may raise, on any input.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from onrecord.valuetypes import (
    normalize,
    parse,
    parse_bool,
    parse_date,
    parse_enum,
    parse_int,
    parse_text,
    render,
)

REF = _dt.date(2026, 9, 1)


class TestDates:
    @pytest.mark.parametrize(
        ("spoken", "expected"),
        [
            # English, which is what the demo calls are in.
            ("September 24th", _dt.date(2026, 9, 24)),
            ("Sept 24", _dt.date(2026, 9, 24)),
            ("Sep 24, 2026", _dt.date(2026, 9, 24)),
            ("October 2nd", _dt.date(2026, 10, 2)),
            ("2nd of October", _dt.date(2026, 10, 2)),
            ("24 September 2026", _dt.date(2026, 9, 24)),
            ("March 31st, 2026", _dt.date(2026, 3, 31)),
            # Korean, kept because one recorded call is in Korean and because
            # the live calls may be.
            ("9월 24일", _dt.date(2026, 9, 24)),
            ("10월 2일", _dt.date(2026, 10, 2)),
            # Machine forms.
            ("2026-09-24", _dt.date(2026, 9, 24)),
            ("9/24", _dt.date(2026, 9, 24)),
        ],
    )
    def test_a_date_a_person_would_say_parses(self, spoken, expected):
        ok, value = parse_date(spoken, reference=REF)
        assert ok and value == expected, f"{spoken!r} -> {value}"

    def test_a_stated_year_beats_the_inferred_one(self):
        ok, value = parse_date("March 31st, 2027", reference=REF)
        assert ok and value == _dt.date(2027, 3, 31)

    def test_a_month_already_past_is_read_as_next_year(self):
        """Said in September, "February 3rd" means the coming February."""
        ok, value = parse_date("February 3rd", reference=REF)
        assert ok and value == _dt.date(2027, 2, 3)

    def test_a_month_just_behind_is_still_this_year(self):
        ok, value = parse_date("August 20th", reference=REF)
        assert ok and value == _dt.date(2026, 8, 20)

    @pytest.mark.parametrize(
        "spoken",
        ["soon", "next week sometime", "", "unknown", "the 31st", "Septembre 24"],
    )
    def test_a_non_date_is_refused_rather_than_guessed(self, spoken):
        ok, value = parse_date(spoken, reference=REF)
        assert not ok and value is None

    def test_an_impossible_date_is_refused(self):
        assert parse_date("February 30th", reference=REF) == (False, None)
        assert parse_date("2026-13-01", reference=REF) == (False, None)


class TestBools:
    @pytest.mark.parametrize("spoken", ["yes", "Yes.", "y", "true", "ok", "네", "가능"])
    def test_agreement(self, spoken):
        assert parse_bool(spoken) == (True, True)

    @pytest.mark.parametrize("spoken", ["no", "No!", "n", "false", "아니오", "불가"])
    def test_refusal(self, spoken):
        assert parse_bool(spoken) == (True, False)

    @pytest.mark.parametrize("spoken", ["maybe", "possibly", "I think so", ""])
    def test_a_hedge_is_not_a_boolean(self, spoken):
        assert parse_bool(spoken) == (False, None)


class TestOthers:
    def test_int_tolerates_the_words_around_it(self):
        assert parse_int("500") == (True, 500)
        assert parse_int("1,200 units") == (True, 1200)
        assert parse_int("all 500 of them") == (True, 500)

    def test_int_refuses_when_there_is_no_number(self):
        assert parse_int("most of them") == (False, None)
        assert parse_int("unknown") == (False, None)

    def test_enum_only_accepts_a_declared_value(self):
        values = ("material_shortage", "production_delay", "none")
        assert parse_enum("production_delay", values) == (True, "production_delay")
        assert parse_enum("PRODUCTION_DELAY", values) == (True, "production_delay")
        assert parse_enum("supplier is slow", values) == (False, None)

    def test_text_refuses_the_unknown_markers(self):
        assert parse_text("Senior Researcher") == (True, "Senior Researcher")
        assert parse_text("  Senior   Researcher ") == (True, "Senior Researcher")
        assert parse_text("unknown") == (False, None)


class TestContract:
    @pytest.mark.parametrize(
        "kind", ["date", "bool", "int", "enum", "text", "nonsense-type"]
    )
    @pytest.mark.parametrize("value", ["", "  ", "???", "0", "네", "\n\t"])
    def test_no_parser_raises_on_anything(self, kind, value):
        ok, parsed = parse(kind, value, values=("a",), reference=REF)
        assert isinstance(ok, bool)
        assert ok or parsed is None

    def test_render_round_trips_into_the_ledger_form(self):
        assert render(_dt.date(2026, 9, 24)) == "2026-09-24"
        assert render(True) == "true"
        assert render(500) == "500"
        assert render(None) == ""

    def test_normalize_collapses_whitespace_and_composes(self):
        assert normalize("  a \n b\tc ") == "a b c"
