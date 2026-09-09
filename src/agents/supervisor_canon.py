# src/agents/supervisor_canon.py

"""
Handles the canon check for the Script Supervisor agent.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple

from google.genai import Client

logger = logging.getLogger(__name__)


class WorldRule(NamedTuple):
    """Information about a world rule for canon checking."""
    rule_id: str
    rule_type: str  # A_POSSIBILITY | B_CONSEQUENCE
    condition: str
    outcome: str
    is_active: bool


@dataclass(frozen=True)
class CanonFinding:
    """The result of a single world rule evaluation."""
    rule_id: str
    rule_type: str
    status: str  # VIOLATED | UNTRIGGERED
    detail: str


def _get_model() -> str:
    """Model string for CANON calls."""
    return os.environ.get("GEMINI_TEXT_MODEL", "models/gemini-3.5-flash")


def _build_canon_check_prompt(scene_text: str, rules: List[WorldRule]) -> str:
    """Builds the canon check prompt for the model."""
    
    rules_text = []
    for rule in rules:
        if rule.rule_type == "A_POSSIBILITY":
            rule_description = f"Type A (A_POSSIBILITY): If `{rule.condition}`, then `{rule.outcome}` is IMPOSSIBLE."
        elif rule.rule_type == "B_CONSEQUENCE":
            rule_description = f"Type B (B_CONSEQUENCE): If `{rule.condition}`, then `{rule.outcome}` MUST follow."
        else:
            continue
        rules_text.append(f'- **Rule ID `{rule.rule_id}`**: {rule_description}')

    rules_section = "\n".join(rules_text)

    return f"""You are a Script Supervisor diagnosing a screenplay scene for canon violations.

**SCENE TEXT:**
---
{scene_text}
---

**ACTIVE WORLD RULES:**
{rules_section}

**TASK:**
Evaluate the scene against all the active world rules. Identify every rule that has been breached.
- For Type A rules, a breach means the impossible outcome occurred.
- For Type B rules, a breach means the established consequence failed to trigger.

Your response must be a single JSON object with one key, "canon_findings". This key should contain a list of objects, where each object represents a single rule breach. If no rules are breached, return an empty list.

Each finding object must have four fields:
1. "rule_id": The ID of the breached rule.
2. "rule_type": The type of the breached rule ("A_POSSIBILITY" or "B_CONSEQUENCE").
3. "status": "VIOLATED" for a Type A breach, or "UNTRIGGERED" for a Type B breach.
4. "detail": A brief, neutral, one-sentence justification for the finding, explaining what happened or didn't happen in the scene. The detail MUST NOT contain suggestions or new ideas.

**EXAMPLE FINDING:**
{{
  "rule_id": "...",
  "rule_type": "B_CONSEQUENCE",
  "status": "UNTRIGGERED",
  "detail": "The character was exposed to sunlight but did not turn to dust."
}}

**JSON-ONLY RESPONSE:**
"""

def get_canon_findings(scene_text: str, rules: List[WorldRule]) -> List[CanonFinding]:
    """
    Evaluates a scene against a set of world rules.
    """
    if not rules:
        return []

    prompt = _build_canon_check_prompt(scene_text, rules)

    try:
        client = Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        response = client.models.generate_content(
            model=_get_model(),
            contents=prompt,
        )
        raw = (response.text or "").strip()

        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()

        parsed = json.loads(raw)
        findings_data = parsed.get("canon_findings", [])
        
        findings = []
        for item in findings_data:
            findings.append(CanonFinding(
                rule_id=item.get("rule_id"),
                rule_type=item.get("rule_type"),
                status=item.get("status"),
                detail=item.get("detail"),
            ))
        return findings

    except Exception as exc:
        logger.warning("Canon check call failed: %s; returning no findings.", exc)
        return []

