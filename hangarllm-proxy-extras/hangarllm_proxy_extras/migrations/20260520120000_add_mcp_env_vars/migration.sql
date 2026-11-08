-- AlterTable: add admin-configured env_vars to MCP server table
ALTER TABLE "HangarLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "env_vars" JSONB DEFAULT '[]';

-- CreateTable: per-user env var values for MCP servers
CREATE TABLE IF NOT EXISTS "HangarLLM_MCPUserEnvVars" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "server_id" TEXT NOT NULL,
    "values_b64" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "HangarLLM_MCPUserEnvVars_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_MCPUserEnvVars_user_id_server_id_key" ON "HangarLLM_MCPUserEnvVars"("user_id", "server_id");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_MCPUserEnvVars_user_id_idx" ON "HangarLLM_MCPUserEnvVars"("user_id");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_MCPUserEnvVars_server_id_idx" ON "HangarLLM_MCPUserEnvVars"("server_id");
