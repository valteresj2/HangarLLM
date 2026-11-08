-- AlterTable
ALTER TABLE "HangarLLM_DailyUserSpend" ADD COLUMN IF NOT EXISTS "autorouter_savings_spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0;

-- AlterTable
ALTER TABLE "HangarLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "autorouter_savings_spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0;

-- AlterTable
ALTER TABLE "HangarLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "autorouter_savings_spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0;

-- AlterTable
ALTER TABLE "HangarLLM_DailyAgentSpend" ADD COLUMN IF NOT EXISTS "autorouter_savings_spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0;

-- AlterTable
ALTER TABLE "HangarLLM_DailyTeamSpend" ADD COLUMN IF NOT EXISTS "autorouter_savings_spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0;

-- AlterTable
ALTER TABLE "HangarLLM_DailyTagSpend" ADD COLUMN IF NOT EXISTS "autorouter_savings_spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0;
