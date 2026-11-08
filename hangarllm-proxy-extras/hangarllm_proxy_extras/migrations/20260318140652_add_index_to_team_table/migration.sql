-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_TeamTable_organization_id_idx" ON "HangarLLM_TeamTable"("organization_id");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_TeamTable_team_alias_idx" ON "HangarLLM_TeamTable"("team_alias");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_TeamTable_created_at_idx" ON "HangarLLM_TeamTable"("created_at");

