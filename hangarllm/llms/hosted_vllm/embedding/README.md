No transformation is required for hosted_vllm embedding.

VLLM is a superset of OpenAI's `embedding` endpoint.

## `encoding_format`

For OpenAI-compatible embedding calls (including `openai/...` with a custom `api_base` pointing at vLLM), HangarLLM resolves `encoding_format` when it is not set on the request. `hosted_vllm/...` models use a separate handler that never adds the field on its own, so this resolution applies to the `openai/...`-style routes only:

1. Explicit value on the embedding call (`encoding_format=...`).
2. Model config (`hangarllm_params.encoding_format` on the proxy `model_list` entry).
3. Environment variable `HANGARLLM_DEFAULT_EMBEDDING_ENCODING_FORMAT` (e.g. in `.env` or container env).

If none of those is set, or the winning value is the literal string `none`, the field is omitted from the upstream request entirely (HangarLLM also bypasses the OpenAI SDK's own base64 default), so OpenAI-compatible servers that reject `encoding_format` keep working.

To pass provider-specific parameters, see [provider-specific params](https://github.com/valteresj2/HangarLLM#readme).
