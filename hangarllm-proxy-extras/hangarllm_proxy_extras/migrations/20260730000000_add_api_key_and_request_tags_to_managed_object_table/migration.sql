-- Add api_key and request_tags columns to HangarLLM_ManagedObjectTable
-- Captured at batch-create time so CheckBatchCost can attribute batch-cost spend
-- back to the creating virtual key (and its tags) even when created_by is null.
ALTER TABLE "HangarLLM_ManagedObjectTable" ADD COLUMN IF NOT EXISTS "api_key" TEXT;
ALTER TABLE "HangarLLM_ManagedObjectTable" ADD COLUMN IF NOT EXISTS "request_tags" JSONB DEFAULT '[]';
