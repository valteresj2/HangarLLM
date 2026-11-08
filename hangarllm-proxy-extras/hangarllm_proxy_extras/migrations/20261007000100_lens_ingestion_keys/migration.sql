CREATE TABLE IF NOT EXISTS "HangarLLM_LensIngestionKey" (
    "id" TEXT NOT NULL,
    "data" JSONB NOT NULL,
    CONSTRAINT "HangarLLM_LensIngestionKey_pkey" PRIMARY KEY ("id")
);
