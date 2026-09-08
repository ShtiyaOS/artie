"""
Artie prose firewall — docs/05_orchestration.md §6.

This module is the single authoritative implementation of assert_no_prose.
It is imported by src/agents/artie.py and tested by tests/test_firewall.py.

Design contract (from the spec, verbatim):
  "It must raise, never sanitize. A silent strip would let the wiring drift
   and the firewall would erode without anyone noticing. A loud failure
   surfaces the regression the moment it is introduced."

Demo artifact:
  This function is the assertion that fails if the screenplay ever reaches
  the agent that talks to the writer. It is a stronger claim than any
  paragraph of policy.
"""

# Forbidden keys — any key in this set, at any nesting depth, is a
# structural violation of the Artie reading boundary.
# Canonical list: docs/05_orchestration.md §6.
FORBIDDEN_KEYS: frozenset[str] = frozenset({
    "scene_text",
    "script",
    "prose",
    "evidence",
    "action_lines",
    "dialogue",
    "draft",
    "content",
})


class FirewallBreach(ValueError):
    """
    Raised when a forbidden prose field reaches Artie's payload.

    The message names the exact dotted path so a regression is immediately
    locatable without a debugger.
    """


def assert_no_prose(payload: dict, path: str = "") -> None:
    """
    Recursively walk *payload* and raise FirewallBreach on the first
    occurrence of any key in FORBIDDEN_KEYS.

    Checks:
      - Top-level keys
      - Keys inside nested dicts (any depth)
      - Keys inside dicts that appear in list values (any depth)

    Args:
        payload: The dict to inspect.
        path:    Dotted key path of the current dict within the root
                 (empty string for the root itself). Used in the error
                 message; callers should leave it at the default.

    Raises:
        FirewallBreach: On the first forbidden key found, with its full
                        dotted path included in the message.
    """
    for k, v in payload.items():
        here = f"{path}.{k}" if path else k
        if k in FORBIDDEN_KEYS:
            raise FirewallBreach(
                f"Prose field '{here}' reached Artie's payload"
            )
        if isinstance(v, dict):
            assert_no_prose(v, here)
        if isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    assert_no_prose(item, f"{here}[{i}]")
