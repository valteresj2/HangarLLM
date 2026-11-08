-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_SSOIdentityAssertion" (
    "user_id" TEXT NOT NULL,
    "assertion_b64" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "HangarLLM_SSOIdentityAssertion_pkey" PRIMARY KEY ("user_id")
);
