-- AlterTable
ALTER TABLE "HangarLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "static_headers" JSONB DEFAULT '{}';
