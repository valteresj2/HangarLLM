-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_UISettings" (
    "id" TEXT NOT NULL DEFAULT 'ui_settings',
    "ui_settings" JSONB NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "HangarLLM_UISettings_pkey" PRIMARY KEY ("id")
);

