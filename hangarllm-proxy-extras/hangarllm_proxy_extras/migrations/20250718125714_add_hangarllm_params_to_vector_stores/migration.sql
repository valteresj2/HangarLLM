-- AlterTable
ALTER TABLE "HangarLLM_ManagedVectorStoresTable" ADD COLUMN IF NOT EXISTS "hangarllm_params" JSONB;

