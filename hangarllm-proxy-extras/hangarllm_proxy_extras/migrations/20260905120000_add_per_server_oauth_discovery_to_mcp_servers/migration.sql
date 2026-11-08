-- AlterTable
ALTER TABLE "HangarLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "per_server_oauth_discovery" BOOLEAN NOT NULL DEFAULT false;
