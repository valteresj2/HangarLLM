DO $$
BEGIN
    ALTER TABLE IF EXISTS "HangarLLM_Engine" RENAME TO "HangarLLM_Lens";
    ALTER TABLE IF EXISTS "HangarLLM_EngineRun" RENAME TO "HangarLLM_LensRun";
    ALTER TABLE IF EXISTS "HangarLLM_EngineWorker" RENAME TO "HangarLLM_LensWorker";
    IF EXISTS (
        SELECT 1 FROM pg_attribute
        WHERE attrelid = to_regclass('"HangarLLM_LensRun"')
          AND attname = 'engine_id' AND NOT attisdropped
    ) THEN
        ALTER TABLE "HangarLLM_LensRun" RENAME COLUMN "engine_id" TO "lens_id";
    END IF;
    ALTER INDEX IF EXISTS "HangarLLM_Engine_pkey" RENAME TO "HangarLLM_Lens_pkey";
    ALTER INDEX IF EXISTS "HangarLLM_EngineRun_pkey" RENAME TO "HangarLLM_LensRun_pkey";
    ALTER INDEX IF EXISTS "HangarLLM_EngineWorker_pkey" RENAME TO "HangarLLM_LensWorker_pkey";
    ALTER INDEX IF EXISTS "HangarLLM_EngineWorker_token_hash_key" RENAME TO "HangarLLM_LensWorker_token_hash_key";
    ALTER INDEX IF EXISTS "HangarLLM_EngineRun_engine_id_created_at_idx" RENAME TO "HangarLLM_LensRun_lens_id_created_at_idx";
END $$;
