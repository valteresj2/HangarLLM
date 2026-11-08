-- AlterTable
ALTER TABLE "HangarLLM_ShadowEvalJob" ADD COLUMN     "stopped_by" TEXT;

UPDATE "HangarLLM_ShadowEvalJob" SET stopped_by = 'unknown'
WHERE stopped_at IS NOT NULL AND ends_at > (NOW() AT TIME ZONE 'utc');
