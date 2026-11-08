-- AlterTable
ALTER TABLE "HangarLLM_ManagedVectorStoresTable"
    ADD COLUMN IF NOT EXISTS "team_id" TEXT,
    ADD COLUMN IF NOT EXISTS "user_id" TEXT;

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_ManagedVectorStoresTable_team_id_idx"
    ON "HangarLLM_ManagedVectorStoresTable"("team_id");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_ManagedVectorStoresTable_user_id_idx"
    ON "HangarLLM_ManagedVectorStoresTable"("user_id");

