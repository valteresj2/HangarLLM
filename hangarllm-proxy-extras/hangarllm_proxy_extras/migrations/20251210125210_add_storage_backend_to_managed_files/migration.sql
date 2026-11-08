-- AlterTable
ALTER TABLE "HangarLLM_ManagedFileTable" ADD COLUMN IF NOT EXISTS "storage_backend" TEXT;
ALTER TABLE "HangarLLM_ManagedFileTable" ADD COLUMN IF NOT EXISTS "storage_url" TEXT;

