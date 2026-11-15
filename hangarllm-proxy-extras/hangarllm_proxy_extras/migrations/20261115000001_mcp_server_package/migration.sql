SET LOCAL lock_timeout = '10s';

CREATE TABLE IF NOT EXISTS "HangarLLM_MCPServerPackageTable" (
    "server_id" TEXT NOT NULL,
    "launcher" TEXT NOT NULL,
    "package_name" TEXT NOT NULL,
    "package_version" TEXT NOT NULL,
    "package_command" TEXT,
    "package_lock" TEXT NOT NULL,
    "egress_allow_hosts" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_by" TEXT,

    CONSTRAINT "HangarLLM_MCPServerPackageTable_pkey" PRIMARY KEY ("server_id")
);
