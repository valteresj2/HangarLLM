-- DropForeignKey
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_LensReview_lens_id_fkey' AND conrelid = '"HangarLLM_LensReview"'::regclass) THEN
        ALTER TABLE "HangarLLM_LensReview" DROP CONSTRAINT "HangarLLM_LensReview_lens_id_fkey";
    END IF;
END $$;

-- AddForeignKey
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_LensReview_lens_id_fkey' AND conrelid = '"HangarLLM_LensReview"'::regclass) THEN
        ALTER TABLE "HangarLLM_LensReview" ADD CONSTRAINT "HangarLLM_LensReview_lens_id_fkey" FOREIGN KEY ("lens_id") REFERENCES "HangarLLM_Lens"("id") ON DELETE CASCADE ON UPDATE CASCADE;
    END IF;
END $$;
