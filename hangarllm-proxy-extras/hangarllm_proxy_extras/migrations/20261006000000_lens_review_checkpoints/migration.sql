CREATE TABLE IF NOT EXISTS "HangarLLM_LensReview" (
    "lens_id" TEXT NOT NULL REFERENCES "HangarLLM_Lens"("id") ON DELETE CASCADE,
    "criteria_key" TEXT NOT NULL,
    "execution_id" TEXT NOT NULL,
    "data" JSONB NOT NULL,
    PRIMARY KEY ("lens_id", "criteria_key", "execution_id")
);
