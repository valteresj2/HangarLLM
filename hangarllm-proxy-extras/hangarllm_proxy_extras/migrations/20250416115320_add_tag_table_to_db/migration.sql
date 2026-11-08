-- AlterTable
ALTER TABLE "HangarLLM_DailyTeamSpend" ADD COLUMN IF NOT EXISTS "cache_creation_input_tokens" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cache_read_input_tokens" INTEGER NOT NULL DEFAULT 0;

-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_DailyTagSpend" (
    "id" TEXT NOT NULL,
    "tag" TEXT NOT NULL,
    "date" TEXT NOT NULL,
    "api_key" TEXT NOT NULL,
    "model" TEXT NOT NULL,
    "model_group" TEXT,
    "custom_llm_provider" TEXT,
    "prompt_tokens" INTEGER NOT NULL DEFAULT 0,
    "completion_tokens" INTEGER NOT NULL DEFAULT 0,
    "cache_read_input_tokens" INTEGER NOT NULL DEFAULT 0,
    "cache_creation_input_tokens" INTEGER NOT NULL DEFAULT 0,
    "spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "api_requests" INTEGER NOT NULL DEFAULT 0,
    "successful_requests" INTEGER NOT NULL DEFAULT 0,
    "failed_requests" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "HangarLLM_DailyTagSpend_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_tag_key" ON "HangarLLM_DailyTagSpend"("tag");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_date_idx" ON "HangarLLM_DailyTagSpend"("date");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_tag_idx" ON "HangarLLM_DailyTagSpend"("tag");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_api_key_idx" ON "HangarLLM_DailyTagSpend"("api_key");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_model_idx" ON "HangarLLM_DailyTagSpend"("model");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_tag_date_api_key_model_custom_llm_pro_key" ON "HangarLLM_DailyTagSpend"("tag", "date", "api_key", "model", "custom_llm_provider");

