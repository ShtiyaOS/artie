# src/agents/script_supervisor.py

"""
The Script Supervisor agent, responsible for matrix diagnosis and canon checking.
"""

import json
import logging
from typing import Any, Dict, List

from src.agents.supervisor_canon import CanonFinding, WorldRule, get_canon_findings
from src.agents.supervisor_judgment import (
    CellInfo,
    CellVerdict,
    get_cell_verdict,
)

logger = logging.getLogger(__name__)


class ScriptSupervisor:
    """
    Evaluates a scene against the six cells for its declared position,
    checks for canon violations against world rules, and emits a
    SCENE_DIAGNOSED event with structured verdicts and findings.
    """

    def __init__(self, clickhouse_client: Any, supabase_client: Any, producer: Any):
        self.clickhouse_client = clickhouse_client
        self.supabase_client = supabase_client
        self.producer = producer

    def _get_cells_for_position(self, position_id: int) -> List[CellInfo]:
        """Fetches the 6 cells for a given narrative position."""
        query = f"""
        SELECT
            cell_id,
            cell_id_num,
            diagnostic_question,
            satisfaction_criteria,
            not_applicable_condition,
            compare_to_position,
            cell_mode
        FROM cells_src
        WHERE position_id = %(position_id)s
        """
        params = {"position_id": position_id}
        results = self.clickhouse_client.execute_query(query, params)
        return [CellInfo(*row) for row in results]

    def _get_world_rules(self, project_id: str) -> List[WorldRule]:
        """Fetches up to 10 active world rules for a project."""
        try:
            rows = (
                self.supabase_client.table("world_rules")
                .select("rule_id, rule_type, condition, outcome, is_active")
                .eq("project_id", project_id)
                .eq("is_active", True)
                .limit(10)
                .execute()
                .data
            )
            return [WorldRule(**row) for row in rows]
        except Exception as e:
            logger.error(f"Could not get world rules for project {project_id}: {e}")
            return []

    def _get_input_confidence(self, cell_id_num: int, project_id: str) -> str:
        """
        Determines the input confidence for a cell based on its consumed slots.
        If any consumed slot is PROVISIONAL, the cell's confidence is PROVISIONAL.
        """
        slot_query = """
        SELECT slot_id FROM cell_slot_consumption WHERE cell_id_num = %(cell_id_num)s
        """
        consumed_slots = self.clickhouse_client.execute_query(
            slot_query, {"cell_id_num": cell_id_num}
        )
        if not consumed_slots:
            return "VALIDATED"

        slot_ids = [row[0] for row in consumed_slots]

        try:
            rows = (
                self.supabase_client.table("bible_slots")
                .select("input_conf")
                .eq("project_id", project_id)
                .in_("slot_id", slot_ids)
                .execute()
                .data
            )
            for row in rows:
                if row.get("input_conf") == "PROVISIONAL":
                    return "PROVISIONAL"
            return "VALIDATED"
        except Exception as e:
            logger.error(f"Could not get input confidence for cell {cell_id_num}: {e}")
            return "PROVISIONAL"  # Fail safe

    def _evaluate_na_condition(self, scene_text: str, condition: str) -> bool:
        """
        Evaluates the not_applicable_condition for a cell.
        A very basic implementation for the one known case.
        """
        if "X12.Y5" in condition and "visual silence" in condition:
            return not scene_text.strip()
        return False

    def _get_scene_text(self, project_id: str, scene_id: str) -> str:
        """Placeholder function to get scene text by ID."""
        # In a real implementation, this would query the database for the scene text.
        # For testing, this can be mocked to return specific text.
        logger.warning("Using placeholder for _get_scene_text")
        return ""

    def diagnose_scene(self, scene_payload: Dict[str, Any]):
        """
        Diagnoses a single scene and emits a verdict.
        """
        project_id = scene_payload["project_id"]
        scene_id = scene_payload["scene_id"]
        bible_version_id = scene_payload["bible_version_id"]
        position_id = scene_payload["position_id"]
        scene_text = scene_payload["scene_text"]

        # 1. Matrix Diagnosis
        cells = self._get_cells_for_position(position_id)
        cell_verdicts: List[Dict[str, Any]] = []

        for cell in cells:
            verdict: CellVerdict
            if cell.not_applicable_condition and self._evaluate_na_condition(
                scene_text, cell.not_applicable_condition
            ):
                verdict = CellVerdict(
                    cell_id_num=cell.cell_id_num, verdict="NA", evidence=None
                )
            else:
                compare_scene_text = None
                if cell.cell_mode == "TRANSFORMATION" and cell.compare_to_position:
                    logger.warning("TRANSFORMATION mode logic is a placeholder.")
                    pass

                verdict = get_cell_verdict(scene_text, cell, compare_scene_text)

            input_confidence = self._get_input_confidence(cell.cell_id_num, project_id)

            cell_verdicts.append(
                {
                    "cell_id_num": verdict.cell_id_num,
                    "verdict": verdict.verdict,
                    "input_confidence": input_confidence,
                    "evidence": verdict.evidence,
                }
            )

        # 2. Canon Check
        world_rules = self._get_world_rules(project_id)
        canon_findings_raw = get_canon_findings(scene_text, world_rules)
        canon_findings = [finding.__dict__ for finding in canon_findings_raw]


        # 3. Emit Event
        event_payload = {
            "project_id": project_id,
            "scene_id": scene_id,
            "bible_version_id": bible_version_id,
            "position_id": position_id,
            "cell_verdicts": cell_verdicts,
            "canon_findings": canon_findings,
        }

        self.producer.produce(
            topic="scene_diagnoses",
            key=str(scene_id),
            value=json.dumps(event_payload),
        )
        logger.info(
            "Published SCENE_DIAGNOSED event for scene %s with %d verdicts and %d canon findings.",
            scene_id, len(cell_verdicts), len(canon_findings)
        )
