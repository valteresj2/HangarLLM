-- AlterTable
ALTER TABLE "HangarLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "budget_fallbacks" JSONB NOT NULL DEFAULT '{}';

-- AlterTable
ALTER TABLE "HangarLLM_DeletedVerificationToken" ADD COLUMN IF NOT EXISTS "budget_fallbacks" JSONB NOT NULL DEFAULT '{}';
