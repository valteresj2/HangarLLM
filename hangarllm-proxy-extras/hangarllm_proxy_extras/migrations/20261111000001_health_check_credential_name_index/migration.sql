-- CreateIndex (CONCURRENTLY). Keep this a single statement so Prisma applies it outside a transaction.
CREATE INDEX CONCURRENTLY IF NOT EXISTS "HangarLLM_HealthCheckTable_credential_name_checked_at_idx" ON "HangarLLM_HealthCheckTable"("credential_name", "checked_at" DESC);
