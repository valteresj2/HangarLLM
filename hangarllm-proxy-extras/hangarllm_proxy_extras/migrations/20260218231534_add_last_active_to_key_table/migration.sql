-- AlterTable
ALTER TABLE "HangarLLM_DeletedVerificationToken" ADD COLUMN IF NOT EXISTS "last_active" TIMESTAMP(3);

-- AlterTable
ALTER TABLE "HangarLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "last_active" TIMESTAMP(3);

