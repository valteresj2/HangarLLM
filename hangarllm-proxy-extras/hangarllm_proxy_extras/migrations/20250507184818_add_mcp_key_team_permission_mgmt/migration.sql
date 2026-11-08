-- AlterTable
ALTER TABLE "HangarLLM_OrganizationTable" ADD COLUMN IF NOT EXISTS "object_permission_id" TEXT;

-- AlterTable
ALTER TABLE "HangarLLM_TeamTable" ADD COLUMN IF NOT EXISTS "object_permission_id" TEXT;

-- AlterTable
ALTER TABLE "HangarLLM_UserTable" ADD COLUMN IF NOT EXISTS "object_permission_id" TEXT;

-- AlterTable
ALTER TABLE "HangarLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "object_permission_id" TEXT;

-- CreateTable
CREATE TABLE IF NOT EXISTS "HangarLLM_ObjectPermissionTable" (
    "object_permission_id" TEXT NOT NULL,
    "mcp_servers" TEXT[] DEFAULT ARRAY[]::TEXT[],

    CONSTRAINT "HangarLLM_ObjectPermissionTable_pkey" PRIMARY KEY ("object_permission_id")
);

-- AddForeignKey
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_OrganizationTable_object_permission_id_fkey') THEN
        ALTER TABLE "HangarLLM_OrganizationTable" ADD CONSTRAINT "HangarLLM_OrganizationTable_object_permission_id_fkey" FOREIGN KEY ("object_permission_id") REFERENCES "HangarLLM_ObjectPermissionTable"("object_permission_id") ON DELETE SET NULL ON UPDATE CASCADE;
    END IF;
END $$;

-- AddForeignKey
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_TeamTable_object_permission_id_fkey') THEN
        ALTER TABLE "HangarLLM_TeamTable" ADD CONSTRAINT "HangarLLM_TeamTable_object_permission_id_fkey" FOREIGN KEY ("object_permission_id") REFERENCES "HangarLLM_ObjectPermissionTable"("object_permission_id") ON DELETE SET NULL ON UPDATE CASCADE;
    END IF;
END $$;

-- AddForeignKey
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_UserTable_object_permission_id_fkey') THEN
        ALTER TABLE "HangarLLM_UserTable" ADD CONSTRAINT "HangarLLM_UserTable_object_permission_id_fkey" FOREIGN KEY ("object_permission_id") REFERENCES "HangarLLM_ObjectPermissionTable"("object_permission_id") ON DELETE SET NULL ON UPDATE CASCADE;
    END IF;
END $$;

-- AddForeignKey
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'HangarLLM_VerificationToken_object_permission_id_fkey') THEN
        ALTER TABLE "HangarLLM_VerificationToken" ADD CONSTRAINT "HangarLLM_VerificationToken_object_permission_id_fkey" FOREIGN KEY ("object_permission_id") REFERENCES "HangarLLM_ObjectPermissionTable"("object_permission_id") ON DELETE SET NULL ON UPDATE CASCADE;
    END IF;
END $$;

