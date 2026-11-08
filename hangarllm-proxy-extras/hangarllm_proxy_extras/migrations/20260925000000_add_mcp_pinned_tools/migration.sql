-- AlterTable
ALTER TABLE "HangarLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "pinned_tools" JSONB DEFAULT '{}';
