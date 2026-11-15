SET LOCAL lock_timeout = '10s';

CREATE TABLE IF NOT EXISTS "HangarLLM_MCPServerControlTable" (
    "server_id" TEXT NOT NULL,
    "disabled" BOOLEAN NOT NULL DEFAULT false,
    "tool_overrides" JSONB NOT NULL DEFAULT '{}',
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_by" TEXT,

    CONSTRAINT "HangarLLM_MCPServerControlTable_pkey" PRIMARY KEY ("server_id")
);
