CREATE TABLE IF NOT EXISTS "HangarLLM_LensSignalConfig" (
    "id" TEXT NOT NULL,
    "data" JSONB NOT NULL,
    CONSTRAINT "HangarLLM_LensSignalConfig_pkey" PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "HangarLLM_LensTraceSignal" (
    "trace_id" TEXT NOT NULL,
    "trace_ref" TEXT NOT NULL DEFAULT '',
    "config_key" TEXT NOT NULL,
    "span_count" INTEGER NOT NULL,
    "claimed_until" TIMESTAMP(3),
    "classified_at" TIMESTAMP(3),
    "data" JSONB NOT NULL,
    CONSTRAINT "HangarLLM_LensTraceSignal_pkey" PRIMARY KEY ("trace_id", "trace_ref")
);
