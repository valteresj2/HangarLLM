DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'HangarLLM_ShadowEvalJob' AND column_name = 'api_key_id'
    ) THEN
        ALTER TABLE "HangarLLM_ShadowEvalJob" RENAME COLUMN "api_key_id" TO "target_id";
    END IF;
END $$;

ALTER TABLE "HangarLLM_ShadowEvalJob" ADD COLUMN IF NOT EXISTS "target_type" TEXT NOT NULL DEFAULT 'key';

DROP INDEX IF EXISTS "HangarLLM_ShadowEvalJob_one_active_per_key_direction";

CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_ShadowEvalJob_one_active_per_target_direction"
    ON "HangarLLM_ShadowEvalJob"("target_type", "target_id", "direction") WHERE "stopped_at" IS NULL;

DROP INDEX IF EXISTS "HangarLLM_ShadowEvalJob_api_key_id_idx";

CREATE INDEX IF NOT EXISTS "HangarLLM_ShadowEvalJob_target_type_target_id_idx"
    ON "HangarLLM_ShadowEvalJob"("target_type", "target_id");
