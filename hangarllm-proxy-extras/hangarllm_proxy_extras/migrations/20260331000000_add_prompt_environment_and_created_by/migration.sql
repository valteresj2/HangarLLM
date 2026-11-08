-- AlterTable
ALTER TABLE "HangarLLM_PromptTable" ADD COLUMN "environment" TEXT NOT NULL DEFAULT 'development';
ALTER TABLE "HangarLLM_PromptTable" ADD COLUMN "created_by" TEXT;

-- DropIndex (old unique constraint)
DROP INDEX IF EXISTS "HangarLLM_PromptTable_prompt_id_version_key";

-- CreateIndex (new unique constraint)
CREATE UNIQUE INDEX "HangarLLM_PromptTable_prompt_id_version_environment_key" ON "HangarLLM_PromptTable"("prompt_id", "version", "environment");

-- CreateIndex (new composite index)
CREATE INDEX "HangarLLM_PromptTable_prompt_id_environment_idx" ON "HangarLLM_PromptTable"("prompt_id", "environment");
