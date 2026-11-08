CREATE INDEX CONCURRENTLY IF NOT EXISTS "HangarLLM_Lens_jobs_idx"
ON "HangarLLM_Lens" USING GIN ((data->'jobs') jsonb_path_ops);
