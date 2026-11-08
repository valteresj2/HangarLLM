-- AlterTable: add budget_limits column to HangarLLM_VerificationToken
ALTER TABLE "HangarLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "budget_limits" JSONB;

-- AlterTable: add budget_limits column to HangarLLM_TeamTable
ALTER TABLE "HangarLLM_TeamTable" ADD COLUMN IF NOT EXISTS "budget_limits" JSONB;
