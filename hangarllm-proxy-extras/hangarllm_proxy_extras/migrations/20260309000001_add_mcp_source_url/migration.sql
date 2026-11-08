-- AlterTable: Add source_url field to HangarLLM_MCPServerTable for GitHub/docs link
ALTER TABLE "HangarLLM_MCPServerTable"
  ADD COLUMN IF NOT EXISTS "source_url" TEXT;
