-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_PolicyTable_policy_name_key";

-- AlterTable
ALTER TABLE "HangarLLM_PolicyTable" ADD COLUMN IF NOT EXISTS "is_latest" BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN IF NOT EXISTS "parent_version_id" TEXT,
ADD COLUMN IF NOT EXISTS "production_at" TIMESTAMP(3),
ADD COLUMN IF NOT EXISTS "published_at" TIMESTAMP(3),
ADD COLUMN IF NOT EXISTS "version_number" INTEGER NOT NULL DEFAULT 1,
ADD COLUMN IF NOT EXISTS "version_status" TEXT NOT NULL DEFAULT 'production';

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_PolicyTable_policy_name_version_status_idx" ON "HangarLLM_PolicyTable"("policy_name", "version_status");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_PolicyTable_policy_name_version_number_key" ON "HangarLLM_PolicyTable"("policy_name", "version_number");

