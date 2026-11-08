-- AlterTable
ALTER TABLE "HangarLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "extra_headers" TEXT[] DEFAULT ARRAY[]::TEXT[];

