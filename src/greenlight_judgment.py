"""
Greenlight JUDGMENT-based slot validation.

docs/02_greenlight.md §8  — determinism map; re-ask taxonomy; three-attempt
                             escalation ladder; PROVISIONAL on non-convergence;
                             curated foreign-example library interface.
docs/04_agent_roster.md §3 — re-ask taxonomy moves; contrast barred from
                              psychological slots.

Judgment-dominant slots: S02, S03, S04, S08, TP1
  These have no deterministic rule gate. Validation is model-evaluated.

Determinism map (§8):
  Judgment-dominant: S02, S03, S04, S08, TP1

Re-ask taxonomy (docs/04_agent_roster.md §3):
  narrow           — "that's a category — which one?"
  specify          — "how does that show up in an ordinary morning?"
  probe_consequence — "what happens to them if they don't get it?"
  test_falsifiability — "tell me a story where that isn't true"
  contrast         — allowed on S03 and S07 only; BARRED from S04 and
                     the psychological_stasis facet of S07.

Escalation ladder (three attempts per slot):
  Attempt 1 — targeted move (narrow / specify / probe_consequence /
               test_falsifiability / contrast where permitted)
  Attempt 2 — formal definition + a pre-written foreign example from the
               curated library (library not yet written — see FOREIGN_EXAMPLE_LIBRARY)
  Attempt 3 — metacognitive probe: the model names the difficulty itself
               ("This is the third time we've been here. Tell me what makes
               this hard to pin down.")
  Non-convergence — accept the degraded value; mark PROVISIONAL. Do not block.

Public interface
----------------
  validate_judgment(slot_id, value, reask_count) -> JudgmentResult
    .confidence  "VALIDATED" | "PROVISIONAL"
    .reask_move  str | None   — the move Artie should make on the next ask
    .converged   bool         — False means attempt limit reached; mark PROVISIONAL
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from google.genai import Client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Foreign-example library interface
# ---------------------------------------------------------------------------
# NOTE: The curated foreign-example library (docs/02_greenlight.md §8 /
# docs/04_agent_roster.md §3 "Foreign examples") is not yet written.
# Attempt 2 in the escalation ladder should show a pre-written example from
# this library. The function below is the interface — replace the stub with
# the actual library lookup when the file exists.

def _get_foreign_example(slot_id: str) -> str | None:
    """
    Return a pre-written foreign example for slot_id from the curated library,
    or None if no example is available.

    docs/04_agent_roster.md §3: "When escalation reaches attempt two, Artie
    may show a pre-written example from the curated library to demonstrate
    required form. He may never generate one."

    TODO: implement when docs/02_greenlight.md §7 (curated foreign-example
          library) is written and the static file is added to src/data/.
    """
    return None   # library not yet written — attempt two proceeds without example


# ---------------------------------------------------------------------------
# JUDGMENT questions — verbatim per slot
# docs/02_greenlight.md §8 (determinism map), §2 (slot descriptions)
# docs/03_scene_rig.md §3 (JUDGMENT question pattern)
#
# Psychological slots: S04, and the psychological_stasis facet of S07.
# Contrast is barred from these (docs/04_agent_roster.md §3).
# ---------------------------------------------------------------------------

# Re-ask moves allowed per slot.
# contrast is permitted on S03 and S07 (non-psychological facets) only.
_CONTRAST_ALLOWED: frozenset[str] = frozenset({"S03", "S07"})

# Slots whose JUDGMENT concerns an internal psychological condition.
# Contrast is absolutely barred here regardless of slot-level permission.
_PSYCHOLOGICAL_SLOTS: frozenset[str] = frozenset({"S04"})

JUDGMENT_QUESTIONS: dict[str, str] = {
    # S02 Protagonist — a specific person the story can rotate around.
    # docs/02_greenlight.md §2: "Y3 all; X01 row; all TRANSFORMATION comparisons"
    "S02": (
        "Is this a specific person — not a type or a role — "
        "that the story can rotate around?"
    ),
    # S03 Protagonist Want — a specific, active want with a countable obstacle.
    # docs/02_greenlight.md §2: "Y2 active goal; Y1 at X04, X06; Scene Rig"
    # Contrast is permitted (docs/04_agent_roster.md §3, docs/02_greenlight.md §8).
    "S03": (
        "Is this a specific, active want that could be satisfied or frustrated "
        "by a concrete event — rather than a general orientation or mood?"
    ),
    # S04 Protagonist Flaw — an internal condition; contrast barred (psychological slot).
    # docs/02_greenlight.md §2: "Y3 at X01, X08; X11.Y3; X12.Y3"
    "S04": (
        "Does this describe an internal condition that would plausibly cost "
        "the protagonist something they value — not a circumstance, "
        "not a habit, not a trait the story admires?"
    ),
    # S08 Arena — a tangible space capable of containing the story's action.
    # docs/02_greenlight.md §2: "Y6 environment cells"
    # Analogous to Scene Rig N06: "Does this describe a spatial environment
    # capable of containing the action?"
    "S08": (
        "Does this describe a tangible space — physical, institutional, "
        "or social — capable of generating the pressures the story requires?"
    ),
    # S14 Principal Characters — distinct people with distinguishable functions.
    # docs/02_greenlight.md §3: explicit JUDGMENT question.
    "S14": (
        "Are these distinct people with distinguishable narrative functions, "
        "or restatements of one role?"
    ),
    # TP1 Inciting Incident — a specific, dated event (optional slot).
    # docs/02_greenlight.md §2: "X02 row; Y1 causal trigger"
    # docs/01_locked_axis.md X02: "The event that irreparably fractures the
    # baseline equilibrium."
    "TP1": (
        "Does this describe a specific, datable event that irreparably "
        "fractures the baseline — not an ongoing condition or a gradual shift?"
    ),
}

# ---------------------------------------------------------------------------
# Escalation ladder prompts — three attempts per slot
# ---------------------------------------------------------------------------

_ESCALATION_PROMPTS = [
    # Attempt 1 — targeted re-ask (move chosen by model in JUDGMENT call)
    (
        "The writer's answer did not clearly satisfy the JUDGMENT question "
        "for this slot. Choose one re-ask move from: narrow, specify, "
        "probe_consequence, test_falsifiability{contrast_option}. "
        "Return the chosen move as 'reask_move' in your response."
    ),
    # Attempt 2 — formal definition + foreign example (if available)
    (
        "The writer has not converged after one re-ask. State the formal "
        "definition of what this slot requires. "
        "{example_clause}"
        "Choose one re-ask move to follow."
    ),
    # Attempt 3 — metacognitive probe
    (
        "This is the third attempt on this slot. Name the difficulty itself — "
        "what specifically makes this hard to pin down for this writer's story. "
        "Use move: metacognitive_probe."
    ),
]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JudgmentResult:
    """
    Result of a JUDGMENT validation call.

    confidence: "VALIDATED" when the answer satisfies the JUDGMENT question;
                "PROVISIONAL" when it does not or when the attempt limit is reached.
    reask_move: the re-ask move Artie should make on the next turn, or None
                when converged or when the limit is reached.
    converged:  True when the model judged the answer satisfactory.
                False when the model judged it unsatisfactory or the attempt
                limit (3) was reached — accept degraded value, mark PROVISIONAL.
    """
    confidence: str     # "VALIDATED" | "PROVISIONAL"
    reask_move: str | None
    converged: bool


_VALIDATED = JudgmentResult(confidence="VALIDATED", reask_move=None, converged=True)


def _provisional(reask_move: str | None = None) -> JudgmentResult:
    return JudgmentResult(confidence="PROVISIONAL", reask_move=reask_move, converged=False)


# ---------------------------------------------------------------------------
# Model call
# ---------------------------------------------------------------------------

def _judgment_model() -> str:
    """Model string for JUDGMENT calls (docs/00_master_blueprint.md §3.5)."""
    return os.environ.get("GEMINI_TEXT_MODEL", "models/gemini-3.5-flash")


def _build_judgment_prompt(
    slot_id: str,
    slot_label: str,
    judgment_question: str,
    value: Any,
    reask_count: int,
    contrast_allowed: bool,
    foreign_example: str | None,
) -> str:
    """
    Build the JUDGMENT evaluation prompt for the model.

    The prompt asks the model to evaluate the writer's answer against the
    JUDGMENT question and return a JSON decision.
    """
    value_text = json.dumps(value) if not isinstance(value, str) else value

    contrast_option = ", contrast" if contrast_allowed else ""

    example_clause: str
    if reask_count == 1 and foreign_example:
        example_clause = (
            f"Show this pre-written example from the curated library: "
            f"{json.dumps(foreign_example)}. "
        )
    else:
        example_clause = (
            "No pre-written example is available for this slot. "
            "State the formal definition only. "
        )

    # Escalation context
    if reask_count == 0:
        escalation_context = ""
    elif reask_count == 1:
        escalation_context = _ESCALATION_PROMPTS[1].format(
            example_clause=example_clause
        )
    elif reask_count >= 2:
        escalation_context = _ESCALATION_PROMPTS[2]
    else:
        escalation_context = ""

    return f"""You are evaluating a writer's answer to a Greenlight slot.

Slot: {slot_id} — {slot_label}
JUDGMENT question: {judgment_question}
Writer's answer: {value_text}
Re-ask attempt number: {reask_count} (0 = first evaluation, 3 = non-convergence)

{escalation_context}

Evaluate the answer against the JUDGMENT question.
A satisfactory answer is specific, active, and falsifiable.
A vague, generic, or hedged answer does not satisfy.

Allowed re-ask moves: narrow, specify, probe_consequence, test_falsifiability{contrast_option}
(metacognitive_probe is used only on attempt 3 and must not appear on attempts 0–2)

Respond with valid JSON only:
{{
  "satisfied": true | false,
  "reason": "<one sentence explaining why the answer is or is not satisfactory>",
  "reask_move": "<move>" | null
}}

"reask_move" must be null when "satisfied" is true.
"reask_move" must be one of the allowed moves (or metacognitive_probe on attempt 3) when "satisfied" is false.
"""


def validate_judgment(
    slot_id: str,
    value: Any,
    reask_count: int,
    *,
    slot_label: str = "",
) -> JudgmentResult:
    """
    Run JUDGMENT validation for a judgment-dominant slot.

    docs/02_greenlight.md §8 — three-attempt ladder; PROVISIONAL on
    non-convergence; contrast barred from psychological slots.
    docs/04_agent_roster.md §3 — foreign examples on attempt two;
    metacognitive probe on attempt three.

    Parameters
    ----------
    slot_id     : slot identifier (e.g. "S02")
    value       : the writer's answer (any JSON-serialisable value)
    reask_count : number of re-asks already made for this slot (0 = first try)
    slot_label  : human-readable label for the slot (used in the prompt)

    Returns
    -------
    JudgmentResult
      .confidence  "VALIDATED" | "PROVISIONAL"
      .reask_move  move for Artie's next question, or None
      .converged   True if the answer satisfied the JUDGMENT question
    """
    judgment_question = JUDGMENT_QUESTIONS.get(slot_id)
    if judgment_question is None:
        # Slot has no JUDGMENT — treat as automatically VALIDATED.
        # (Pure-rule and structurally-gated slots do not call this function.)
        logger.debug("No JUDGMENT question for slot %s; skipping", slot_id)
        return _VALIDATED

    # Non-convergence: three attempts exhausted — accept degraded value.
    # docs/02_greenlight.md §8: "On non-convergence, accept the degraded value
    # and mark the slot PROVISIONAL. Do not block."
    if reask_count >= 3:
        logger.info(
            "Slot %s: attempt limit reached (reask_count=%d); "
            "accepting degraded value as PROVISIONAL",
            slot_id, reask_count,
        )
        return _provisional(reask_move=None)

    # Contrast permission check.
    # docs/04_agent_roster.md §3: contrast on S03 and S07 only.
    # Barred from psychological slots (S04) and psychological_stasis facet of S07.
    contrast_allowed = (
        slot_id in _CONTRAST_ALLOWED
        and slot_id not in _PSYCHOLOGICAL_SLOTS
    )

    # Foreign example for attempt 2.
    foreign_example = _get_foreign_example(slot_id) if reask_count == 1 else None

    # Build prompt and call model.
    prompt = _build_judgment_prompt(
        slot_id=slot_id,
        slot_label=slot_label or slot_id,
        judgment_question=judgment_question,
        value=value,
        reask_count=reask_count,
        contrast_allowed=contrast_allowed,
        foreign_example=foreign_example,
    )

    try:
        client = Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        response = client.models.generate_content(
            model=_judgment_model(),
            contents=prompt,
        )
        raw = (response.text or "").strip()

        # Strip markdown fences if present.
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()

        parsed = json.loads(raw)
        satisfied = bool(parsed.get("satisfied", False))
        reask_move = parsed.get("reask_move") if not satisfied else None

        if satisfied:
            return _VALIDATED

        # Not yet satisfied.
        return _provisional(reask_move=reask_move or None)

    except Exception as exc:
        # Model call failed — fail open, mark PROVISIONAL, do not block.
        logger.warning(
            "JUDGMENT call failed for slot %s (reask_count=%d): %s; "
            "marking PROVISIONAL",
            slot_id, reask_count, exc,
        )
        return _provisional(reask_move=None)
