CREATE INDEX IF NOT EXISTS "HangarLLM_LensWorker_active_scope_idx"
ON "HangarLLM_LensWorker" USING GIN ((data->'scope') jsonb_path_ops)
WHERE data @> '{"revoked": false}'::jsonb;
