-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_PromptTable_prompt_id_key";

-- AlterTable
ALTER TABLE "HangarLLM_PromptTable"
ADD COLUMN IF NOT EXISTS "version" INTEGER NOT NULL DEFAULT 1;

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_PromptTable_prompt_id_idx" ON "HangarLLM_PromptTable" ("prompt_id");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_PromptTable_prompt_id_version_key" ON "HangarLLM_PromptTable" ("prompt_id", "version");