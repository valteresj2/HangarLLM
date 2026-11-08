SET LOCAL lock_timeout = '10s';
CREATE TABLE IF NOT EXISTS "HangarLLM_ClaudeCodePluginVersion" (
    "id" TEXT NOT NULL,
    "plugin_id" TEXT NOT NULL,
    "version" TEXT,
    "description" TEXT,
    "manifest_json" TEXT,
    "published_at" TIMESTAMP(3),
    "published_by" TEXT,
    "archive_available" BOOLEAN NOT NULL DEFAULT false,
    "content" BYTEA,
    CONSTRAINT "HangarLLM_ClaudeCodePluginVersion_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "HangarLLM_ClaudeCodePluginVersion_plugin_id_fkey" FOREIGN KEY ("plugin_id") REFERENCES "HangarLLM_ClaudeCodePluginTable"("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_ClaudeCodePluginVersion_plugin_id_version_key" ON "HangarLLM_ClaudeCodePluginVersion"("plugin_id", "version");
CREATE INDEX IF NOT EXISTS "HangarLLM_ClaudeCodePluginVersion_plugin_id_published_at_idx" ON "HangarLLM_ClaudeCodePluginVersion"("plugin_id", "published_at");
