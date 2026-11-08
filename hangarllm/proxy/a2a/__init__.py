"""
A2A registration helpers for the HangarLLM proxy.

- ``discovery``: fetches the upstream agent's well-known card so the UI can
  display its skills/capabilities for the user to pick from.
- ``agent_card``: pure merge logic that builds the HangarLLM-fronted agent card
  from the upstream card + the values the user set in the UI.
- ``endpoints``: FastAPI routes that wire the above into the proxy.
"""

from hangarllm.proxy.a2a.agent_card import (
    HANGARLLM_A2A_PROTOCOL_VERSION,
    HANGARLLM_SECURITY_REQUIREMENTS,
    HANGARLLM_SECURITY_SCHEMES,
    merge_agent_card,
)
from hangarllm.proxy.a2a.discovery import (
    AGENT_CARD_WELL_KNOWN_PATHS,
    fetch_well_known_card,
)

__all__ = [
    "AGENT_CARD_WELL_KNOWN_PATHS",
    "HANGARLLM_A2A_PROTOCOL_VERSION",
    "HANGARLLM_SECURITY_REQUIREMENTS",
    "HANGARLLM_SECURITY_SCHEMES",
    "fetch_well_known_card",
    "merge_agent_card",
]
