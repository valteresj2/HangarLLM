CREATE TABLE IF NOT EXISTS "HangarLLM_EngineRun" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "engine_id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL,
    "data" JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS "HangarLLM_EngineRun_engine_id_created_at_idx" ON "HangarLLM_EngineRun"("engine_id", "created_at");
