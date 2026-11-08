-- AlterTable
ALTER TABLE "HangarLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "oauth_passthrough" BOOLEAN NOT NULL DEFAULT false;
