-- AlterTable: Add new fields to HangarLLM_ProjectTable
ALTER TABLE "HangarLLM_ProjectTable" ADD COLUMN IF NOT EXISTS "description" TEXT;
ALTER TABLE "HangarLLM_ProjectTable" ADD COLUMN IF NOT EXISTS "model_rpm_limit" JSONB NOT NULL DEFAULT '{}';
ALTER TABLE "HangarLLM_ProjectTable" ADD COLUMN IF NOT EXISTS "model_tpm_limit" JSONB NOT NULL DEFAULT '{}';

