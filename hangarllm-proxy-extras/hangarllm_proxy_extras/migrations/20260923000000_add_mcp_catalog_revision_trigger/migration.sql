CREATE OR REPLACE FUNCTION hangarllm_bump_mcp_catalog_revision() RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO "HangarLLM_Config" ("param_name", "reload_revision")
  VALUES ('mcp_catalog', 1)
  ON CONFLICT ("param_name") DO UPDATE SET "reload_revision" = "HangarLLM_Config"."reload_revision" + 1;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS "hangarllm_mcp_catalog_revision" ON "HangarLLM_MCPServerTable";
CREATE TRIGGER "hangarllm_mcp_catalog_revision"
AFTER INSERT OR UPDATE OR DELETE ON "HangarLLM_MCPServerTable"
FOR EACH STATEMENT EXECUTE PROCEDURE hangarllm_bump_mcp_catalog_revision();
