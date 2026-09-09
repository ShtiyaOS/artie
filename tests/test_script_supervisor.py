"""
Tests for the Script Supervisor agent.
"""

import json
import unittest
from unittest.mock import MagicMock, patch, ANY

from src.agents.script_supervisor import ScriptSupervisor
from src.agents.supervisor_judgment import CellInfo, CellVerdict

class TestScriptSupervisor(unittest.TestCase):
    """
    Tests the Script Supervisor's matrix diagnosis functionality.
    """

    def setUp(self):
        """
        Set up mocks for ClickHouse, Supabase clients and Confluent producer.
        """
        self.mock_clickhouse_client = MagicMock()
        self.mock_supabase_client = MagicMock()
        self.mock_producer = MagicMock()
        self.supervisor = ScriptSupervisor(
            clickhouse_client=self.mock_clickhouse_client,
            supabase_client=self.mock_supabase_client,
            producer=self.mock_producer
        )
        self.project_id = "test_project_uuid"
        self.scene_id = "test_scene_uuid"

    def test_supervisor_initialization(self):
        """
        Tests that the supervisor is initialized correctly.
        """
        self.assertIsNotNone(self.supervisor)
        self.assertEqual(self.supervisor.clickhouse_client, self.mock_clickhouse_client)
        self.assertEqual(self.supervisor.supabase_client, self.mock_supabase_client)
        self.assertEqual(self.supervisor.producer, self.mock_producer)

    def test_get_input_confidence_validated(self):
        """
        Tests input confidence is VALIDATED when all consumed slots are validated.
        """
        self.mock_clickhouse_client.execute_query.return_value = [("S02",), ("S03",)]
        self.mock_supabase_client.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
            {"input_conf": "VALIDATED"},
            {"input_conf": "VALIDATED"},
        ]
        confidence = self.supervisor._get_input_confidence(1, self.project_id)
        self.assertEqual(confidence, "VALIDATED")

    def test_get_input_confidence_provisional(self):
        """
        Tests input confidence is PROVISIONAL if any consumed slot is provisional.
        """
        self.mock_clickhouse_client.execute_query.return_value = [("S02",), ("S04",)]
        self.mock_supabase_client.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
            {"input_conf": "VALIDATED"},
            {"input_conf": "PROVISIONAL"},
        ]
        confidence = self.supervisor._get_input_confidence(2, self.project_id)
        self.assertEqual(confidence, "PROVISIONAL")

    def test_get_input_confidence_no_slots(self):
        """
        Tests input confidence is VALIDATED when no slots are consumed.
        """
        self.mock_clickhouse_client.execute_query.return_value = []
        confidence = self.supervisor._get_input_confidence(3, self.project_id)
        self.assertEqual(confidence, "VALIDATED")

    def test_evaluate_na_condition_met(self):
        """
        Tests the NA condition is met for X12.Y5 and visual silence.
        """
        condition = "X12.Y5 visual silence"
        scene_text = " \n "
        self.assertTrue(self.supervisor._evaluate_na_condition(scene_text, condition))

    def test_evaluate_na_condition_not_met(self):
        """
        Tests the NA condition is not met when scene has text.
        """
        condition = "X12.Y5 visual silence"
        scene_text = "Some text."
        self.assertFalse(self.supervisor._evaluate_na_condition(scene_text, condition))

    @patch('src.agents.script_supervisor.get_cell_verdict')
    def test_diagnose_scene_full_flow(self, mock_get_cell_verdict):
        """
        Tests the full diagnose_scene flow with activation, transformation, and NA cells.
        """
        scene_payload = {
            "project_id": self.project_id,
            "scene_id": self.scene_id,
            "bible_version_id": 1,
            "position_id": 12,
            "scene_text": "A scene with action.",
        }

        # Mock data
        mock_cells = [
            CellInfo("X12.Y1", 61, "Q1", "C1", None, "X01", "TRANSFORMATION"),
            CellInfo("X12.Y2", 62, "Q2", "C2", None, None, "ACTIVATION"),
            CellInfo("X12.Y5", 65, "Q5", "C5", "For script ending in visual silence.", None, "ACTIVATION"),
        ]
        self.supervisor._get_cells_for_position = MagicMock(return_value=mock_cells)
        self.supervisor._get_input_confidence = MagicMock(side_effect=["VALIDATED", "PROVISIONAL", "VALIDATED"])
        self.supervisor._get_scene_text = MagicMock(return_value="Compare scene text.")

        mock_get_cell_verdict.side_effect = [
            CellVerdict(cell_id_num=61, verdict="SATISFIED", evidence="Transformed."),
            CellVerdict(cell_id_num=62, verdict="GAP", evidence="No conflict."),
            CellVerdict(cell_id_num=65, verdict="GAP", evidence="Scene has text."),
        ]

        # Execute
        self.supervisor.diagnose_scene(scene_payload)

        # Assertions
        # Check that get_cell_verdict was called for all three cells
        self.assertEqual(mock_get_cell_verdict.call_count, 3)
        
        # Check producer call
        self.mock_producer.produce.assert_called_once()
        call_args = self.mock_producer.produce.call_args
        self.assertEqual(call_args.kwargs['topic'], 'scene_diagnoses')
        self.assertEqual(call_args.kwargs['key'], self.scene_id)
        
        event_value = json.loads(call_args.kwargs['value'])
        self.assertEqual(event_value['project_id'], self.project_id)
        self.assertEqual(event_value['scene_id'], self.scene_id)
        self.assertEqual(len(event_value['cell_verdicts']), 3)

        # Verdict 1 (Transformation)
        self.assertEqual(event_value['cell_verdicts'][0]['cell_id_num'], 61)
        self.assertEqual(event_value['cell_verdicts'][0]['verdict'], 'SATISFIED')
        self.assertEqual(event_value['cell_verdicts'][0]['input_confidence'], 'VALIDATED')
        self.assertEqual(event_value['cell_verdicts'][0]['evidence'], 'Transformed.')

        # Verdict 2 (Activation)
        self.assertEqual(event_value['cell_verdicts'][1]['cell_id_num'], 62)
        self.assertEqual(event_value['cell_verdicts'][1]['verdict'], 'GAP')
        self.assertEqual(event_value['cell_verdicts'][1]['input_confidence'], 'PROVISIONAL')
        self.assertEqual(event_value['cell_verdicts'][1]['evidence'], 'No conflict.')

        # Verdict 3 (NA condition not met)
        self.assertEqual(event_value['cell_verdicts'][2]['cell_id_num'], 65)
        self.assertEqual(event_value['cell_verdicts'][2]['verdict'], 'GAP')
        self.assertEqual(event_value['cell_verdicts'][2]['input_confidence'], 'VALIDATED')
        self.assertEqual(event_value['cell_verdicts'][2]['evidence'], 'Scene has text.')


if __name__ == '__main__':
    unittest.main()
