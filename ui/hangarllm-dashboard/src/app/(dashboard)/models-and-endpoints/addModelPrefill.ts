import { parseAsString } from "nuqs";

export const PREFILL_URL_PARAMS = {
  provider: parseAsString,
  hangarllm_model: parseAsString,
  hangarllm_credential_name: parseAsString,
};

export const CLEARED_PREFILL = { provider: null, hangarllm_model: null, hangarllm_credential_name: null };
