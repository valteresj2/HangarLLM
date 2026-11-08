-- AlterTable
ALTER TABLE "HangarLLM_GuardrailsTable" ADD COLUMN IF NOT EXISTS "reviewed_at" TIMESTAMP(3),
ADD COLUMN IF NOT EXISTS "status" TEXT NOT NULL DEFAULT 'active',
ADD COLUMN IF NOT EXISTS "submitted_at" TIMESTAMP(3);

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_GuardrailsTable_status_idx" ON "HangarLLM_GuardrailsTable"("status");

