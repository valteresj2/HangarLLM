"""
Key-generation defaults applied from the key's team.

* ``organization_id`` - a key created for a team that belongs to an organization
  inherits that organization (so org budgets / reporting include it).
* ``team.metadata.key_defaults`` - optional dict of ``GenerateKeyRequest`` fields
  (e.g. ``{"duration": "30d", "max_budget": 50, "tags": ["team-x"]}``) applied
  to new team keys when the caller did not set them.
"""

from collections.abc import Mapping
from typing import Final

from litellm._logging import verbose_proxy_logger

_DEFAULTABLE_FIELDS: Final = frozenset(
    {
        "duration",
        "max_budget",
        "soft_budget",
        "budget_duration",
        "tpm_limit",
        "rpm_limit",
        "max_parallel_requests",
        "models",
        "tags",
        "allowed_routes",
        "guardrails",
        "key_type",
    }
)


def apply_enterprise_key_management_params(data, team_table):
    if team_table is None:
        return data
    team_org_id: Final = getattr(team_table, "organization_id", None)
    if getattr(data, "organization_id", None) is None and isinstance(team_org_id, str) and team_org_id:
        data.organization_id = team_org_id
    team_metadata: Final = getattr(team_table, "metadata", None)
    defaults: Final = team_metadata.get("key_defaults") if isinstance(team_metadata, Mapping) else None
    if isinstance(defaults, Mapping):
        for field, value in defaults.items():
            if field not in _DEFAULTABLE_FIELDS or not hasattr(data, field):
                continue
            current = getattr(data, field)
            if current is None or current == [] or (field == "models" and current == []):
                try:
                    setattr(data, field, value)
                except Exception as e:  # noqa: BLE001 - invalid default is skipped, never fails key creation
                    verbose_proxy_logger.warning(
                        "HangarLLM: ignoring invalid team key default %s=%r - %s", field, value, e
                    )
    return data


apply_hangar_key_management_params = apply_enterprise_key_management_params
