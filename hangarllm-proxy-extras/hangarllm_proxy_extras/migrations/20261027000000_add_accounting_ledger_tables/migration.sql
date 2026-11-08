SET LOCAL lock_timeout = '10s';

CREATE TYPE "AccountingEventKind" AS ENUM ('inbound_usage', 'outbound_usage', 'cost');

CREATE TYPE "AccountingDeliveryState" AS ENUM ('pending', 'applied', 'parked');

CREATE TYPE "AccountingDeliveryTarget" AS ENUM ('HangarLLM_VerificationToken', 'HangarLLM_UserTable', 'HangarLLM_TeamTable', 'HangarLLM_TeamMembership', 'HangarLLM_OrganizationTable', 'HangarLLM_OrganizationMembership', 'HangarLLM_EndUserTable', 'HangarLLM_AgentsTable', 'HangarLLM_TagTable', 'HangarLLM_ProjectTable', 'HangarLLM_ModelAccessGroupBudgetTable', 'HangarLLM_BudgetTable', 'HangarLLM_BudgetWindowSpend', 'HangarLLM_DailyUserSpend', 'HangarLLM_DailyTeamSpend', 'HangarLLM_DailyOrganizationSpend', 'HangarLLM_DailyEndUserSpend', 'HangarLLM_DailyAgentSpend', 'HangarLLM_DailyTagSpend', 'HangarLLM_DailyModelUsage', 'HangarLLM_DailyToolSpend', 'HangarLLM_AutoRouterDailySpend');

-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_AccountingEvent" (
    "event_id" TEXT NOT NULL,
    "kind" "AccountingEventKind" NOT NULL,
    "source_event_id" TEXT,
    "schema_version" INTEGER NOT NULL,
    "payload_hash" TEXT NOT NULL,
    "occurred_at" TIMESTAMP(3) NOT NULL,
    "recorded_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "payload" JSONB NOT NULL,

    CONSTRAINT "HangarLLM_AccountingEvent_schema_version_check" CHECK ("schema_version" > 0),
    CONSTRAINT "HangarLLM_AccountingEvent_pkey" PRIMARY KEY ("event_id")
);

-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_AccountingDelivery" (
    "event_id" TEXT NOT NULL,
    "target" "AccountingDeliveryTarget" NOT NULL,
    "version" INTEGER NOT NULL,
    "state" "AccountingDeliveryState" NOT NULL DEFAULT 'pending',
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "next_attempt_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "applied_at" TIMESTAMP(3),
    "last_error" TEXT,

    CONSTRAINT "HangarLLM_AccountingDelivery_version_check" CHECK ("version" > 0),
    CONSTRAINT "HangarLLM_AccountingDelivery_attempts_check" CHECK ("attempts" >= 0),
    CONSTRAINT "HangarLLM_AccountingDelivery_pkey" PRIMARY KEY ("event_id","target","version")
);

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_AccountingEvent_recorded_at_idx" ON "HangarLLM_AccountingEvent"("recorded_at");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_AccountingEvent_kind_source_event_id_idx" ON "HangarLLM_AccountingEvent"("kind", "source_event_id");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_AccountingDelivery_target_state_next_attempt_at_idx" ON "HangarLLM_AccountingDelivery"("target", "state", "next_attempt_at");
