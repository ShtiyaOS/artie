# src/agents/script_supervisor.py

"""
The Script Supervisor agent, responsible for matrix diagnosis.
"""

import json
import logging
from typing import Any, Dict, List

from src.agents.supervisor_judgment import (
    CellInfo,
    CellVerdict,
    get_cell_verdict,
)

logger = logging.getLogger(__name__)


class ScriptSupervisor:
    """
    Evaluates a scene against the six cells for its declared position and
    emits a SCENE_DIAGNOSED event with structured verdicts.
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
            return "PROVISIONAL" # Fail safe

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
                    # This is a simplification. We need a way to find a scene_id
                    # for a given position_id. This likely needs another lookup.
                    # For now, we assume we can get it.
                    # This logic is also flawed because it doesn't specify *which* scene.
                    # Let's assume we get the *first* scene for that position.
                    # This part of the design is underspecified in the prompt.
                    # I'll add a placeholder here.
                    logger.warning("TRANSFORMATION mode logic is a placeholder.")
                    # compare_scene_id = self._get_scene_id_for_position(project_id, cell.compare_to_position)
                    # if compare_scene_id:
                    #    compare_scene_text = self._get_scene_text(project_id, compare_scene_id)
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

        event_payload = {
            "project_id": project_id,
            "scene_id": scene_id,
            "bible_version_id": bible_version_id,
            "position_id": position_id,
            "cell_verdicts": cell_verdicts,
        }

        self.producer.produce(
            topic="scene_diagnoses",
            key=str(scene_id),
            value=json.dumps(event_payload),
        )
        logger.info(
            "Published SCENE_DIAGNOSED event for scene %s", scene_id
        )
