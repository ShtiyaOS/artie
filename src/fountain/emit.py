"""
Fountain emission with forcing characters.

docs/14_editor.md §2 — Always emit the forcing character. The component type
is known, so there is no reason to rely on Fountain's inference.

Component → Fountain forcing character:
  SCENE_HEADING  →  .INT. DINER - NIGHT
  ACTION         →  !paragraph text
  CHARACTER      →  @MARLA
  DIALOGUE       →  (no forcing char — appears beneath a CHARACTER cue)
  PARENTHETICAL  →  (no forcing char — uses literal parens)
  TRANSITION     →  >CUT TO:
  NOTE           →  [[thought]]  (no forcing char; bracket syntax)

The spec table (§2) marks DIALOGUE, PARENTHETICAL, and NOTE as having no
forcing character, but those types require special formatting:
  DIALOGUE       — plain text with a blank line above (provided by structure)
  PARENTHETICAL  — wrapped in parentheses
  NOTE           — wrapped in [[double brackets]]
"""

from __future__ import annotations

from typing import Sequence


# ---------------------------------------------------------------------------
# Forcing character map
# ---------------------------------------------------------------------------

# Each value is a prefix callable: given the content string, return the
# correctly-formatted Fountain line(s).

def _scene_heading(content: str) -> str:
    """Force a scene heading: .<content>"""
    return f".{content}"


def _action(content: str) -> str:
    """Force an action paragraph: !<content>"""
    return f"!{content}"


def _character(content: str) -> str:
    """Force a character cue: @<content>"""
    return f"@{content}"


def _dialogue(content: str) -> str:
    """Dialogue — no forcing character; plain text under a character cue."""
    return content


def _parenthetical(content: str) -> str:
    """Parenthetical — literal parentheses if not already present."""
    stripped = content.strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        return stripped
    return f"({stripped})"


def _transition(content: str) -> str:
    """Force a transition: ><content>"""
    return f">{content}"


def _note(content: str) -> str:
    """Note — [[double bracket]] syntax."""
    stripped = content.strip()
    # Remove existing brackets if the writer included them.
    if stripped.startswith("[[") and stripped.endswith("]]"):
        return stripped
    return f"[[{stripped}]]"


_EMITTERS = {
    "SCENE_HEADING": _scene_heading,
    "ACTION": _action,
    "CHARACTER": _character,
    "DIALOGUE": _dialogue,
    "PARENTHETICAL": _parenthetical,
    "TRANSITION": _transition,
    "NOTE": _note,
}

# Blank-line rules between consecutive component types.
# Each type emits its line(s); the assembler inserts blank lines to separate
# logical blocks.  In Fountain: blank line before scene heading, character cue,
# transition; action paragraphs separated by a blank line; dialogue immediately
# below its cue with no blank line in between.

_NEEDS_BLANK_BEFORE = {
    "SCENE_HEADING",
    "ACTION",
    "CHARACTER",
    "TRANSITION",
    "NOTE",
}

# Types that glue to the line above without a blank separator.
_NO_BLANK_BEFORE = {
    "DIALOGUE",
    "PARENTHETICAL",
}


def emit_component(comp_type: str, content: str) -> str:
    """
    Return the correctly-formatted Fountain line for a single component.

    Raises ValueError for unknown component types.
    """
    emitter = _EMITTERS.get(comp_type)
    if emitter is None:
        raise ValueError(f"Unknown component type: {comp_type!r}")
    return emitter(content)


def emit_fountain(components: Sequence[dict]) -> str:
    """
    Assemble a list of component dicts into a Fountain document string.

    Each dict must have keys ``comp_type`` and ``content``.
    Components are ordered by their position in the sequence (caller must
    pre-sort by ``sequence_order`` before passing here).

    Blank lines are inserted according to Fountain conventions:
      - A blank line before SCENE_HEADING, ACTION, CHARACTER, TRANSITION, NOTE
        (except at the very start of the document).
      - DIALOGUE and PARENTHETICAL glue directly to the line above.

    Returns a string with Unix line endings.
    """
    lines: list[str] = []

    for i, comp in enumerate(components):
        comp_type = comp["comp_type"]
        content = comp.get("content", "")

        fountain_line = emit_component(comp_type, content)

        if i > 0 and comp_type in _NEEDS_BLANK_BEFORE:
            lines.append("")

        lines.append(fountain_line)

    return "\n".join(lines)
