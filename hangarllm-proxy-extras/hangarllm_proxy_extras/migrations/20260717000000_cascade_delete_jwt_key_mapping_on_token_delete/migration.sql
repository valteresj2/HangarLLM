-- DropForeignKey
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_JWTKeyMapping_token_fkey') THEN
        ALTER TABLE "HangarLLM_JWTKeyMapping" DROP CONSTRAINT "HangarLLM_JWTKeyMapping_token_fkey";
    END IF;
END $$;

-- AddForeignKey
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_JWTKeyMapping_token_fkey') THEN
        ALTER TABLE "HangarLLM_JWTKeyMapping" ADD CONSTRAINT "HangarLLM_JWTKeyMapping_token_fkey" FOREIGN KEY ("token") REFERENCES "HangarLLM_VerificationToken"("token") ON DELETE CASCADE ON UPDATE CASCADE;
    END IF;
END $$;
