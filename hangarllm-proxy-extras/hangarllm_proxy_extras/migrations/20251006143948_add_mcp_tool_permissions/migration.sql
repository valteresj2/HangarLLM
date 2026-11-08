-- AlterTable
ALTER TABLE "HangarLLM_ObjectPermissionTable" ADD COLUMN IF NOT EXISTS "mcp_tool_permissions" JSONB;

