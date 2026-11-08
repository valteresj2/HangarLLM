SET LOCAL lock_timeout = '10s';

CREATE TABLE IF NOT EXISTS "HangarLLM_SkillGitSource" (
    "source_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "api_base_url" TEXT NOT NULL DEFAULT 'https://api.github.com',
    "owner" TEXT NOT NULL,
    "repository" TEXT NOT NULL,
    "branch" TEXT NOT NULL DEFAULT 'main',
    "skills_path" TEXT NOT NULL DEFAULT '',
    "auth_type" TEXT NOT NULL DEFAULT 'token',
    "credentials" TEXT,
    "app_id" TEXT,
    "installation_id" TEXT,
    "scope" TEXT NOT NULL DEFAULT 'access_group',
    "access_group_id" TEXT,
    "publish_mode" TEXT NOT NULL DEFAULT 'auto',
    "remove_policy" TEXT NOT NULL DEFAULT 'unpublish',
    "auto_sync" BOOLEAN NOT NULL DEFAULT true,
    "poll_interval_seconds" INTEGER NOT NULL DEFAULT 300,
    "webhook_secret" TEXT,
    "status" TEXT NOT NULL DEFAULT 'never_synced',
    "status_message" TEXT,
    "last_seen_sha" TEXT,
    "applied_sha" TEXT,
    "managed_skills" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "quarantined_skills" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "last_checked_at" TIMESTAMP(3),
    "last_synced_at" TIMESTAMP(3),
    "sync_lock_until" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_by" TEXT,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_by" TEXT,
    CONSTRAINT "HangarLLM_SkillGitSource_pkey" PRIMARY KEY ("source_id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "HangarLLM_SkillGitSource_name_key" ON "HangarLLM_SkillGitSource"("name");

CREATE TABLE IF NOT EXISTS "HangarLLM_SkillGitSync" (
    "sync_id" TEXT NOT NULL,
    "source_id" TEXT NOT NULL,
    "commit_sha" TEXT,
    "trigger" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "report_json" TEXT NOT NULL DEFAULT '{}',
    "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMP(3),
    "triggered_by" TEXT,
    CONSTRAINT "HangarLLM_SkillGitSync_pkey" PRIMARY KEY ("sync_id")
);

CREATE INDEX IF NOT EXISTS "HangarLLM_SkillGitSync_source_id_started_at_idx" ON "HangarLLM_SkillGitSync"("source_id", "started_at" DESC);
