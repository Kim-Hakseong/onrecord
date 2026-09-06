"""Deterministic value parsers.

Every parser returns `(ok, value)` and never raises. A string that cannot be
parsed is not an error condition -- it is the normal outcome of a call where
nobody committed to anything, and the adjudicator turns it into UNRESOLVED.
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from typing import Any

Parsed = tuple[bool, Any]

_TRUE_WORDS = frozenset(
    {"yes", "y", "true", "1", "ok", "okay", "가능", "네", "예", "됩니다", "가능합니다"}
)
_FALSE_WORDS = frozenset(
    {"no", "n", "false", "0", "불가", "아니오", "아니요", "안됩니다", "불가능"}
)
_UNKNOWN_WORDS = frozenset({"", "unknown", "unspecified", "n/a", "na", "null", "none_given", "모름"})

_ISO = re.compile(r"(?P<y>\d{4})[-/.](?P<m>\d{1,2})[-/.](?P<d>\d{1,2})")
_SLASH = re.compile(r"(?<!\d)(?P<m>\d{1,2})[/.](?P<d>\d{1,2})(?!\d)")
# "9월 20일" / "9 월 20 일" -- Korean month/day markers, not domain vocabulary.
_KO = re.compile(r"(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일")
_INT = re.compile(r"-?\d[\d,]*")

# Every spelling of a month this parser will accept, listed rather than matched
# by prefix: a wildcard stem reads "Septembre" as September, which is a guess.
# These are calendar words, not domain vocabulary -- the adjudicator still has
# no idea what a shipment is.
_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
# Longest first so "sept" is preferred over "sep" before the word boundary runs.
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
_ORDINAL = r"(?:st|nd|rd|th)?"
_YEAR = r"(?:,?\s*(?P<y>\d{4}))?"
# `(?!\d)` after the day matters: without it "24 September 2026" is read as
# September 20th, because the day group happily eats the first two digits of
# the year.
_DAY = r"(?P<d>\d{1,2})(?!\d)"

# "October 2nd", "Oct 2, 2026"
_EN_MONTH_DAY = re.compile(
    rf"\b(?P<m>{_MONTH_ALT})\b\.?\s+{_DAY}{_ORDINAL}{_YEAR}", re.IGNORECASE
)
# "2nd of October", "24 September 2026"
_EN_DAY_MONTH = re.compile(
    rf"\b{_DAY}{_ORDINAL}\s+(?:of\s+)?(?P<m>{_MONTH_ALT})\b\.?{_YEAR}",
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    """NFC-normalize and collapse whitespace. Used before every comparison."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def is_unknown(raw: str) -> bool:
    return normalize(str(raw)).lower() in _UNKNOWN_WORDS


def parse_date(raw: str, *, reference: _dt.date | None = None) -> Parsed:
    text = normalize(str(raw))
    if is_unknown(text):
        return False, None
    match = _ISO.search(text)
    if match:
        return _build_date(int(match["y"]), int(match["m"]), int(match["d"]))

    ref = reference or _dt.date.today()

    # Named months first: "March 31st, 2026" contains digits a numeric pattern
    # would otherwise misread.
    for pattern in (_EN_MONTH_DAY, _EN_DAY_MONTH):
        match = pattern.search(text)
        if match:
            month = _MONTHS[match["m"].lower()]
            return _resolve_year(int(match["d"]), month, match["y"], ref)

    for pattern in (_KO, _SLASH):
        match = pattern.search(text)
        if match:
            return _resolve_year(int(match["d"]), int(match["m"]), None, ref)
    return False, None


def _resolve_year(day: int, month: int, year: str | None, ref: _dt.date) -> Parsed:
    """Use the stated year, or infer the one the speaker must have meant."""
    if year:
        return _build_date(int(year), month, day)
    ok, value = _build_date(ref.year, month, day)
    if not ok:
        return False, None
    # A month more than six months behind the reference is next year's.
    if (ref - value).days > 183:
        return _build_date(ref.year + 1, month, day)
    return ok, value


def _build_date(year: int, month: int, day: int) -> Parsed:
    try:
        return True, _dt.date(year, month, day)
    except ValueError:
        return False, None


def parse_bool(raw: str) -> Parsed:
    text = normalize(str(raw)).lower().rstrip(".!?")
    if text in _TRUE_WORDS:
        return True, True
    if text in _FALSE_WORDS:
        return True, False
    return False, None


def parse_int(raw: str) -> Parsed:
    text = normalize(str(raw))
    if is_unknown(text):
        return False, None
    match = _INT.search(text)
    if not match:
        return False, None
    try:
        return True, int(match.group(0).replace(",", ""))
    except ValueError:  # pragma: no cover - regex guarantees digits
        return False, None


def parse_enum(raw: str, values: tuple[str, ...]) -> Parsed:
    text = normalize(str(raw)).lower()
    for candidate in values:
        if text == candidate.lower():
            return True, candidate
    return False, None


def parse_text(raw: str) -> Parsed:
    text = normalize(str(raw))
    if is_unknown(text):
        return False, None
    return True, text


def parse(kind: str, raw: str, *, values: tuple[str, ...] = (), reference: _dt.date | None = None) -> Parsed:
    if kind == "date":
        return parse_date(raw, reference=reference)
    if kind == "bool":
        return parse_bool(raw)
    if kind == "int":
        return parse_int(raw)
    if kind == "enum":
        return parse_enum(raw, values)
    if kind == "text":
        return parse_text(raw)
    return False, None


def render(value: Any) -> str:
    """Canonical string form used in the ledger and in equality comparisons."""
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)
