CREATE TABLE IF NOT EXISTS "HangarLLM_LensDataset" (
    "id" TEXT NOT NULL,
    "revision" INTEGER NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL,
    "data" JSONB NOT NULL,
    CONSTRAINT "HangarLLM_LensDataset_pkey" PRIMARY KEY ("id", "revision")
);
