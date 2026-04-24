from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mode:
    name: str
    directive: str | None
    display: str
    glyph: str


MODES: tuple[Mode, ...] = (
    Mode(
        name="very-concise",
        directive="Yes or no if possible. Max 5 words otherwise.",
        display="very concise",
        glyph=".",
    ),
    Mode(
        name="concise",
        directive="One sentence.",
        display="concise",
        glyph="..",
    ),
    Mode(
        name="normal",
        directive=None,
        display="normal",
        glyph="-",
    ),
    Mode(
        name="thorough",
        directive="Include reasoning, tradeoffs, and an example if it helps.",
        display="thorough",
        glyph='"',
    ),
    Mode(
        name="very-thorough",
        directive="Go deep where depth helps: reasoning, tradeoffs, edge cases. Skip padding.",
        display="very thorough",
        glyph='""',
    ),
    Mode(
        name="table",
        directive="Markdown table only, no prose.",
        display="table",
        glyph="⊞",
    ),
)

_BY_NAME: dict[str, Mode] = {m.name: m for m in MODES}

DEFAULT: Mode = _BY_NAME["normal"]


def next_mode(current: Mode) -> Mode:
    idx = MODES.index(current)
    return MODES[(idx + 1) % len(MODES)]


def find_by_name(name: str) -> Mode:
    return _BY_NAME[name]


def all_names() -> tuple[str, ...]:
    return tuple(m.name for m in MODES)
