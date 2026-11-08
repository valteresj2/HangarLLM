"""
Passthrough table repositories.

Each repository centralizes access to a single Prisma table behind a ``table``
property, making the repository the one place that names the underlying table.
These are thin wrappers for tables that do not (yet) need domain-specific query
methods; richer repositories live in their own modules.
"""

from collections.abc import Mapping, Sequence
from datetime import timedelta
from itertools import groupby
from typing import TYPE_CHECKING, Any, Final, Generic, Protocol

from pydantic import TypeAdapter

from hangarllm.hangarllm_core_utils.core_helpers import require_attributes
from hangarllm.hangarllm_core_utils.safe_json_dumps import safe_dumps
from hangarllm.repositories.accounting_delivery_repository import LedgerDatabase, LedgerTransaction
from hangarllm.repositories.prisma_protocols import RowT_co, TableActions

if TYPE_CHECKING:
    from prisma import models as prisma_models  # noqa: F401  # used by quoted base-class subscripts


class _PrismaReaderClientView(Protocol):
    @property
    def db(self) -> object: ...


class _PrismaWriterClientView(Protocol):
    @property
    def writer_db(self) -> object: ...


class PrismaTableRepository(Generic[RowT_co]):
    """Base for repositories that expose a single Prisma table."""

    table_name: str

    def __init__(self, prisma_client: object, *, use_writer: bool = False) -> None:
        self._prisma_client = prisma_client
        self._use_writer = use_writer

    def _connected_client(self) -> object:
        if self._prisma_client is None:
            raise RuntimeError("No DB Connected. See - https://github.com/valteresj2/HangarLLM#readme")
        return self._prisma_client

    @property
    def prisma_client(self) -> Any:
        return self._connected_client()

    def _selected_database(self) -> object:
        client: Final = self._connected_client()
        if self._use_writer:
            return require_attributes(client, _PrismaWriterClientView, "writer_db").writer_db
        return require_attributes(client, _PrismaReaderClientView, "db").db

    @property
    def table(self) -> TableActions[RowT_co]:
        from hangarllm.proxy.common_utils.config_sync_pubsub import wrap_table_actions_for_config_sync

        actions: Final[TableActions[RowT_co]] = getattr(self._selected_database(), self.table_name)
        return wrap_table_actions_for_config_sync(actions=actions, table_name=self.table_name)


class PolicyRepository(PrismaTableRepository["prisma_models.HangarLLM_PolicyTable"]):
    table_name = "hangarllm_policytable"


class AgentsRepository(PrismaTableRepository["prisma_models.HangarLLM_AgentsTable"]):
    table_name = "hangarllm_agentstable"


class AgentIdentityRepository(PrismaTableRepository["prisma_models.HangarLLM_AgentIdentity"]):
    table_name = "hangarllm_agentidentity"


class RetiredAgentIdentityRepository(PrismaTableRepository["prisma_models.HangarLLM_RetiredAgentIdentity"]):
    table_name = "hangarllm_retiredagentidentity"


class VerifiedSubjectRepository(PrismaTableRepository["prisma_models.HangarLLM_VerifiedSubject"]):
    table_name = "hangarllm_verifiedsubject"


class ObjectPermissionRepository(PrismaTableRepository["prisma_models.HangarLLM_ObjectPermissionTable"]):
    table_name = "hangarllm_objectpermissiontable"


class GuardrailsRepository(PrismaTableRepository["prisma_models.HangarLLM_GuardrailsTable"]):
    table_name = "hangarllm_guardrailstable"


class MCPServerRepository(PrismaTableRepository["prisma_models.HangarLLM_MCPServerTable"]):
    table_name = "hangarllm_mcpservertable"


class ManagedObjectRepository(PrismaTableRepository["prisma_models.HangarLLM_ManagedObjectTable"]):
    table_name = "hangarllm_managedobjecttable"


class OrganizationMembershipRepository(PrismaTableRepository["prisma_models.HangarLLM_OrganizationMembership"]):
    table_name = "hangarllm_organizationmembership"


_SPEND_LOG_FIELDS: Final = TypeAdapter(dict[str, object])


def _accounting_payload(value: object) -> Mapping[str, object]:
    return (
        _SPEND_LOG_FIELDS.validate_json(value) if isinstance(value, str) else _SPEND_LOG_FIELDS.validate_python(value)
    )


_ACCOUNTING_ONLY_FIELDS: Final = frozenset({"accounting_payload", "accounting_log_disabled", "accounting_delivery_id"})


def _settles_once(row: Mapping[str, object]) -> bool:
    """A batch or video cost row: update_database gives every other ledger row its own delivery id."""
    return "accounting_delivery_id" not in row


def _delivery_id(row: Mapping[str, object]) -> str:
    return str(row["accounting_delivery_id"]) if not _settles_once(row) else str(row["request_id"])


class SpendLogsRepository(PrismaTableRepository["prisma_models.HangarLLM_SpendLogs"]):
    table_name = "hangarllm_spendlogs"

    async def insert_with_deliveries(
        self, rows: Sequence[Mapping[str, object]], *, write_spend_logs: bool = True
    ) -> int:
        legacy: Final = tuple(row for row in rows if "accounting_payload" not in row)
        legacy_count: Final = await self.table.create_many(data=legacy, skip_duplicates=True) if legacy else 0
        ledger: Final = tuple(
            sorted(
                {_delivery_id(row): row for row in reversed(rows) if "accounting_payload" in row}.values(),
                key=_delivery_id,
            )
        )
        if not ledger:
            return legacy_count
        database: Final[LedgerDatabase] = self.prisma_client.writer_db
        async with database.tx(timeout=timedelta(seconds=60)) as transaction:
            accepted: Final = await self._insert_ledger(transaction, ledger, write_spend_logs=write_spend_logs)
        return legacy_count + accepted

    @staticmethod
    async def _insert_ledger(
        transaction: LedgerTransaction, rows: Sequence[Mapping[str, object]], *, write_spend_logs: bool
    ) -> int:
        from hangarllm.proxy.db.db_span import db_span
        from hangarllm.repositories.spend_log_insert import spend_log_insert_statement

        payloads: Final = tuple(
            {
                "delivery_id": _delivery_id(row),
                "request_id": row["request_id"],
                "accounting_payload": _accounting_payload(row["accounting_payload"]),
                "is_batch": _settles_once(row),
            }
            for row in rows
        )
        inserted_deliveries: Final = await transaction.query_raw(
            'INSERT INTO "HangarLLM_SpendLogDelivery" (delivery_id, request_id, accounting_payload, is_batch) '
            "SELECT delivery_id, request_id, accounting_payload, is_batch FROM jsonb_to_recordset($1::jsonb) "
            "AS inputs(delivery_id text, request_id text, accounting_payload jsonb, is_batch boolean) "
            "ON CONFLICT (delivery_id) DO NOTHING RETURNING delivery_id",
            safe_dumps(payloads, non_finite_as_null=True),
        )
        accepted_ids: Final = frozenset(str(row["delivery_id"]) for row in inserted_deliveries)
        charged_by_legacy: Final = await SpendLogsRepository._jobs_charged_by_legacy(
            transaction,
            tuple(_delivery_id(row) for row in rows if _settles_once(row) and _delivery_id(row) in accepted_ids),
        )
        if charged_by_legacy:
            await transaction.execute_raw(
                'DELETE FROM "HangarLLM_SpendLogDelivery" WHERE delivery_id = ANY($1::text[])', list(charged_by_legacy)
            )
        accepted: Final = accepted_ids - charged_by_legacy
        local_rows: Final = tuple(
            {key: value for key, value in row.items() if key not in _ACCOUNTING_ONLY_FIELDS}
            for row in rows
            if _delivery_id(row) in accepted and row.get("accounting_log_disabled") is not True
        )
        if write_spend_logs and local_rows:
            groups: Final = tuple(
                tuple(group)
                for _, group in groupby(
                    sorted(local_rows, key=lambda row: tuple(sorted(row))), key=lambda row: tuple(sorted(row))
                )
            )
            async with db_span("insert_spend_logs", "HangarLLM_SpendLogs"):
                for group in groups:
                    await transaction.query_raw(*spend_log_insert_statement(group))
        return len(accepted)

    @staticmethod
    async def _jobs_charged_by_legacy(transaction: LedgerTransaction, cost_row_ids: Sequence[str]) -> frozenset[str]:
        """Batches and videos a pre-ledger poll already charged through their SpendLogs cost row."""
        if not cost_row_ids:
            return frozenset()
        rows: Final = await transaction.query_raw(
            'SELECT DISTINCT request_id FROM "HangarLLM_SpendLogs" WHERE request_id = ANY($1::text[]) '
            "AND status = 'success' AND spend > 0",
            list(cost_row_ids),
        )
        return frozenset(str(row["request_id"]) for row in rows)

    async def has_delivery(self, delivery_id: str) -> bool:
        database: Final[LedgerTransaction] = self.prisma_client.writer_db
        rows: Final = await database.query_raw(
            'SELECT 1 FROM "HangarLLM_SpendLogDelivery" WHERE delivery_id = $1', delivery_id
        )
        return bool(rows)


class BudgetWindowSpendRepository(PrismaTableRepository["prisma_models.HangarLLM_BudgetWindowSpend"]):
    table_name = "hangarllm_budgetwindowspend"


class ClaudeCodePluginRepository(PrismaTableRepository["prisma_models.HangarLLM_ClaudeCodePluginTable"]):
    table_name = "hangarllm_claudecodeplugintable"


class TeamMembershipRepository(PrismaTableRepository["prisma_models.HangarLLM_TeamMembership"]):
    table_name = "hangarllm_teammembership"


class EndUserRepository(PrismaTableRepository["prisma_models.HangarLLM_EndUserTable"]):
    table_name = "hangarllm_endusertable"


class ManagedVectorStoresRepository(PrismaTableRepository["prisma_models.HangarLLM_ManagedVectorStoresTable"]):
    table_name = "hangarllm_managedvectorstorestable"


class MCPUserCredentialsRepository(PrismaTableRepository["prisma_models.HangarLLM_MCPUserCredentials"]):
    table_name = "hangarllm_mcpusercredentials"


class MCPServerOAuthClientRepository(PrismaTableRepository["prisma_models.HangarLLM_MCPServerOAuthClient"]):
    table_name = "hangarllm_mcpserveroauthclient"


class PromptRepository(PrismaTableRepository["prisma_models.HangarLLM_PromptTable"]):
    table_name = "hangarllm_prompttable"


class TagRepository(PrismaTableRepository["prisma_models.HangarLLM_TagTable"]):
    table_name = "hangarllm_tagtable"


class ModelAccessGroupBudgetRepository(PrismaTableRepository["prisma_models.HangarLLM_ModelAccessGroupBudgetTable"]):
    table_name = "hangarllm_modelaccessgroupbudgettable"


class InvitationLinkRepository(PrismaTableRepository["prisma_models.HangarLLM_InvitationLink"]):
    table_name = "hangarllm_invitationlink"


class JWTKeyMappingRepository(PrismaTableRepository["prisma_models.HangarLLM_JWTKeyMapping"]):
    table_name = "hangarllm_jwtkeymapping"


class MemoryRepository(PrismaTableRepository["prisma_models.HangarLLM_MemoryTable"]):
    table_name = "hangarllm_memorytable"


class SearchToolsRepository(PrismaTableRepository["prisma_models.HangarLLM_SearchToolsTable"]):
    table_name = "hangarllm_searchtoolstable"


class ConfigOverridesRepository(PrismaTableRepository["prisma_models.HangarLLM_ConfigOverrides"]):
    table_name = "hangarllm_configoverrides"


class MCPToolsetRepository(PrismaTableRepository["prisma_models.HangarLLM_MCPToolsetTable"]):
    table_name = "hangarllm_mcptoolsettable"


class ToolRepository(PrismaTableRepository["prisma_models.HangarLLM_ToolTable"]):
    table_name = "hangarllm_tooltable"


class DeletedVerificationTokenRepository(PrismaTableRepository["prisma_models.HangarLLM_DeletedVerificationToken"]):
    table_name = "hangarllm_deletedverificationtoken"


class WorkflowRunRepository(PrismaTableRepository["prisma_models.HangarLLM_WorkflowRun"]):
    table_name = "hangarllm_workflowrun"


class ModelTableRepository(PrismaTableRepository["prisma_models.HangarLLM_ModelTable"]):
    table_name = "hangarllm_modeltable"


class AccessGroupRepository(PrismaTableRepository["prisma_models.HangarLLM_AccessGroupTable"]):
    table_name = "hangarllm_accessgrouptable"


class SSOConfigRepository(PrismaTableRepository["prisma_models.HangarLLM_SSOConfig"]):
    table_name = "hangarllm_ssoconfig"


class UISettingsRepository(PrismaTableRepository["prisma_models.HangarLLM_UISettings"]):
    table_name = "hangarllm_uisettings"


class DailyGuardrailMetricsRepository(PrismaTableRepository["prisma_models.HangarLLM_DailyGuardrailMetrics"]):
    table_name = "hangarllm_dailyguardrailmetrics"


class DailyGuardrailUsageUnitsRepository(PrismaTableRepository["prisma_models.HangarLLM_DailyGuardrailUsageUnits"]):
    table_name = "hangarllm_dailyguardrailusageunits"


class PolicyAttachmentRepository(PrismaTableRepository["prisma_models.HangarLLM_PolicyAttachmentTable"]):
    table_name = "hangarllm_policyattachmenttable"


class TeamRepository(PrismaTableRepository["prisma_models.HangarLLM_TeamTable"]):
    table_name = "hangarllm_teamtable"


class DeletedTeamRepository(PrismaTableRepository["prisma_models.HangarLLM_DeletedTeamTable"]):
    table_name = "hangarllm_deletedteamtable"


class SkillsRepository(PrismaTableRepository["prisma_models.HangarLLM_SkillsTable"]):
    table_name = "hangarllm_skillstable"


class CacheConfigRepository(PrismaTableRepository["prisma_models.HangarLLM_CacheConfig"]):
    table_name = "hangarllm_cacheconfig"


class ManagedVectorStoreIndexRepository(PrismaTableRepository["prisma_models.HangarLLM_ManagedVectorStoreIndexTable"]):
    table_name = "hangarllm_managedvectorstoreindextable"


class WorkflowMessageRepository(PrismaTableRepository["prisma_models.HangarLLM_WorkflowMessage"]):
    table_name = "hangarllm_workflowmessage"


class DailyTagSpendRepository(PrismaTableRepository["prisma_models.HangarLLM_DailyTagSpend"]):
    table_name = "hangarllm_dailytagspend"


class SpendLogToolIndexRepository(PrismaTableRepository["prisma_models.HangarLLM_SpendLogToolIndex"]):
    table_name = "hangarllm_spendlogtoolindex"


class DailyToolSpendRepository(PrismaTableRepository["prisma_models.HangarLLM_DailyToolSpend"]):
    table_name = "hangarllm_dailytoolspend"


class DailyModelUsageRepository(PrismaTableRepository["prisma_models.HangarLLM_DailyModelUsage"]):
    table_name = "hangarllm_dailymodelusage"


class SpendLogGuardrailIndexRepository(PrismaTableRepository["prisma_models.HangarLLM_SpendLogGuardrailIndex"]):
    table_name = "hangarllm_spendlogguardrailindex"


class UserNotificationsRepository(PrismaTableRepository["prisma_models.HangarLLM_UserNotifications"]):
    table_name = "hangarllm_usernotifications"


class HealthCheckRepository(PrismaTableRepository["prisma_models.HangarLLM_HealthCheckTable"]):
    table_name = "hangarllm_healthchecktable"


class DeprecatedVerificationTokenRepository(PrismaTableRepository["prisma_models.HangarLLM_DeprecatedVerificationToken"]):
    table_name = "hangarllm_deprecatedverificationtoken"


class WorkflowEventRepository(PrismaTableRepository["prisma_models.HangarLLM_WorkflowEvent"]):
    table_name = "hangarllm_workflowevent"


class DailyPolicyMetricsRepository(PrismaTableRepository["prisma_models.HangarLLM_DailyPolicyMetrics"]):
    table_name = "hangarllm_dailypolicymetrics"


class AdaptiveRouterStateRepository(PrismaTableRepository["prisma_models.HangarLLM_AdaptiveRouterState"]):
    table_name = "hangarllm_adaptiverouterstate"


class AuditLogRepository(PrismaTableRepository["prisma_models.HangarLLM_AuditLog"]):
    table_name = "hangarllm_auditlog"


class AdaptiveRouterSessionRepository(PrismaTableRepository["prisma_models.HangarLLM_AdaptiveRouterSession"]):
    table_name = "hangarllm_adaptiveroutersession"


class BackgroundInteractionSettlementRepository(
    PrismaTableRepository["prisma_models.HangarLLM_BackgroundInteractionSettlement"]
):
    table_name = "hangarllm_backgroundinteractionsettlement"


class RetiredAgentRepository(PrismaTableRepository["prisma_models.HangarLLM_RetiredAgent"]):
    table_name = "hangarllm_retiredagent"


class DailyUserSpendRepository(PrismaTableRepository["prisma_models.HangarLLM_DailyUserSpend"]):
    table_name = "hangarllm_dailyuserspend"
