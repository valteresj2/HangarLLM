-- AlterTable
ALTER TABLE "HangarLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "allowed_tools" TEXT[] DEFAULT ARRAY[]::TEXT[];

