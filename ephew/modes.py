from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mode:
    name: str
    directive: str | None
    display: str
    glyph: str
    marker_instruction: str = ""


MODES: tuple[Mode, ...] = (
    Mode(
        name="none",
        directive=None,
        display="none",
        glyph="-x",
    ),
    Mode(
        name="concise",
        directive="Fewest words possible. Max one sentence.",
        display="concise",
        glyph="-c",
        marker_instruction="End your response with a space followed by the literal text: (ephew-c)",
    ),
    Mode(
        name="paragraph",
        directive="2 paragraphs max, biasing to the least response needed.",
        display="paragraph",
        glyph="-p",
        marker_instruction="End your response with a space followed by the literal text: (ephew-p)",
    ),
    Mode(
        name="verbose",
        directive="Go deep where depth helps: reasoning, tradeoffs, edge cases. Skip padding.",
        display="verbose",
        glyph="-v",
        marker_instruction="End your response with a space followed by the literal text: (ephew-v)",
    ),
    Mode(
        name="table",
        directive="Markdown table only, no prose.",
        display="table",
        glyph="-t",
        marker_instruction="End your response with a space followed by the literal text: (ephew-t)",
    ),
)

_BY_NAME: dict[str, Mode] = {m.name: m for m in MODES}

DEFAULT: Mode = _BY_NAME["none"]

OVERRIDE_FLAGS: dict[str, str] = {
    "-x": "none",
    "--none": "none",
    "-c": "concise",
    "--concise": "concise",
    "-p": "paragraph",
    "--paragraph": "paragraph",
    "-v": "verbose",
    "--verbose": "verbose",
    "-t": "table",
    "--table": "table",
}


def next_mode(current: Mode) -> Mode:
    idx = MODES.index(current)
    return MODES[(idx + 1) % len(MODES)]


def find_by_name(name: str) -> Mode:
    return _BY_NAME[name]


def all_names() -> tuple[str, ...]:
    return tuple(m.name for m in MODES)
