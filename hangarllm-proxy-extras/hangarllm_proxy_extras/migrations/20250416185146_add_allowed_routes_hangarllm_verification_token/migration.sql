-- AlterTable
ALTER TABLE "HangarLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "allowed_routes" TEXT[] DEFAULT ARRAY[]::TEXT[];

