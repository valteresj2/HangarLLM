SET LOCAL lock_timeout = '10s';

CREATE SEQUENCE IF NOT EXISTS "hangarllm_environment_variables_revision_seq";
GRANT USAGE ON SEQUENCE "hangarllm_environment_variables_revision_seq" TO PUBLIC;

CREATE OR REPLACE FUNCTION hangarllm_bump_environment_variables_revision() RETURNS TRIGGER AS $$
DECLARE
  next_revision BIGINT := nextval(format('%I.hangarllm_environment_variables_revision_seq', TG_TABLE_SCHEMA)::regclass);
BEGIN
  IF TG_OP = 'UPDATE' THEN
    NEW."reload_revision" := GREATEST(next_revision, OLD."reload_revision" + 1);
  ELSE
    NEW."reload_revision" := next_revision;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS "hangarllm_environment_variables_revision" ON "HangarLLM_Config";
CREATE TRIGGER "hangarllm_environment_variables_revision"
BEFORE INSERT OR UPDATE ON "HangarLLM_Config"
FOR EACH ROW WHEN (NEW."param_name" = 'environment_variables')
EXECUTE PROCEDURE hangarllm_bump_environment_variables_revision();
