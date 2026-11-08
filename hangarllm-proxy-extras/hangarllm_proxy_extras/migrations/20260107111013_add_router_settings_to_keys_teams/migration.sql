-- AlterTable
ALTER TABLE "HangarLLM_TeamTable" ADD COLUMN IF NOT EXISTS "router_settings" JSONB DEFAULT '{}';

-- AlterTable
ALTER TABLE "HangarLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "router_settings" JSONB DEFAULT '{}';

