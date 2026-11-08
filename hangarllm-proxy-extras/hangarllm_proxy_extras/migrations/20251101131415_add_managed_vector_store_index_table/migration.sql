-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_ManagedVectorStoreIndexTable" (
    "id" TEXT NOT NULL,
    "index_name" TEXT NOT NULL,
    "hangarllm_params" JSONB NOT NULL,
    "index_info" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_by" TEXT,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "updated_by" TEXT,

    CONSTRAINT "HangarLLM_ManagedVectorStoreIndexTable_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_ManagedVectorStoreIndexTable_index_name_key" ON "HangarLLM_ManagedVectorStoreIndexTable"("index_name");

