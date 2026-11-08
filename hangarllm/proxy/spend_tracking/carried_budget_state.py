"""Pins the budget state auth resolved onto ``UserAPIKeyAuth`` and emits it as request metadata."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from hangarllm.models.organization import HangarLLM_OrganizationTable
from hangarllm.models.team import HangarLLM_TeamTable
from hangarllm.models.user import HangarLLM_UserTable
from hangarllm.proxy._types import UserAPIKeyAuth
from hangarllm.types.proxy.carried_budget_state import (
    OrgBudgetSnapshot,
    TeamBudgetSnapshot,
    UserBudgetSnapshot,
)


def carry_team_and_user_budget_state(
    valid_token: UserAPIKeyAuth,
    team_object: HangarLLM_TeamTable | None,
    user_object: HangarLLM_UserTable | None,
) -> None:
    if team_object is not None:
        valid_token.team_budget_snapshot = TeamBudgetSnapshot(  # rebind-ok: the request credential is pinned in place
            budget_reset_at=team_object.budget_reset_at,
            max_budget=team_object.max_budget,
        )
        valid_token.team_model_max_budget = team_object.model_max_budget  # rebind-ok: caller keeps this object
    if user_object is not None:
        valid_token.user_budget_snapshot = UserBudgetSnapshot(  # rebind-ok: same object the caller keeps using
            budget_reset_at=user_object.budget_reset_at,
            max_budget=user_object.max_budget,
            user_alias=user_object.user_alias,
        )


def carry_organization_budget_state(valid_token: UserAPIKeyAuth, org_table: HangarLLM_OrganizationTable) -> None:
    budget_table: Final = org_table.hangarllm_budget_table
    valid_token.organization_alias = org_table.organization_alias
    valid_token.org_budget_snapshot = OrgBudgetSnapshot(  # rebind-ok: same object the caller keeps using
        spend=org_table.spend,
        max_budget=budget_table.max_budget if budget_table is not None else None,
    )


def carried_budget_metadata(valid_token: UserAPIKeyAuth) -> Mapping[str, object]:
    snapshots: Final = (
        valid_token.team_budget_snapshot,
        valid_token.user_budget_snapshot,
        valid_token.org_budget_snapshot,
    )
    return MappingProxyType(
        {
            key: value
            for snapshot in snapshots
            if snapshot is not None
            for key, value in snapshot.metadata_entries().items()
        }
    )
