# src/agents/supervisor_judgment.py

"""
Handles the cell-by-cell diagnosis for the Script Supervisor agent.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, NamedTuple, Optional

from google.genai import Client

logger = logging.getLogger(__name__)

class CellInfo(NamedTuple):
    """Information about a cell needed for diagnosis."""
    cell_id: str
    cell_id_num: int
    diagnostic_question: str
    satisfaction_criteria: str
    not_applicable_condition: str | None
    compare_to_position: str | None
    cell_mode: str

@dataclass(frozen=True)
class CellVerdict:
    """The result of a single cell diagnosis."""
    cell_id_num: int
    verdict: str  # SATISFIED | GAP | NA
    evidence: str | None = None


def _get_model() -> str:
    """Model string for JUDGMENT calls."""
    return os.environ.get("GEMINI_TEXT_MODEL", "models/gemini-3.5-flash")

def _build_cell_diagnosis_prompt(
    scene_text: str,
    cell: CellInfo,
    compare_scene_text: Optional[str] = None,
) -> str:
    """Builds the diagnostic prompt for the model."""
    if cell.cell_mode == "TRANSFORMATION" and compare_scene_text:
        task_instruction = f"""
**COMPARISON SCENE TEXT (Position {cell.compare_to_position}):**
---
{compare_scene_text}
---

**TASK:**
Evaluate the main scene against the comparison scene, using the diagnostic lens. The main scene must show a transformation relative to the comparison scene, as described in the satisfaction criteria.
- If the main scene shows the required transformation, the verdict is SATISFIED.
- If it does not, the verdict is GAP.
"""
    else:
        task_instruction = """
**TASK:**
Evaluate the scene against the single diagnostic lens and its satisfaction criteria.
- If the scene meets the criteria, the verdict is SATISFIED.
- If the scene does not meet the criteria, the verdict is GAP.
"""

    return f"""You are a Script Supervisor diagnosing a screenplay scene.

**MAIN SCENE TEXT:**
---
{scene_text}
---

**DIAGNOSTIC LENS:**
{cell.diagnostic_question}

**SATISFACTION CRITERIA:**
{cell.satisfaction_criteria}

{task_instruction}

Your response must be a single JSON object with two fields:
1. "verdict": "SATISFIED" or "GAP".
2. "evidence": A brief, neutral, one-sentence justification for your verdict, quoting or referencing the text directly. The evidence MUST NOT contain suggestions or new ideas. It points to what is present or absent in the scene text provided.

**JSON-ONLY RESPONSE:**
"""

def get_cell_verdict(
    scene_text: str,
    cell: CellInfo,
    compare_scene_text: Optional[str] = None,
) -> CellVerdict:
    """
    Diagnoses a scene against a single cell.
    """
    prompt = _build_cell_diagnosis_prompt(scene_text, cell, compare_scene_text)

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
        verdict = parsed.get("verdict", "GAP").upper()
        evidence = parsed.get("evidence")

        if verdict not in ["SATISFIED", "GAP"]:
            verdict = "GAP" # Default to GAP on invalid verdict

        return CellVerdict(
            cell_id_num=cell.cell_id_num,
            verdict=verdict,
            evidence=evidence
        )

    except Exception as exc:
        logger.warning(
            "Cell diagnosis call failed for cell %s: %s; defaulting to GAP.",
            cell.cell_id, exc
        )
        return CellVerdict(cell_id_num=cell.cell_id_num, verdict="GAP", evidence=str(exc))
