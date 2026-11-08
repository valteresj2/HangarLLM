/*
  Warnings:

  - You are about to drop the column `spec_version` on the `HangarLLM_MCPServerTable` table. All the data in the column will be lost.

*/
-- AlterTable
ALTER TABLE "HangarLLM_MCPServerTable" DROP COLUMN IF EXISTS "spec_version";
