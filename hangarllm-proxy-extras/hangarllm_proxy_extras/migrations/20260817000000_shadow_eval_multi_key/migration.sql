ALTER TABLE "HangarLLM_ShadowEvalJob" ADD COLUMN IF NOT EXISTS "group_id" TEXT;

UPDATE "HangarLLM_ShadowEvalJob" SET "group_id" = "id" WHERE "group_id" IS NULL;

ALTER TABLE "HangarLLM_ShadowEvalJob" ALTER COLUMN "group_id" SET NOT NULL;

CREATE INDEX IF NOT EXISTS "HangarLLM_ShadowEvalJob_group_id_idx" ON "HangarLLM_ShadowEvalJob"("group_id");
