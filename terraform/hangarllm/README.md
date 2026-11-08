# HangarLLM Terraform stacks

Two self-contained, reusable Terraform **modules** that deploy the
**componentized** HangarLLM proxy — the gateway, backend, and UI as three
independent containers (see `helm/hangarllm-components/` for the canonical chart with the
same split).

Each module declares **no `provider` block of its own**, so it can be called
with `count` / `for_each` / `depends_on` and the caller controls region,
assume-role / impersonation, aliases, and `default_tags`. A ready-to-run root
that wires the provider lives at `<stack>/examples/default/` — that's the
one-command deploy path. To embed a stack in your own config, call the module
by source:

```hcl
module "hangarllm" {
  source = "github.com/valteresj2/HangarLLM//terraform/hangarllm/aws?ref=<tag>"
  # ... inputs ...
}
```

| Stack  | Compute     | Database (writer + reader)         | Cache       | Object store | Public entrypoint  |
| ------ | ----------- | ---------------------------------- | ----------- | ------------ | ------------------ |
| `aws/` | ECS Fargate | Aurora Postgres (IAM auth)         | ElastiCache | S3           | Application LB     |
| `gcp/` | Cloud Run   | Cloud SQL Postgres (password auth) | Memorystore | GCS          | External HTTPS LB  |

Each stack creates its own VPC and managed data stores — from
`<stack>/examples/default/`, drop in a tfvars file and run `terraform apply`.
Both stacks support a typed `proxy_config` input (mirrors `helm/hangarllm-components`'s
`gateway.config.proxy_config`) and per-component extra env vars /
secret-manager refs.

## Components

The proxy is split into three deployables:

| Component | Default image                            | Port | Role                                                                 |
| --------- | ---------------------------------------- | ---- | -------------------------------------------------------------------- |
| `gateway` | `ghcr.io/hangarllm/hangarllm-gateway:main-stable` | 4000 | LLM data plane (`/v1/chat/completions`, `/v1/embeddings`, …)         |
| `backend` | `ghcr.io/hangarllm/hangarllm-backend:main-stable` | 4001 | Management API (`/key/*`, `/user/*`, `/team/*`, `/model/*`, …)       |
| `ui`      | `ghcr.io/hangarllm/hangarllm-ui:main-stable`      | 3000 | Static Next.js dashboard served by nginx                             |

The load balancer routes gateway path prefixes (mirrored verbatim from
`gateway/routes/allowlist.py`) to the gateway, UI asset paths (`/`,
`/hangarllm-asset-prefix/*`, `/_next/*`, `/favicon.ico`) to the UI, and
everything else to the backend.

## Architecture

### AWS (`terraform/hangarllm/aws/`)

```
                        ┌───────────────────────────────────────┐
                        │            Public Internet            │
                        └─────────────────┬─────────────────────┘
                                          │ HTTP/80
                          ┌───────────────▼───────────────┐
                          │   Application Load Balancer   │
                          │   (path-routing listener)     │
                          └─┬─────────────┬─────────────┬─┘
                            │             │             │
            UI assets, /    │  /v1/chat,  │   /key/*    │
            /_next/*, …     │  /v1/embed, │   /user/*   │
                            │  …          │   …         │
              ┌─────────────▼───┐  ┌──────▼──────┐  ┌───▼──────────────┐
              │    ECS Service  │  │ ECS Service │  │   ECS Service    │
              │       (ui)      │  │  (gateway)  │  │    (backend)     │
              │   Fargate :3000 │  │ Fargate:4000│  │  Fargate :4001   │
              └─────────────────┘  └──────┬──────┘  └────────┬─────────┘
                                          │                  │
              ┌─── private subnets (one per AZ) ──────────────────────┐
              │                                                       │
              │   ┌────────────────────────┐    ┌────────────────┐   │
              │   │  Aurora Postgres       │    │  ElastiCache   │   │
              │   │  cluster (IAM auth)    │    │  Redis (1 node)│   │
              │   │  ┌───────┐  ┌───────┐  │    └────────────────┘   │
              │   │  │writer │  │reader │  │                         │
              │   │  └───────┘  └───────┘  │    ┌────────────────┐   │
              │   └────────────────────────┘    │  S3 bucket     │   │
              │                                  │  (versioned)   │   │
              │   ┌────────────────────────┐    └────────────────┘   │
              │   │  Secrets Manager       │                         │
              │   │  • HANGARLLM_MASTER_KEY  │    ┌────────────────┐   │
              │   │  • DB master password  │    │ One-off ECS    │   │
              │   │  • user-supplied API   │    │ task: prisma   │   │
              │   │    keys (referenced)   │    │ migrate deploy │   │
              │   └────────────────────────┘    └────────────────┘   │
              │                                                       │
              └─── VPC ───────────────────────────────────────────────┘
                          │ NAT gateway in one public subnet
                          ▼
                    egress to LLM providers
```

### GCP (`terraform/hangarllm/gcp/`)

```
                        ┌───────────────────────────────────────┐
                        │            Public Internet            │
                        └─────────────────┬─────────────────────┘
                                          │ HTTP/80
                          ┌───────────────▼───────────────┐
                          │ External HTTPS Load Balancer  │
                          │   (global, URL map routing)   │
                          └─┬─────────────┬─────────────┬─┘
                            │             │             │
                            │ Serverless NEGs (one per service)
                            │             │             │
              ┌─────────────▼───┐  ┌──────▼──────┐  ┌───▼──────────────┐
              │   Cloud Run     │  │  Cloud Run  │  │    Cloud Run     │
              │      (ui)       │  │  (gateway)  │  │    (backend)     │
              │      :3000      │  │   :4000     │  │      :4001       │
              └─────────────────┘  └──────┬──────┘  └────────┬─────────┘
                                          │                  │
                                          │ Serverless VPC Access connector
              ┌─── VPC (private services access range) ──────────────────┐
              │                                                          │
              │   ┌────────────────────────┐    ┌──────────────────┐    │
              │   │  Cloud SQL Postgres    │    │  Memorystore     │    │
              │   │  ┌───────┐  ┌───────┐  │    │  Redis           │    │
              │   │  │writer │  │reader │  │    └──────────────────┘    │
              │   │  └───────┘  └───────┘  │                            │
              │   └────────────────────────┘    ┌──────────────────┐    │
              │                                  │  GCS bucket      │    │
              │   ┌────────────────────────┐    │  (versioned)     │    │
              │   │  Secret Manager        │    └──────────────────┘    │
              │   │  • HANGARLLM_MASTER_KEY  │                            │
              │   │  • DB password         │    ┌──────────────────┐    │
              │   │  • user-supplied API   │    │ Cloud Run Job:   │    │
              │   │    keys (referenced)   │    │ prisma migrate   │    │
              │   └────────────────────────┘    │ deploy           │    │
              │                                  └──────────────────┘    │
              └──────────────────────────────────────────────────────────┘
```

## Images

Both stacks take per-component image references as variables. The defaults
point at the public `ghcr.io/hangarllm/hangarllm-<component>:main-stable`
images, so the stack is runnable end-to-end without pre-flight setup —
pin to a specific tag for production:

- **AWS** can pull from any registry the task execution role can reach.
  The role gets `AmazonECSTaskExecutionRolePolicy` attached, which grants
  ECR pull permissions for repositories in the same account.

- **GCP Cloud Run** can only pull from Artifact Registry or
  `gcr.io`-style registries. To use images hosted elsewhere, mirror them
  into Artifact Registry first.

## Migrations

HangarLLM's proxy runs `prisma migrate deploy` at startup, but on first apply
the gateway/backend can race the empty database. Both stacks expose a
one-off migration task that runs `python hangarllm/proxy/prisma_migration.py`
against the backend image:

- AWS: an `aws_ecs_task_definition` (`hangarllm-migrations`). Run with
  `aws ecs run-task` — the command is printed in `terraform output`.
- GCP: a `google_cloud_run_v2_job` (`hangarllm-migrations`). Run with
  `gcloud run jobs execute` — the command is printed in `terraform output`.

Run the migration job once after the first `terraform apply` and before the
gateway/backend services start serving traffic.

## Feature parity between stacks

The two modules expose the same conceptual surface; concrete inputs differ
only where the underlying cloud forces it.

| Capability                       | AWS input(s)                                            | GCP input(s)                                              |
| -------------------------------- | ------------------------------------------------------- | --------------------------------------------------------- |
| Tenant + env naming              | `tenant`, `env`                                         | `tenant`, `env`                                           |
| Pre-shared master key / license  | `hangarllm_master_key`, `hangarllm_license`                 | `hangarllm_master_key`, `hangarllm_license`                   |
| UI admin password                | `ui_password`                                           | `ui_password`                                             |
| Per-deployment tags / labels     | `tags` (`map(string)`)                                  | `labels` (`map(string)`)                                  |
| TLS posture                      | `acm_certificate_arn`, `allow_plaintext_alb`            | `lb_domains`, `allow_plaintext_lb`                        |
| Force destroy of object store    | `s3_force_destroy`                                      | `gcs_force_destroy`                                       |
| Database deletion protection     | `skip_final_snapshot`                                   | `cloudsql_deletion_protection`                            |
| `proxy_config` (typed YAML map)  | `proxy_config`                                          | `proxy_config`                                            |
| Coordination Redis               | `REDIS_*` from ElastiCache (automatic)                  | `REDIS_*` from Memorystore (automatic)                    |
| Extra plain env per component    | `gateway_extra_env`, `backend_extra_env`                | `gateway_extra_env`, `backend_extra_env`                  |
| Extra secret-backed env          | `gateway_extra_secrets`, `backend_extra_secrets` (ARNs) | `gateway_extra_secrets`, `backend_extra_secrets` (resource IDs) |
| Uvicorn `--workers` on gateway   | `gateway_num_workers`                                   | `gateway_num_workers`                                     |
| OpenTelemetry v2 (opt-in)        | `otel_endpoint`, `otel_exporter`, `otel_environment_name`, `otel_capture_message_content`, `otel_headers_secret_arn` | `otel_endpoint`, `otel_exporter`, `otel_environment_name`, `otel_capture_message_content`, `otel_headers_secret` |
| Collector sidecar (opt-in)    | `collector_enabled`, `collector_port`, `collector_cpu`, `collector_memory`, `collector_buffer_size`, `collector_on_unavailable`, `collector_drain_timeout_seconds` | same names; `collector_cpu` / `collector_memory` take Cloud Run strings |

Each module stamps its own stack-identity tag (`hangarllm:stack` on AWS,
`hangarllm-stack` on GCP — GCP label keys forbid colons) plus
`managed-by = "terraform"` onto every taggable / labelable resource and
merges `var.tags` / `var.labels` on top. Provider `default_tags` on AWS
merge on top of all of these.

Coordination Redis needs no input on either cloud. Each module provisions the
managed Redis (ElastiCache on AWS, Memorystore on GCP) and exports `REDIS_HOST`,
`REDIS_PORT` and `REDIS_SSL` (plus `REDIS_SSL_CA_CERTS` on GCP) into the gateway
and backend env. The proxy falls back to those variables to build its
coordination Redis, which backs cross-pod tpm/rpm rate limits, spend tracking
and the pod lock manager. This is independent of LLM response caching, which
stays off unless you enable `hangarllm_settings.cache` in `proxy_config`.

To coordinate through a Redis the module does not manage, set
`general_settings.coordination_redis` in `var.proxy_config`. An explicit block
overrides the `REDIS_*` env fallback; see the commented example in each
stack's `examples/default/terraform.tfvars.example`

OTel is opt-in on both clouds: leave `otel_endpoint` empty and nothing
OTel-related is added to the container env; set it and both gateway and
backend get `HANGARLLM_OTEL_V2=true` plus the full `OTEL_*` block, with
`OTEL_SERVICE_NAME` stamped per component
(`<tenant>-hangarllm-<env>-gateway` and `-backend`). Any `OTEL_*` key set
in `gateway_extra_env` / `backend_extra_env` wins for that service.

## What's not included

- TLS certificates / custom domains. Both stacks expose plain-HTTP load
  balancers; bring your own ACM cert (AWS) or managed cert (GCP) and wire
  it into the LB resource.
- Remote state backends. Default local state — add an `s3` or `gcs`
  backend block to `versions.tf` when graduating to a team environment.
- Observability beyond the cloud provider's defaults (CloudWatch logs on
  AWS, Cloud Logging on GCP). Wire your own Prometheus / Datadog / Langfuse
  via the `*_extra_env` variables, or turn on OTel v2 (see the parity
  table above).

## HCP Terraform no-code (1-click) deploy

Both stacks are publishable as no-code modules in HCP Terraform's private
registry. The end-user flow is: open the no-code launch URL, fill in a
few inputs, hit *Create workspace*, and HCP runs plan/apply against your
cloud account using a variable-set of credentials (static keys or
dynamic-credentials OIDC).

Required overrides the launcher must supply per stack:

- **AWS** (`terraform/hangarllm/aws`): `region`, `azs`, `tenant`, `env`.
  The image vars (`gateway_image`, `backend_image`, `ui_image`,
  `migrations_image`) can be left at their defaults — the GHCR images
  are anonymous-readable and ECS Fargate pulls them without extra
  credentials.

- **GCP** (`terraform/hangarllm/gcp`): `project`, `tenant`, `env`, **and
  one of**:
  - `image_registry` pointed at an Artifact Registry **remote** repository
    backed by `https://ghcr.io` (e.g.
    `us-central1-docker.pkg.dev/<project>/hangarllm/hangarllm`), so Cloud Run
    pulls the four upstream `hangarllm-*` images through it; or
  - all four per-component `*_image` URIs pointing at images mirrored
    into a regular Artifact Registry repo.

  The defaults (`ghcr.io/hangarllm`) cause Cloud Run admission to reject
  the service spec — Cloud Run only authenticates against Artifact
  Registry, `[region.]gcr.io`, or `docker.io`. See
  `terraform/hangarllm/gcp/README.md#image-pulls` for the
  `gcloud artifacts repositories create … --mode=remote-repository`
  command that sets up the passthrough repo (one-time, per project).

What still requires a manual step regardless of HCP no-code:

- The one-off migration task. The stacks auto-run it via `local-exec`
  during `terraform apply`, but that requires the `aws` / `gcloud` CLI
  on the runner. HCP-hosted runners don't have them; use an HCP agent
  pool with a custom image that includes the relevant CLI, or run the
  command printed in the `migration_run_command` output by hand after
  the first apply.
