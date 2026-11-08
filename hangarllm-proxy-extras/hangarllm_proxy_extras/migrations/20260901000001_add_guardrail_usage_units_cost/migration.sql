-- AlterTable
ALTER TABLE "HangarLLM_DailyGuardrailUsageUnits" ADD COLUMN IF NOT EXISTS "cost" DOUBLE PRECISION;
ALTER TABLE "HangarLLM_DailyGuardrailUsageUnits" ADD COLUMN IF NOT EXISTS "untracked_units" BIGINT NOT NULL DEFAULT 0;
