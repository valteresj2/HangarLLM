-- AlterTable
ALTER TABLE "HangarLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "credentials" JSONB DEFAULT '{}';
