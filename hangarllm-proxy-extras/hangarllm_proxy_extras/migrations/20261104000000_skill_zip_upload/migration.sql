SET LOCAL lock_timeout = '10s';

CREATE TABLE IF NOT EXISTS "HangarLLM_ClaudeCodePluginUpload" (
    "plugin_name" TEXT NOT NULL,
    "content" BYTEA NOT NULL,
    CONSTRAINT "HangarLLM_ClaudeCodePluginUpload_pkey" PRIMARY KEY ("plugin_name"),
    CONSTRAINT "HangarLLM_ClaudeCodePluginUpload_plugin_name_fkey" FOREIGN KEY ("plugin_name")
        REFERENCES "HangarLLM_ClaudeCodePluginTable"("name") ON DELETE CASCADE ON UPDATE CASCADE
);
