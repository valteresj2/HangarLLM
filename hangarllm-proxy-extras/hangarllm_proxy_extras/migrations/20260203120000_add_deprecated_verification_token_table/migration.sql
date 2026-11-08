-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_DeprecatedVerificationToken" (
    "id" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "active_token_id" TEXT NOT NULL,
    "revoke_at" TIMESTAMP(3) NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "HangarLLM_DeprecatedVerificationToken_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_DeprecatedVerificationToken_token_key" ON "HangarLLM_DeprecatedVerificationToken"("token");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DeprecatedVerificationToken_token_revoke_at_idx" ON "HangarLLM_DeprecatedVerificationToken"("token", "revoke_at");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_DeprecatedVerificationToken_revoke_at_idx" ON "HangarLLM_DeprecatedVerificationToken"("revoke_at");
