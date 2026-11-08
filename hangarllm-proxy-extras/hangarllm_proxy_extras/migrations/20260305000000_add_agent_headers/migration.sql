-- Add static_headers and extra_headers to HangarLLM_AgentsTable

ALTER TABLE "HangarLLM_AgentsTable"
  ADD COLUMN IF NOT EXISTS "static_headers" JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS "extra_headers"  TEXT[] DEFAULT ARRAY[]::TEXT[];
