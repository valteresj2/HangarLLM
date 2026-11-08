-- DropForeignKey
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_TeamMembership_budget_id_fkey') THEN
        ALTER TABLE "HangarLLM_TeamMembership" DROP CONSTRAINT "HangarLLM_TeamMembership_budget_id_fkey";
    END IF;
END $$;

-- AddForeignKey
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_TeamMembership_budget_id_fkey') THEN
        ALTER TABLE "HangarLLM_TeamMembership" ADD CONSTRAINT "HangarLLM_TeamMembership_budget_id_fkey" FOREIGN KEY ("budget_id") REFERENCES "HangarLLM_BudgetTable"("budget_id") ON DELETE CASCADE ON UPDATE CASCADE;
    END IF;
END $$;

