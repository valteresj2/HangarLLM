-- AlterTable
ALTER TABLE "HangarLLM_DailyTagSpend" ALTER COLUMN "tag" DROP NOT NULL;

-- AlterTable
ALTER TABLE "HangarLLM_DailyTeamSpend" ALTER COLUMN "team_id" DROP NOT NULL;

-- AlterTable
ALTER TABLE "HangarLLM_DailyUserSpend" ALTER COLUMN "user_id" DROP NOT NULL;

