-- AlterTable
ALTER TABLE "HangarLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "available_on_public_internet" BOOLEAN NOT NULL DEFAULT false;

