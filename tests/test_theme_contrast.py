"""The pastel palette must not make the four verdicts unreadable.

A soft-gradient design pushes every colour toward the background, and the four
verdicts are the product's core distinction. This test reads the stylesheet the
screens actually ship and checks the contrast of each verdict badge, in both
themes, so the palette cannot be softened past the point of legibility without
the build saying so.

It is deliberately a repository test rather than a frontend one: the numbers it
guards are a product requirement, not a styling preference.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS = (Path(__file__).resolve().parents[1] / "web" / "app" / "globals.css").read_text(
    encoding="utf-8"
)

VERDICTS = ("confirmed", "contradicted", "unresolved", "noauthority")

#: WCAG AA for normal text. Badge labels are small, so this is the right bar.
AA_TEXT = 4.5
#: WCAG AA for incidental/large text -- the muted ink used for timestamps and ids.
AA_MUTED = 3.0

Rgb = tuple[float, float, float]


def theme_block(name: str) -> str:
    return CSS.split(f':root[data-theme="{name}"] {{')[1].split("}")[0]


def token(block: str, name: str) -> str:
    match = re.search(rf"{name}:\s*([^;]+);", block)
    assert match, f"missing token {name}"
    return match.group(1).strip()


def parse_color(value: str) -> tuple[Rgb, float]:
    """Return (rgb, alpha) for a #hex or rgba() token."""
    rgba = re.match(r"rgba?\(([^)]+)\)", value)
    if rgba:
        parts = [float(p.strip()) for p in rgba.group(1).split(",")]
        alpha = parts[3] if len(parts) > 3 else 1.0
        return (parts[0], parts[1], parts[2]), alpha
    hexed = value.lstrip("#")
    return tuple(int(hexed[i : i + 2], 16) for i in (0, 2, 4)), 1.0  # type: ignore[return-value]


def composite(value: str, backdrop: Rgb) -> Rgb:
    rgb, alpha = parse_color(value)
    return tuple(c * alpha + b * (1 - alpha) for c, b in zip(rgb, backdrop))  # type: ignore[return-value]


def _channel(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: Rgb) -> float:
    r, g, b = (_channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: Rgb, b: Rgb) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def panel_of(theme: str) -> Rgb:
    """A card interior: the translucent panel composited over the page base."""
    block = theme_block(theme)
    base, _ = parse_color(token(block, "--base"))
    return composite(token(block, "--surface"), base)


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("verdict", VERDICTS)
def test_verdict_badge_text_is_readable(theme: str, verdict: str):
    block = theme_block(theme)
    foreground, _ = parse_color(token(block, f"--{verdict}-fg"))
    background = composite(token(block, f"--{verdict}-bg"), panel_of(theme))
    ratio = contrast(foreground, background)
    assert ratio >= AA_TEXT, f"{theme}/{verdict} is {ratio:.2f}:1, needs {AA_TEXT}:1"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_body_text_is_readable_on_a_card(theme: str):
    block, panel = theme_block(theme), panel_of(theme)
    for name, minimum in (("--ink", AA_TEXT), ("--ink-2", AA_TEXT), ("--ink-3", AA_MUTED)):
        foreground, _ = parse_color(token(block, name))
        ratio = contrast(foreground, panel)
        assert ratio >= minimum, f"{theme}{name} is {ratio:.2f}:1, needs {minimum}:1"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_four_verdicts_stay_distinguishable_from_each_other(theme: str):
    """Not just readable -- telling them apart is the whole point."""
    block, panel = theme_block(theme), panel_of(theme)
    tints = {v: composite(token(block, f"--{v}-bg"), panel) for v in VERDICTS}
    seen = set()
    for verdict, rgb in tints.items():
        rounded = tuple(round(c / 6) for c in rgb)  # tolerate imperceptible drift
        assert rounded not in seen, f"{theme}: {verdict} tint collides with another"
        seen.add(rounded)


def test_both_themes_define_every_colour_the_other_does():
    light, dark = theme_block("light"), theme_block("dark")
    names = lambda block: set(re.findall(r"(--[a-z0-9-]+):", block))  # noqa: E731
    assert names(light) == names(dark)


def test_the_primary_button_label_is_readable():
    for theme in ("light", "dark"):
        block = theme_block(theme)
        accent, _ = parse_color(token(block, "--accent"))
        ink, _ = parse_color(token(block, "--accent-ink"))
        ratio = contrast(ink, accent)
        assert ratio >= AA_TEXT, f"{theme} call-again button is {ratio:.2f}:1"
