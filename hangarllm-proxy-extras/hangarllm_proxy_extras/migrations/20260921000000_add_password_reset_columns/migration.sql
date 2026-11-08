ALTER TABLE "HangarLLM_UserTable" ADD COLUMN IF NOT EXISTS "password_reset_required" BOOLEAN;

ALTER TABLE "HangarLLM_UserTable" ADD COLUMN IF NOT EXISTS "last_breach_check_at" TIMESTAMP(3);
