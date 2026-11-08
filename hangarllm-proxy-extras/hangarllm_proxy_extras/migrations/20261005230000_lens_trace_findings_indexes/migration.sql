CREATE INDEX CONCURRENTLY IF NOT EXISTS "HangarLLM_LensRun_completed_executions_idx"
ON "HangarLLM_LensRun" USING GIN ((data->'sample'->'executions') jsonb_path_ops)
WHERE data->>'status'='completed';
