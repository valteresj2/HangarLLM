-- AlterTable
ALTER TABLE "HangarLLM_DailyUserSpend" ADD COLUMN IF NOT EXISTS "cache_creation_input_tokens" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cache_read_input_tokens" INTEGER NOT NULL DEFAULT 0;

