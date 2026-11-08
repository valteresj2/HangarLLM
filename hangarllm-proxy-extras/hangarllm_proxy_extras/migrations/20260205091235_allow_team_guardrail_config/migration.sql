-- AlterTable
ALTER TABLE "HangarLLM_DeletedTeamTable" ADD COLUMN IF NOT EXISTS "allow_team_guardrail_config" BOOLEAN NOT NULL DEFAULT false;

-- AlterTable
ALTER TABLE "HangarLLM_TeamTable" ADD COLUMN IF NOT EXISTS "allow_team_guardrail_config" BOOLEAN NOT NULL DEFAULT false;

