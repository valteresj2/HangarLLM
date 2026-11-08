-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyAgentSpend_agent_id_date_api_key_model_custom__key";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyEndUserSpend_end_user_id_date_api_key_model_cu_key";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyOrganizationSpend_organization_id_date_api_key_key";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyTagSpend_tag_date_api_key_model_custom_llm_pro_key";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyTeamSpend_team_id_date_api_key_model_custom_ll_key";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyUserSpend_user_id_date_api_key_model_custom_ll_key";

-- AlterTable
ALTER TABLE "HangarLLM_DailyAgentSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;

-- AlterTable
ALTER TABLE "HangarLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;

-- AlterTable
ALTER TABLE "HangarLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;

-- AlterTable
ALTER TABLE "HangarLLM_DailyTagSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;

-- AlterTable
ALTER TABLE "HangarLLM_DailyTeamSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;

-- AlterTable
ALTER TABLE "HangarLLM_DailyUserSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyAgentSpend_endpoint_idx" ON "HangarLLM_DailyAgentSpend"("endpoint");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyAgentSpend_agent_id_date_api_key_model_custom__key" ON "HangarLLM_DailyAgentSpend"("agent_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyEndUserSpend_endpoint_idx" ON "HangarLLM_DailyEndUserSpend"("endpoint");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyEndUserSpend_end_user_id_date_api_key_model_cu_key" ON "HangarLLM_DailyEndUserSpend"("end_user_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyOrganizationSpend_endpoint_idx" ON "HangarLLM_DailyOrganizationSpend"("endpoint");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyOrganizationSpend_organization_id_date_api_key_key" ON "HangarLLM_DailyOrganizationSpend"("organization_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_endpoint_idx" ON "HangarLLM_DailyTagSpend"("endpoint");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_tag_date_api_key_model_custom_llm_pro_key" ON "HangarLLM_DailyTagSpend"("tag", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyTeamSpend_endpoint_idx" ON "HangarLLM_DailyTeamSpend"("endpoint");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyTeamSpend_team_id_date_api_key_model_custom_ll_key" ON "HangarLLM_DailyTeamSpend"("team_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyUserSpend_endpoint_idx" ON "HangarLLM_DailyUserSpend"("endpoint");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyUserSpend_user_id_date_api_key_model_custom_ll_key" ON "HangarLLM_DailyUserSpend"("user_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");

