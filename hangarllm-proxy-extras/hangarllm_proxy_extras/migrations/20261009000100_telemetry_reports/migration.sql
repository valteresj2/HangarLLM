SET LOCAL lock_timeout = '10s';

CREATE TABLE IF NOT EXISTS "HangarLLM_TelemetryReport" (
    "id" TEXT NOT NULL,
    "window_start" DOUBLE PRECISION NOT NULL,
    "window_end" DOUBLE PRECISION NOT NULL,
    "report" JSONB NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "HangarLLM_TelemetryReport_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "HangarLLM_TelemetryReport_window_end_idx" ON "HangarLLM_TelemetryReport"("window_end");

CREATE INDEX IF NOT EXISTS "HangarLLM_TelemetryReport_created_at_idx" ON "HangarLLM_TelemetryReport"("created_at");
