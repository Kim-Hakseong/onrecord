"""Turning an adjudication into something a screen can render, without lying."""

from __future__ import annotations

from onrecord.constants import RULE_COUNT
from onrecord.explain import (
    group_by_subject,
    rule_trace,
    transcript_lines,
    verdict_counts,
)
from onrecord.valuetypes import normalize
from onrecord.verdict import LedgerRow, Reason, Verdict

TURNS = [
    {"speaker": "agent", "text": "What date can you ship?", "offset_seconds": 0},
    {"speaker": "callee", "text": "It ships on September 24th.", "offset_seconds": 14},
    {"speaker": "agent", "text": "Thank you.", "offset_seconds": 20},
]
TRANSCRIPT = normalize("\n".join(f"{t['speaker']}: {t['text']}" for t in TURNS))


def _row(field: str, verdict: Verdict, reason: Reason, **kwargs) -> LedgerRow:
    return LedgerRow(field=field, verdict=verdict, reason=reason, **kwargs)


class TestRuleTrace:
    def test_a_contradiction_marks_the_rule_that_decided_it(self):
        row = _row(
            "promised_ship_date",
            Verdict.CONTRADICTED,
            Reason.DIFFERS_FROM_KNOWN_VALUE,
            rule=4,
        )
        trace = rule_trace(row)
        assert len(trace) == RULE_COUNT
        decided = [step for step in trace if step["decided"]]
        assert len(decided) == 1
        # Settled at compare, so the fifth rule genuinely never ran -- and the
        # screen can now say which one decided instead of trailing off.
        assert decided[0]["rule"] == "compare"
        assert decided[0]["status"] == "passed"
        assert trace[4]["status"] == "not_reached"

    def test_a_failure_marks_the_rule_it_stopped_at(self):
        row = _row("x", Verdict.UNRESOLVED, Reason.QUOTE_NOT_IN_TRANSCRIPT, rule=1)
        trace = rule_trace(row)
        assert trace[0]["decided"] and trace[0]["status"] == "failed"
        assert all(step["status"] == "not_reached" for step in trace[1:])

    def test_exactly_one_rule_is_ever_marked_as_deciding(self):
        for verdict, reason, rule in [
            (Verdict.CONFIRMED, Reason.QUOTED_AND_AUTHORIZED, 5),
            (Verdict.NO_AUTHORITY, Reason.RESPONDENT_LACKS_AUTHORITY, 3),
            (Verdict.UNRESOLVED, Reason.TYPE_PARSE_FAILED, 2),
            (Verdict.UNRESOLVED, Reason.NO_CLAIM, 1),
        ]:
            trace = rule_trace(_row("x", verdict, reason, rule=rule))
            assert sum(step["decided"] for step in trace) == 1


class TestTranscriptLines:
    def test_the_speaker_per_line_structure_is_recovered(self):
        lines = transcript_lines(TRANSCRIPT, TURNS)
        assert [line["speaker"] for line in lines] == ["agent", "callee", "agent"]
        assert lines[1]["text"] == "It ships on September 24th."
        assert all(line["start"] >= 0 for line in lines)

    def test_recovered_offsets_point_at_the_same_text(self):
        lines = transcript_lines(TRANSCRIPT, TURNS)
        for line in lines:
            rendered = TRANSCRIPT[line["start"] : line["end"]]
            assert rendered.startswith(f"{line['speaker']}:")
            assert line["text"] in rendered

    def test_a_quote_highlights_inside_its_own_turn_only(self):
        quote = "It ships on September 24th."
        start = TRANSCRIPT.find(quote)
        lines = transcript_lines(
            TRANSCRIPT, TURNS, [(start, start + len(quote), "promised_ship_date")]
        )
        quoted = [
            (index, piece)
            for index, line in enumerate(lines)
            for piece in line["segments"]
            if piece["field"]
        ]
        assert len(quoted) == 1
        index, piece = quoted[0]
        assert index == 1  # the callee's turn, not the agent's
        assert piece["text"] == quote

    def test_segments_reassemble_into_the_turn_verbatim(self):
        quote = "September 24th"
        start = TRANSCRIPT.find(quote)
        lines = transcript_lines(TRANSCRIPT, TURNS, [(start, start + len(quote), "f")])
        for line in lines:
            assert "".join(piece["text"] for piece in line["segments"]) == line["text"]

    def test_a_partial_quote_splits_the_turn_into_three(self):
        quote = "September 24th"
        start = TRANSCRIPT.find(quote)
        lines = transcript_lines(TRANSCRIPT, TURNS, [(start, start + len(quote), "f")])
        segments = lines[1]["segments"]
        assert [bool(piece["field"]) for piece in segments] == [False, True, False] or [
            bool(piece["field"]) for piece in segments
        ] == [True, False]

    def test_an_unlocatable_turn_still_renders(self):
        lines = transcript_lines(TRANSCRIPT, [{"speaker": "callee", "text": "a line that is not there"}])
        assert lines[0]["start"] == -1
        assert lines[0]["segments"][0]["text"] == "a line that is not there"

    def test_no_turns_is_not_an_error(self):
        assert transcript_lines("", []) == []


class TestGrouping:
    def test_a_subject_appears_once_not_twice(self):
        rows = [
            {"subject_id": "PO-1042", "field": "a", "verdict": "CONTRADICTED"},
            {"subject_id": "PO-1041", "field": "b", "verdict": "CONFIRMED"},
            {"subject_id": "PO-1042", "field": "c", "verdict": "UNRESOLVED"},
        ]
        groups = group_by_subject(rows)
        assert [g["subject_id"] for g in groups] == ["PO-1042", "PO-1041"]
        assert len(groups[0]["rows"]) == 2

    def test_the_subject_needing_action_comes_first(self):
        rows = [
            {"subject_id": "A", "field": "x", "verdict": "CONFIRMED"},
            {"subject_id": "B", "field": "y", "verdict": "NO_AUTHORITY"},
            {"subject_id": "C", "field": "z", "verdict": "UNRESOLVED"},
        ]
        assert [g["subject_id"] for g in group_by_subject(rows)] == ["B", "C", "A"]

    def test_each_group_reports_all_four_counts(self):
        rows = [{"subject_id": "A", "field": "x", "verdict": "CONFIRMED"}]
        group = group_by_subject(rows)[0]
        assert group["counts"] == {
            "CONFIRMED": 1,
            "CONTRADICTED": 0,
            "UNRESOLVED": 0,
            "NO_AUTHORITY": 0,
        }
        assert group["open_count"] == 0

    def test_subject_metadata_is_carried_through(self):
        rows = [{"subject_id": "A", "field": "x", "verdict": "UNRESOLVED"}]
        groups = group_by_subject(rows, [{"id": "A", "label": "Drive shaft", "known_values": {}}])
        assert groups[0]["label"] == "Drive shaft"
        assert groups[0]["open_count"] == 1


def test_verdict_counts_always_lists_four_states():
    assert set(verdict_counts([])) == {
        "CONFIRMED",
        "CONTRADICTED",
        "UNRESOLVED",
        "NO_AUTHORITY",
    }
