-- AlterTable
ALTER TABLE "HangarLLM_TeamTable" ADD COLUMN IF NOT EXISTS "team_member_permissions" TEXT[] DEFAULT ARRAY[]::TEXT[];

