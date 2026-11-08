-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_TagTable" (
    "tag_name" TEXT NOT NULL,
    "description" TEXT,
    "models" TEXT[],
    "model_info" JSONB,
    "spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "budget_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_by" TEXT,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "HangarLLM_TagTable_pkey" PRIMARY KEY ("tag_name")
);

-- AddForeignKey
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_TagTable_budget_id_fkey') THEN
        ALTER TABLE "HangarLLM_TagTable" ADD CONSTRAINT "HangarLLM_TagTable_budget_id_fkey" FOREIGN KEY ("budget_id") REFERENCES "HangarLLM_BudgetTable"("budget_id") ON DELETE SET NULL ON UPDATE CASCADE;
    END IF;
END $$;

