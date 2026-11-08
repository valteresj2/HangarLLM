-- AlterTable
ALTER TABLE "HangarLLM_DeletedTeamTable" ADD COLUMN IF NOT EXISTS "router_settings" JSONB DEFAULT '{}';

-- AlterTable
ALTER TABLE "HangarLLM_DeletedVerificationToken" ADD COLUMN IF NOT EXISTS "router_settings" JSONB DEFAULT '{}';

