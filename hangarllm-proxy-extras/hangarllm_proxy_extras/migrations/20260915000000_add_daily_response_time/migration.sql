-- AlterTable
ALTER TABLE "HangarLLM_DailyUserSpend" ADD COLUMN IF NOT EXISTS "total_response_time_ms" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "HangarLLM_DailyUserSpend" ADD COLUMN IF NOT EXISTS "timed_requests" BIGINT NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "HangarLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "total_response_time_ms" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "HangarLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "timed_requests" BIGINT NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "HangarLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "total_response_time_ms" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "HangarLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "timed_requests" BIGINT NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "HangarLLM_DailyAgentSpend" ADD COLUMN IF NOT EXISTS "total_response_time_ms" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "HangarLLM_DailyAgentSpend" ADD COLUMN IF NOT EXISTS "timed_requests" BIGINT NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "HangarLLM_DailyTeamSpend" ADD COLUMN IF NOT EXISTS "total_response_time_ms" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "HangarLLM_DailyTeamSpend" ADD COLUMN IF NOT EXISTS "timed_requests" BIGINT NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "HangarLLM_DailyTagSpend" ADD COLUMN IF NOT EXISTS "total_response_time_ms" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "HangarLLM_DailyTagSpend" ADD COLUMN IF NOT EXISTS "timed_requests" BIGINT NOT NULL DEFAULT 0;
