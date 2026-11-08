-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyTagSpend_tag_date_api_key_model_custom_llm_pro_key";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyTeamSpend_team_id_date_api_key_model_custom_ll_key";

-- DropIndex
DROP INDEX IF EXISTS "HangarLLM_DailyUserSpend_user_id_date_api_key_model_custom_ll_key";

-- AlterTable
ALTER TABLE "HangarLLM_DailyTagSpend" ADD COLUMN IF NOT EXISTS "mcp_namespaced_tool_name" TEXT,
ALTER COLUMN "model" DROP NOT NULL;

-- AlterTable
ALTER TABLE "HangarLLM_DailyTeamSpend" ADD COLUMN IF NOT EXISTS "mcp_namespaced_tool_name" TEXT,
ALTER COLUMN "model" DROP NOT NULL;

-- AlterTable
ALTER TABLE "HangarLLM_DailyUserSpend" ADD COLUMN IF NOT EXISTS "mcp_namespaced_tool_name" TEXT,
ALTER COLUMN "model" DROP NOT NULL;

-- AlterTable
ALTER TABLE "HangarLLM_SpendLogs" ADD COLUMN IF NOT EXISTS "mcp_namespaced_tool_name" TEXT;

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_mcp_namespaced_tool_name_idx" ON "HangarLLM_DailyTagSpend"("mcp_namespaced_tool_name");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyTagSpend_tag_date_api_key_model_custom_llm_pro_key" ON "HangarLLM_DailyTagSpend"("tag", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyTeamSpend_mcp_namespaced_tool_name_idx" ON "HangarLLM_DailyTeamSpend"("mcp_namespaced_tool_name");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyTeamSpend_team_id_date_api_key_model_custom_ll_key" ON "HangarLLM_DailyTeamSpend"("team_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DailyUserSpend_mcp_namespaced_tool_name_idx" ON "HangarLLM_DailyUserSpend"("mcp_namespaced_tool_name");

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DailyUserSpend_user_id_date_api_key_model_custom_ll_key" ON "HangarLLM_DailyUserSpend"("user_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name");

