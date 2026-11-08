-- Add org_id column to HangarLLM_ManagedObjectTable
-- Snapshots the creating key's organization at submission time, like team_id,
-- so CheckBatchCost can bill organization spend hours later without re-resolving
ALTER TABLE "HangarLLM_ManagedObjectTable" ADD COLUMN IF NOT EXISTS "org_id" TEXT;
