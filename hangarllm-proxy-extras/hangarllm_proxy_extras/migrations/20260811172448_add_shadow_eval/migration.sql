-- CreateTable
CREATE TABLE "HangarLLM_ShadowEvalJob" (
    "id" TEXT NOT NULL,
    "api_key_id" TEXT NOT NULL,
    "router_name" TEXT NOT NULL,
    "judge_model" TEXT NOT NULL,
    "shadow_percentage" DOUBLE PRECISION NOT NULL,
    "max_turns" INTEGER NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_by" TEXT,
    "ends_at" TIMESTAMP(3) NOT NULL,
    "stopped_at" TIMESTAMP(3),

    CONSTRAINT "HangarLLM_ShadowEvalJob_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "HangarLLM_ShadowEvalAttempt" (
    "id" TEXT NOT NULL,
    "job_id" TEXT NOT NULL,
    "request_id" TEXT NOT NULL,
    "outcome" TEXT NOT NULL,
    "tier" TEXT,
    "real_model" TEXT,
    "shadow_model" TEXT,
    "confidence" DOUBLE PRECISION,
    "judge_cost" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "error" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "HangarLLM_ShadowEvalAttempt_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "HangarLLM_ShadowEvalJob_api_key_id_idx" ON "HangarLLM_ShadowEvalJob"("api_key_id");

-- CreateIndex
CREATE INDEX "HangarLLM_ShadowEvalJob_created_at_idx" ON "HangarLLM_ShadowEvalJob"("created_at");

-- CreateIndex
CREATE INDEX "HangarLLM_ShadowEvalAttempt_job_id_idx" ON "HangarLLM_ShadowEvalAttempt"("job_id");


-- One active job per key, enforced by the database rather than a read-then-create in the
-- start endpoint, which races against a concurrent start on another pod. Partial indexes
-- are not expressible in schema.prisma, so this lives here only. Active means not yet
-- stopped; the start endpoint stamps stopped_at on expired jobs before creating.
CREATE UNIQUE INDEX "HangarLLM_ShadowEvalJob_one_active_per_key"
    ON "HangarLLM_ShadowEvalJob"("api_key_id") WHERE "stopped_at" IS NULL;
