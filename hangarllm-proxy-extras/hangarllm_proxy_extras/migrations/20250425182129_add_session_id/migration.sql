-- AlterTable
ALTER TABLE "HangarLLM_SpendLogs" ADD COLUMN IF NOT EXISTS "proxy_server_request" JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS "session_id" TEXT;

