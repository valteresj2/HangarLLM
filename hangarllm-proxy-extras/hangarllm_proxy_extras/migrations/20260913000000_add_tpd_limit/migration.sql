-- AlterTable
ALTER TABLE "HangarLLM_BudgetTable" ADD COLUMN IF NOT EXISTS "tpd_limit" BIGINT;

-- AlterTable
ALTER TABLE "HangarLLM_TeamTable" ADD COLUMN IF NOT EXISTS "tpd_limit" BIGINT;

-- AlterTable
ALTER TABLE "HangarLLM_DeletedTeamTable" ADD COLUMN IF NOT EXISTS "tpd_limit" BIGINT;

-- AlterTable
ALTER TABLE "HangarLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "tpd_limit" BIGINT;

-- AlterTable
ALTER TABLE "HangarLLM_DeletedVerificationToken" ADD COLUMN IF NOT EXISTS "tpd_limit" BIGINT;
