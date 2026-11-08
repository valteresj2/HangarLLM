These are file-specific types for the proxy.

For types you expect to be used across the proxy, put them in `hangarllm/types/proxy/` or, for database table models, `hangarllm/models/`. Don't add new types to `hangarllm/proxy/_types.py`, since SDK code can't import from it without depending on the proxy