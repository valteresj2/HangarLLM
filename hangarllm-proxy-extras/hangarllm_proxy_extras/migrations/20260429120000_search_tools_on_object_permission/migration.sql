-- Search tool allowlists live on HangarLLM_ObjectPermissionTable (with agents, MCP, vector stores).
ALTER TABLE "HangarLLM_ObjectPermissionTable" ADD COLUMN IF NOT EXISTS "search_tools" TEXT[] DEFAULT ARRAY[]::TEXT[];
