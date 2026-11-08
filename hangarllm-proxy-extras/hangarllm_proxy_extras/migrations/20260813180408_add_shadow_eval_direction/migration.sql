-- AlterTable
ALTER TABLE "HangarLLM_ShadowEvalJob" ADD COLUMN     "baseline_model" TEXT,
ADD COLUMN     "direction" TEXT NOT NULL DEFAULT 'forward';

DROP INDEX IF EXISTS "HangarLLM_ShadowEvalJob_one_active_per_key";

CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_ShadowEvalJob_one_active_per_key_direction"
    ON "HangarLLM_ShadowEvalJob"("api_key_id", "direction") WHERE "stopped_at" IS NULL;
