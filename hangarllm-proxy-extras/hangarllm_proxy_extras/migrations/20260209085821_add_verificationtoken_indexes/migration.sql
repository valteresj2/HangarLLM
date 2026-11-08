-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_VerificationToken_user_id_team_id_idx" ON "HangarLLM_VerificationToken"("user_id", "team_id");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_VerificationToken_team_id_idx" ON "HangarLLM_VerificationToken"("team_id");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_VerificationToken_budget_reset_at_expires_idx" ON "HangarLLM_VerificationToken"("budget_reset_at", "expires");
