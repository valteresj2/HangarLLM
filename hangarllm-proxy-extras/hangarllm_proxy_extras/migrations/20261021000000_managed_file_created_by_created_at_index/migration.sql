CREATE INDEX CONCURRENTLY IF NOT EXISTS "HangarLLM_ManagedFileTable_created_by_created_at_idx"
ON "HangarLLM_ManagedFileTable" ("created_by", "created_at" DESC);
