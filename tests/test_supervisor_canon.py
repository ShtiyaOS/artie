# tests/test_supervisor_canon.py

import json
from unittest.mock import MagicMock, patch

from src.agents.supervisor_canon import (
    CanonFinding,
    WorldRule,
    get_canon_findings,
)


def mock_generate_content(findings: list):
    """Factory to create a mock for the generate_content client method."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({"canon_findings": findings})
    
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    return mock_client

# Test Cases
def test_get_canon_findings_no_violations():
    """
    GIVEN a scene and rules where no rules are violated
    WHEN get_canon_findings is called
    THEN it should return an empty list.
    """
    scene_text = "The vampire entered the room. It was daytime, but the curtains were drawn."
    rules = [
        WorldRule("1", "B_CONSEQUENCE", "vampire is exposed to sunlight", "turns to dust", True),
    ]
    
    mock_client = mock_generate_content([])
    
    with patch("src.agents.supervisor_canon.Client", return_value=mock_client) as mock_google_client:
        findings = get_canon_findings(scene_text, rules)
        assert findings == []
        mock_google_client.assert_called_once()
        # We can also inspect the prompt passed to the model
        prompt = mock_client.models.generate_content.call_args[1]['contents']
        assert "vampire is exposed to sunlight" in prompt
        assert "turns to dust" in prompt

def test_get_canon_findings_b_consequence_untriggered():
    """
    GIVEN a scene that violates a B_CONSEQUENCE rule
    WHEN get_canon_findings is called
    THEN it should return a finding with status UNTRIGGERED.
    """
    scene_text = "The vampire walked in the sun, admiring the day."
    rules = [
        WorldRule("1", "B_CONSEQUENCE", "vampire is exposed to sunlight", "turns to dust", True),
    ]
    expected_finding = {
        "rule_id": "1",
        "rule_type": "B_CONSEQUENCE",
        "status": "UNTRIGGERED",
        "detail": "A vampire was exposed to sunlight but did not turn to dust.",
    }
    
    mock_client = mock_generate_content([expected_finding])

    with patch("src.agents.supervisor_canon.Client", return_value=mock_client):
        findings = get_canon_findings(scene_text, rules)
        assert len(findings) == 1
        finding = findings[0]
        assert isinstance(finding, CanonFinding)
        assert finding.rule_id == "1"
        assert finding.rule_type == "B_CONSEQUENCE"
        assert finding.status == "UNTRIGGERED"
        assert "did not turn to dust" in finding.detail

def test_get_canon_findings_a_possibility_violated():
    """
    GIVEN a scene that violates an A_POSSIBILITY rule
    WHEN get_canon_findings is called
    THEN it should return a finding with status VIOLATED.
    """
    scene_text = "The human character lifted a car with one hand."
    rules = [
        WorldRule("2", "A_POSSIBILITY", "a human character is unaided", "can lift a car", True),
    ]
    expected_finding = {
        "rule_id": "2",
        "rule_type": "A_POSSIBILITY",
        "status": "VIOLATED",
        "detail": "A human character lifted a car, which is impossible.",
    }
    
    mock_client = mock_generate_content([expected_finding])

    with patch("src.agents.supervisor_canon.Client", return_value=mock_client):
        findings = get_canon_findings(scene_text, rules)
        assert len(findings) == 1
        finding = findings[0]
        assert isinstance(finding, CanonFinding)
        assert finding.rule_id == "2"
        assert finding.rule_type == "A_POSSIBILITY"
        assert finding.status == "VIOLATED"
        assert "lifted a car" in finding.detail

def test_get_canon_findings_no_rules():
    """
    GIVEN a scene but no active rules
    WHEN get_canon_findings is called
    THEN it should return an empty list without calling the model.
    """
    scene_text = "Anything can happen here."
    rules = []
    
    with patch("src.agents.supervisor_canon.Client") as mock_google_client:
        findings = get_canon_findings(scene_text, rules)
        assert findings == []
        mock_google_client.assert_not_called()

def test_get_canon_findings_api_failure():
    """
    GIVEN the model API call fails
    WHEN get_canon_findings is called
    THEN it should log a warning and return an empty list.
    """
    scene_text = "The test will fail."
    rules = [
        WorldRule("1", "B_CONSEQUENCE", "a test runs", "it must succeed", True),
    ]

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("API Error")

    with patch("src.agents.supervisor_canon.Client", return_value=mock_client):
        with patch("src.agents.supervisor_canon.logger") as mock_logger:
            findings = get_canon_findings(scene_text, rules)
            assert findings == []
            mock_logger.warning.assert_called_once()
            assert "Canon check call failed" in mock_logger.warning.call_args[0][0]
