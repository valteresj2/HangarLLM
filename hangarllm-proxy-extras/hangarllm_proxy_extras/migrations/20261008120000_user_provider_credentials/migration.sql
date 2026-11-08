-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_UserProviderCredentials" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "credential_name" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "credential_b64" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "HangarLLM_UserProviderCredentials_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_UserProviderCredentials_user_id_credential_name_key" ON "HangarLLM_UserProviderCredentials"("user_id", "credential_name");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "HangarLLM_UserProviderCredentials_credential_name_idx" ON "HangarLLM_UserProviderCredentials"("credential_name");
