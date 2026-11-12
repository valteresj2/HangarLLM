SET LOCAL lock_timeout = '10s';

ALTER TABLE "HangarLLM_HealthCheckTable" ADD COLUMN IF NOT EXISTS "credential_name" TEXT;
