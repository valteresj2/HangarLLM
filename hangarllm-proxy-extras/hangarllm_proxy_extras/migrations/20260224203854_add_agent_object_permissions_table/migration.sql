-- AlterTable
ALTER TABLE "HangarLLM_AgentsTable" ADD COLUMN IF NOT EXISTS "object_permission_id" TEXT;

-- AlterTable
ALTER TABLE "HangarLLM_MCPServerTable" DROP COLUMN IF EXISTS "spec_path";

-- AlterTable
ALTER TABLE "HangarLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "agent_id" TEXT;

-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_ToolTable" (
    "tool_id" TEXT NOT NULL,
    "tool_name" TEXT NOT NULL,
    "origin" TEXT,
    "call_policy" TEXT NOT NULL DEFAULT 'untrusted',
    "call_count" INTEGER NOT NULL DEFAULT 0,
    "assignments" JSONB DEFAULT '{}',
    "key_hash" TEXT,
    "team_id" TEXT,
    "key_alias" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_by" TEXT,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_by" TEXT,

    CONSTRAINT "HangarLLM_ToolTable_pkey" PRIMARY KEY ("tool_id")
);

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_ToolTable_tool_name_key" ON "HangarLLM_ToolTable"("tool_name");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_ToolTable_call_policy_idx" ON "HangarLLM_ToolTable"("call_policy");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_ToolTable_team_id_idx" ON "HangarLLM_ToolTable"("team_id");

-- AddForeignKey
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_AgentsTable_object_permission_id_fkey') THEN
        ALTER TABLE "HangarLLM_AgentsTable" ADD CONSTRAINT "HangarLLM_AgentsTable_object_permission_id_fkey" FOREIGN KEY ("object_permission_id") REFERENCES "HangarLLM_ObjectPermissionTable"("object_permission_id") ON DELETE SET NULL ON UPDATE CASCADE;
    END IF;
END $$;

