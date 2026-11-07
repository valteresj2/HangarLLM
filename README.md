<p align="center">
  <img src="branding/marketing/hero-one-home.webp" alt="HangarLLM, one home for every AI agent" width="100%">
</p>

<h1 align="center">HangarLLM</h1>

<p align="center"><b>One home for every AI model and agent.</b><br>
An open-source LLM gateway, Python SDK and admin UI. Call 100+ model providers through one OpenAI-compatible API, with keys, budgets, guardrails, routing and observability built in.</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-F5B400?style=flat-square&labelColor=0F172A"></a>
  <img alt="Python 3.10 to 3.15" src="https://img.shields.io/badge/python-3.10%E2%80%933.15-F5B400?style=flat-square&labelColor=0F172A">
  <img alt="Self-hosted" src="https://img.shields.io/badge/self--hosted-Docker%20%C2%B7%20Kubernetes-F5B400?style=flat-square&labelColor=0F172A">
</p>

## What is HangarLLM

HangarLLM is a gateway that sits between your applications and every model or agent they use. Teams point their OpenAI, Anthropic or MCP clients at one URL, and HangarLLM handles authentication, routing, retries, fallbacks, spend tracking, rate limits, guardrails and logging for all of them.

It is a fork of [LiteLLM](https://github.com/BerriAI/litellm) (MIT). Everything is open source under the MIT License, including the capabilities that upstream sells as an enterprise add-on. There is no license key, no seat limit, and no call to a license server. See [NOTICE](NOTICE) for provenance.

<p align="center">
  <img src="branding/marketing/build-in-any-tool.webp" alt="Build agents in any AI tool" width="49%">
  <img src="branding/marketing/any-platform.webp" alt="Use them from any platform" width="49%">
</p>

## Features

**Models and protocols.** One OpenAI-compatible API for 100+ providers (OpenAI, Anthropic, Azure, Bedrock, Vertex AI, Gemini, Mistral, Groq, Ollama, vLLM and many more), covering `/chat/completions`, `/responses`, `/messages`, `/embeddings`, `/images`, `/audio`, `/batches`, `/files`, `/rerank` and realtime. The gateway also speaks MCP and A2A, so agents and tools live behind the same keys and policies as models.

**Routing and reliability.** Load balancing across deployments, retries, fallbacks, cooldowns, latency and cost based routing, an auto router that picks a model per prompt, and Redis-backed shared state for multi-instance deployments.

**Access and governance.** Virtual keys, teams, organizations, projects, customers, per-key and per-team budgets, TPM/RPM limits, priority-based rate limit reservations, IP allow lists, and model access groups.

**Formerly paid features, now open.** These are part of HangarLLM for every deployment.

| Capability | What you get |
| --- | --- |
| SSO | Google, Microsoft, Okta and any OIDC or SAML provider for the admin UI, plus custom SSO handlers and JWT auth |
| Audit log | Who changed which key, team, model or setting, and when, queryable from the API and the UI |
| Guardrails | Secret detection, banned keywords, blocked users, OpenAI and Google moderation, Llama Guard, LLM Guard, PII masking, and custom guardrails per key or team |
| Alerts | Email alerts through SMTP, SendGrid or Resend, PagerDuty incidents, Slack and webhook alerts for budgets, outages and slow responses |
| Cost tracking | Spend per key, user, team, tag and model, including batch and Responses API jobs, with Prometheus metrics |
| Stage to prod | Promote models, guardrails and settings from a staging gateway to production |
| Memory | Managed files, managed vector stores and shared agent memory behind the gateway |
| Secret managers | AWS Secrets Manager and KMS, Azure Key Vault, Google Secret Manager, HashiCorp Vault and CyberArk |
| Branding | Custom logo, colors and docs title for the admin UI and the OpenAPI page |

<p align="center">
  <img src="branding/marketing/combine-agents.webp" alt="Combine agents into new agents" width="49%">
  <img src="branding/marketing/enterprise-ready.webp" alt="Open source, self-hosted, enterprise-ready" width="49%">
</p>

## Quickstart

### Docker Compose (gateway, admin UI, Postgres, Redis, Prometheus)

```bash
cp .env.example .env
```

Set `HANGARLLM_MASTER_KEY` and `HANGARLLM_SALT_KEY` in `.env` (any `sk-` prefixed random string, for example `sk-$(openssl rand -hex 32)`), then start the stack.

```bash
docker compose up -d --build
```

The API listens on `http://localhost:4000`, the admin UI on `http://localhost:4000/ui` (user `admin`, password is your master key) and Prometheus on `http://localhost:9090`. Turn on gateway metrics with `callbacks: ["prometheus"]` under `litellm_settings` in your config.

Keep `HANGARLLM_SALT_KEY` stable. Changing it makes the provider credentials already stored in the database unreadable.

### Docker, single container

```bash
docker run -p 4000:4000 -e HANGARLLM_MASTER_KEY=sk-change-me -e OPENAI_API_KEY=$OPENAI_API_KEY ghcr.io/hangarllm/hangarllm:latest --model gpt-4o
```

### pip

```bash
pip install 'hangarllm[proxy]'
```

```bash
hangarllm --model gpt-4o
```

Building from source needs the Rust toolchain, because part of the request path is a native extension built with maturin.

```bash
uv sync --extra proxy
```

```bash
uv run hangarllm --config litellm/proxy/proxy_config.yaml
```

### Call it

```python
import openai

client = openai.OpenAI(api_key="sk-change-me", base_url="http://localhost:4000")
response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hello from the hangar"}])
print(response.choices[0].message.content)
```

### Python SDK

```python
import hangarllm

response = hangarllm.completion(model="anthropic/claude-sonnet-4-5", messages=[{"role": "user", "content": "Hello!"}])
```

`import hangarllm` and `import litellm` return the same module, so existing code and integrations keep working.

## Configuration

Every setting that upstream reads from a `LITELLM_*` environment variable also accepts a `HANGARLLM_*` spelling. When both are set, the explicit `LITELLM_*` value wins. An empty `HANGARLLM_*` value is ignored.

| Variable | Purpose |
| --- | --- |
| `HANGARLLM_MASTER_KEY` | Admin key for the API and the UI |
| `HANGARLLM_SALT_KEY` | Encrypts provider credentials stored in the database |
| `DATABASE_URL` | Postgres connection string for keys, teams, spend and audit logs |
| `REDIS_HOST`, `REDIS_PORT` | Shared cache, rate limits and router state across instances |
| `HANGARLLM_LOCAL_MODEL_COST_MAP` | The bundled model price map is used at startup by default, so the gateway makes no outbound call to fetch prices. Set it to `false` to fetch the latest map from the network instead |
| `HANGARLLM_DISABLED_FEATURES` | Comma separated list of features to switch off, for a leaner deployment |
| `HANGARLLM_DISABLE_SKILL_GIT_SYNC` | Set to `true` to stop the background job that polls GitHub skill repositories |

## Skills Hub Git Sync

Connect the Skills Hub to your company's GitHub (or GitHub Enterprise Server) and treat a repository as the source of truth for agent skills. Open **Skills > GitHub Sync > Connect repository**, pick the credentials, the repository, the branch and the folder that holds the skills (one folder per skill, each with a `SKILL.md`), and HangarLLM does the rest.

Every push to the branch is picked up through a webhook, with polling as a fallback, and the gateway re-applies the skills at that exact commit. Only one replica syncs at a time. Each skill is validated on its own before it reaches the hub. A skill with an invalid `SKILL.md`, a duplicate name, a symlink, a compiled binary, a secret or a dangerous shell pattern is quarantined, while the other skills still go out. When a skill that was already live breaks in a new commit, its last good version stays live. Anything unexpected is shown in a banner on the Skills page and in the per-commit sync report, and is sent to your configured Slack or webhook alerts (`skill_sync_alerts`).

You choose how far the skills reach. **Access group** (recommended) keeps them private and adds them to the access group `git:<owner>/<repo>`, which you attach to the teams or keys that should get them. **All API keys** publishes them to every key. A repository can auto-publish every push, or hold each new commit until an admin approves it. Any earlier commit can be restored with one click. Skills that come from Git are read-only in the hub, so edits always go through the repository.

For organizations, use a GitHub App with read-only *Contents* and *Metadata* permissions, installed on the repositories that hold skills. For a quick start, a fine-grained token with the same read-only access works too, and public repositories need no credentials at all.

## Migrating from LiteLLM

HangarLLM is a drop-in replacement. The Python package is still importable as `litellm`, the `litellm` CLI command still works next to `hangarllm`, and config files, `LITELLM_*` variables, database schema, API routes and response headers are unchanged. Point your existing deployment at the HangarLLM image, keep your `DATABASE_URL` and salt key, and remove `LITELLM_LICENSE`, which is no longer needed.

The upstream admin agent ("LiteAdmin") is not part of HangarLLM.

## Deploy

| Target | Where |
| --- | --- |
| Docker Compose | [docker-compose.yml](docker-compose.yml) and [docker/docker-compose.quickstart.yml](docker/docker-compose.quickstart.yml) |
| Kubernetes (single image) | [helm/hangarllm](helm/hangarllm) |
| Kubernetes (gateway, UI backend and UI as separate services) | [helm/hangarllm-components](helm/hangarllm-components) |
| AWS ECS or GCP Cloud Run | [terraform/litellm](terraform/litellm) |

These run on plain Docker, Kubernetes, GKE, AKS and EKS.

## Development

Start Postgres, Redis and Prometheus.

```bash
docker compose up -d db redis prometheus
```

Install the backend (requires Rust) and run the gateway with reload.

```bash
make bootstrap
```

```bash
uv run python litellm/proxy/proxy_cli.py --config litellm/proxy/dev_config.yaml --reload
```

Run the admin UI in dev mode from `ui/litellm-dashboard`.

```bash
npm run dev
```

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE). HangarLLM is an independent project and is not affiliated with BerriAI. "LiteLLM" is a name and trademark of BerriAI, used here only to describe the project's origin and compatibility.
