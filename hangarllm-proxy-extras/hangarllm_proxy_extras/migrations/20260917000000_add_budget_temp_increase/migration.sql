-- AlterTable
ALTER TABLE "HangarLLM_BudgetTable" ADD COLUMN IF NOT EXISTS "temp_budget_increase" DOUBLE PRECISION;

-- AlterTable
ALTER TABLE "HangarLLM_BudgetTable" ADD COLUMN IF NOT EXISTS "temp_budget_expiry" TIMESTAMP(3);
