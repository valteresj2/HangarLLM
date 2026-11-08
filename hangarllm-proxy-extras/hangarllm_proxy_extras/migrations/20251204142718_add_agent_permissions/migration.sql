-- Add agent permission fields to HangarLLM_ObjectPermissionTable
ALTER TABLE "HangarLLM_ObjectPermissionTable" ADD COLUMN IF NOT EXISTS "agents" TEXT[] DEFAULT ARRAY[]::TEXT[];
ALTER TABLE "HangarLLM_ObjectPermissionTable" ADD COLUMN IF NOT EXISTS "agent_access_groups" TEXT[] DEFAULT ARRAY[]::TEXT[];

-- Add agent_access_groups field to HangarLLM_AgentsTable  
ALTER TABLE "HangarLLM_AgentsTable" ADD COLUMN IF NOT EXISTS "agent_access_groups" TEXT[] DEFAULT ARRAY[]::TEXT[];

