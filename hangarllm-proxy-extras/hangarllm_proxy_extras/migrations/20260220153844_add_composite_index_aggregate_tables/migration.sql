-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyAgentSpend_agent_id_idx";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyEndUserSpend_end_user_id_idx";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyOrganizationSpend_organization_id_idx";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyTagSpend_tag_idx";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyTeamSpend_team_id_idx";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyUserSpend_user_id_idx";

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyAgentSpend_agent_id_date_idx" ON "HangarLLM_DailyAgentSpend"("agent_id", "date");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyEndUserSpend_end_user_id_date_idx" ON "HangarLLM_DailyEndUserSpend"("end_user_id", "date");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyOrganizationSpend_organization_id_date_idx" ON "HangarLLM_DailyOrganizationSpend"("organization_id", "date");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_tag_date_idx" ON "HangarLLM_DailyTagSpend"("tag", "date");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyTeamSpend_team_id_date_idx" ON "HangarLLM_DailyTeamSpend"("team_id", "date");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyUserSpend_user_id_date_idx" ON "HangarLLM_DailyUserSpend"("user_id", "date");

