-- AlterTable
ALTER TABLE "HangarLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "settings_updated_at" TIMESTAMP(3);

-- AlterTable
ALTER TABLE "HangarLLM_DeletedVerificationToken" ADD COLUMN IF NOT EXISTS "settings_updated_at" TIMESTAMP(3);
