Additional files for the proxy. Reduces the size of the main hangarllm package.

Currently, only stores the migration.sql files for hangarllm-proxy.

To install, run:

```bash
uv add hangarllm-proxy-extras
```
OR 

```bash
uv tool install 'hangarllm[proxy]' # installs hangarllm-proxy-extras and other proxy dependencies
```

To use the migrations, run:

```bash
hangarllm --use_prisma_migrate
```
