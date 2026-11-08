-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_ManagedFileContentTable" (
    "id" TEXT NOT NULL,
    "content" BYTEA NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "HangarLLM_ManagedFileContentTable_pkey" PRIMARY KEY ("id")
);
