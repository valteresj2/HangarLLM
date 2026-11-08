SET LOCAL lock_timeout = '10s';

ALTER TABLE "HangarLLM_SkillSubmission" ADD COLUMN IF NOT EXISTS "scan_json" TEXT;
