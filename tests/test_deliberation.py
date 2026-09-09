
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from src.deliberation import get_active_axes, generate_poles

class TestDeliberation(unittest.TestCase):

    def test_get_active_axes_no_findings(self):
        payload = {}
        self.assertEqual(get_active_axes(payload), [])

    def test_get_active_axes_pending_findings(self):
        payload = {"pending_findings": [{"id": 1}]}
        self.assertEqual(get_active_axes(payload), ["A1"])

    def test_get_active_axes_anchored_finding(self):
        payload = {"pending_findings": [{"id": 1, "status": "ANCHORED"}]}
        self.assertEqual(get_active_axes(payload), ["A1", "A4"])

    def test_get_active_axes_greenlight_slot(self):
        payload = {"gate": "GREENLIGHT", "slot_id": "S01"}
        self.assertEqual(get_active_axes(payload), ["A2"])

    def test_get_active_axes_multiple_triggers(self):
        payload = {
            "pending_findings": [{"id": 1, "status": "ANCHORED"}],
            "gate": "GREENLIGHT",
            "slot_id": "S01"
        }
        # A1, A2, A4 are triggered, but capped at 2, with A1 and A4 being the strongest
        self.assertEqual(get_active_axes(payload), ["A1", "A4"])

    def test_get_active_axes_no_triggers(self):
        payload = {"gate": "SCENE_RIG", "foo": "bar"}
        self.assertEqual(get_active_axes(payload), [])

    @patch('src.deliberation.LlmAgent')
    async def test_generate_poles(self, mock_llm_agent):
        mock_agent_instance = MagicMock()
        mock_llm_agent.return_value = mock_agent_instance

        mock_response = MagicMock()
        mock_response.parts = [MagicMock()]
        mock_response.parts[0].text = '```json\n{"axis": "A1", "poles": []}```'

        mock_agent_instance.send = AsyncMock(return_value=mock_response)

        mock_session = MagicMock()
        mock_session.session_id = "test_session_id"

        async with patch('src.deliberation.get_session_for_user', new_callable=AsyncMock) as mock_get_session:
            mock_get_session.return_value = mock_session

            axes = ["A1"]
            payload = {"pending_findings": [{"id": 1}]}

            result = await generate_poles(axes, payload=payload, user_id="test_user")

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["axis"], "A1")
            mock_llm_agent.assert_called_with(
                name='pole_A1',
                model='gemini-text-model',
                instruction='You are one side of an argument about how to give feedback to a writer.'
            )

if __name__ == '__main__':
    unittest.main()

