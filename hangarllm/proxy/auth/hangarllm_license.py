"""
HangarLLM feature entitlement.

HangarLLM is fully open source: every capability that upstream gated behind a
commercial license key is available to every deployment. This module keeps the
``LicenseCheck`` interface that the rest of the proxy calls, but it never phones
home, never limits seats or teams, and grants every feature.

Operators that want to *restrict* features (e.g. to run a lean deployment) can
set ``HANGARLLM_DISABLED_FEATURES`` to a comma-separated list of feature names;
``grants_feature`` then returns False for those names. Everything else stays on.
"""

import os
from typing import TYPE_CHECKING, Final

from hangarllm._logging import verbose_proxy_logger

if TYPE_CHECKING:
    from hangarllm.proxy._types import EnterpriseLicenseData


AUTO_ROUTER_LICENSE_FEATURE: Final = "auto_router"
LICENSE_ALL_FEATURES: Final = "*"
AUTO_ROUTER_LICENSE_REMEDY: Final = (
    "Remove 'auto_router' from HANGARLLM_DISABLED_FEATURES to lift the limit."
)


def _disabled_features() -> frozenset[str]:
    raw: Final = os.getenv("HANGARLLM_DISABLED_FEATURES", "")
    return frozenset(f.strip() for f in raw.split(",") if f.strip())


class LicenseCheck:
    """
    Open-core entitlement check. Every method answers "allowed" unless the
    operator explicitly disabled a feature through HANGARLLM_DISABLED_FEATURES.
    """

    base_url = ""  # HangarLLM never contacts a license server

    def __init__(self) -> None:
        # kept for API compatibility with code that inspects these attributes
        self.license_str: str | None = os.getenv("HANGARLLM_LICENSE") or os.getenv("HANGARLLM_LICENSE") or "hangarllm-open"
        self.public_key = None
        self._premium_check_logged = False
        self.airgapped_license_data: EnterpriseLicenseData | None = None
        verbose_proxy_logger.debug("HangarLLM: all features enabled (open core, no license server)")

    def read_public_key(self) -> None:
        return None

    def is_premium(self) -> bool:
        return True

    def user_seat_limit(self) -> int | None:
        return None

    def is_over_limit(self, total_users: int) -> bool:
        return False

    def is_team_count_over_limit(self, team_count: int) -> bool:
        return False

    def grants_feature(self, feature: str) -> bool:
        return feature not in _disabled_features()

    def auto_router_capability_limit(self) -> int | None:
        if self.grants_feature(AUTO_ROUTER_LICENSE_FEATURE):
            return None
        return 1

    def verify_license_without_api_request(self, public_key, license_key) -> bool:
        return True
