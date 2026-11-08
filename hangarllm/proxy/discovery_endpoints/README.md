Return the proxy base url and server root path, so UI can construct the correct url to access the proxy.

This is useful when the proxy is deployed at a different path than the root of the domain.

## How to use 

**Action** Route the `/hangarllm` path to the proxy.

**Result** The UI will call `/hangarllm/.well-known/hangarllm-ui-config` to get the proxy base url and server root path.



