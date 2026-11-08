-- AlterTable
ALTER TABLE "HangarLLM_AgentsTable" ADD COLUMN IF NOT EXISTS "kill_switch" JSONB;
