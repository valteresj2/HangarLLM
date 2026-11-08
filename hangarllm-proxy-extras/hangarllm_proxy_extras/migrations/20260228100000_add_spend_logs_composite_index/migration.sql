-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_SpendLogs_startTime_request_id_idx" ON "HangarLLM_SpendLogs"("startTime", "request_id");
