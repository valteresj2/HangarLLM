-- AlterTable
ALTER TABLE "HangarLLM_PolicyAttachmentTable" ADD COLUMN IF NOT EXISTS "tags" TEXT[] DEFAULT ARRAY[]::TEXT[];

