"""
Tests for the main event router in src/main.py.
"""
import json
import unittest
from unittest.mock import AsyncMock, patch
import asyncio

from src.main import handle_scene_diagnosed

class EventHandlerTest(unittest.TestCase):
    @patch("src.main.get_cell_definitions")
    @patch("src.main.artie.invoke", new_callable=AsyncMock)
    def test_handle_scene_diagnosed_event_unit(self, mock_artie_invoke, mock_get_cell_defs):
        """
        Tests that a SCENE_DIAGNOSED event is correctly processed, stripped,
        and handed off to Artie by directly calling the handler.
        """
        # 1. Mock the dependencies
        mock_get_cell_defs.return_value = {
            62: {
                "cell_id_num": 62,
                "cell_id": "X06.Y2",
                "confidence": "ATTESTED",
                "priority_weight": 5,
                "failure_signature": "Does the scene establish the protagonist's active goal?"
            },
            63: {
                "cell_id_num": 63,
                "cell_id": "X06.Y3",
                "confidence": "ANCHORED",
                "priority_weight": 3,
                "failure_signature": "Does the midpoint reveal new information about the theme?"
            }
        }

        # 2. Define the input event
        supervisor_findings = {
            "cell_verdicts": [
                {
                    "cell_id_num": 62,
                    "verdict": "GAP",
                    "input_confidence": "VALIDATED",
                    "evidence": "The protagonist seems to be reacting, not planning."
                },
                {
                    "cell_id_num": 63,
                    "verdict": "SATISFIED",
                    "input_confidence": "PROVISIONAL",
                    "evidence": "The mention of 'freedom' connects to the theme of liberation."
                }
            ],
            "canon_findings": []
        }
        
        # The structure of the event payload needs to match what the handler expects.
        # Based on supervisor.py, the payload has `response_text` which is a JSON string.
        supervisor_event_payload = {
            "response_text": json.dumps(supervisor_findings)
        }

        event_envelope = {
            "event_id": "test-event-123",
            "event_type": "SCENE_DIAGNOSED",
            "project_id": "test-project-uuid",
            "scene_id": "test-scene-uuid",
            "bible_version_id": 42,
            "actor": "supervisor",
            "ts_micros": 123456789,
            "payload": supervisor_event_payload
        }

        # 3. Call the handler function directly
        asyncio.run(handle_scene_diagnosed(event_envelope))

        # 4. Assert that dependencies were called correctly
        mock_get_cell_defs.assert_called_once_with([62, 63])
        mock_artie_invoke.assert_awaited_once()

        # 5. Assert the payload sent to Artie is correct
        invoke_kwargs = mock_artie_invoke.call_args.kwargs
        artie_payload = invoke_kwargs.get("payload", {})
        
        self.assertIn("pending_findings", artie_payload)
        self.assertEqual(len(artie_payload["pending_findings"]), 2)

        finding1 = artie_payload["pending_findings"][0]
        finding2 = artie_payload["pending_findings"][1]

        # Check that 'evidence' is stripped and other fields are correct
        self.assertNotIn("evidence", finding1)
        self.assertEqual(finding1["cell_id"], "X06.Y2")
        self.assertEqual(finding1["verdict"], "GAP")
        self.assertEqual(finding1["cell_confidence"], "ATTESTED")
        self.assertEqual(finding1["input_confidence"], "VALIDATED")
        self.assertEqual(finding1["priority_weight"], 5)
        self.assertEqual(finding1["display_confidence"], "ATTESTED")

        self.assertNotIn("evidence", finding2)
        self.assertEqual(finding2["cell_id"], "X06.Y3")
        self.assertEqual(finding2["verdict"], "SATISFIED")
        self.assertEqual(finding2["cell_confidence"], "ANCHORED")
        self.assertEqual(finding2["input_confidence"], "PROVISIONAL")
        self.assertEqual(finding2["priority_weight"], 3)
        self.assertEqual(finding2["display_confidence"], "EXTRAPOLATED")
        
        from src.agents.firewall import assert_no_prose, FirewallBreach
        try:
            assert_no_prose(artie_payload)
        except FirewallBreach as e:
            self.fail(f"FirewallBreach was raised unexpectedly: {e}")

if __name__ == "__main__":
    unittest.main()
