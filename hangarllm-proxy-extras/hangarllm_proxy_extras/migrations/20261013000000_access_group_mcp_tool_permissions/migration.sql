SET LOCAL lock_timeout = '10s';

-- AlterTable
ALTER TABLE "HangarLLM_AccessGroupTable" ADD COLUMN IF NOT EXISTS "mcp_tool_permissions" JSONB;
