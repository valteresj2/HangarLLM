# HangarLLM roadmap

This file lists the known gaps of the first release and the planned work.

## Known gaps

`CheckResponsesCost` tracks background responses but does not bill them yet. `CheckBatchCost` prices batches through core batch cost logging and has not been tested against a real provider. Managed files cover upload, retrieve, list, delete, content, batches, fine-tuning and access control, but not every edge case, such as output file id lag and storage backend URLs. `/liteadmin/slack/connect` and some vector store routes are not implemented.

Compiling the admin UI inside a Linux container fails with a Turbopack error in Next.js 16.4.1, which also happens on the original upstream source. Compose therefore uses the committed bundle by default, and `HANGARLLM_UI_STAGE=ui-builder` switches back once a fixed Next.js release is available.

The package requires the native Rust extension, so installing from source needs the Rust toolchain. Control-plane worker deployments still receive the session key in the browser.

## Next

The first priority is the foundation. That means splitting `proxy_server.py` (about 23,000 lines) into an app factory, startup modules and domain routers, publishing container images and packages, adding a selective upstream sync for providers and prices, offering a pure Python fallback for the native bridge, and running a fast smoke suite in CI.

Key protection continues with mandatory expiry and budgets on virtual keys, automatic rotation, a distinctive key prefix with a checksum so leaked keys can be detected and revoked, AES-GCM with envelope encryption through a KMS, secret detection on by default, anomaly alerts on key usage and an egress allow list per provider.

On the product side, the plan includes an agent registry across A2A, MCP and ACP with stage to prod promotion, agent composition with aggregated cost per call tree, managed memory with retention policies, real-time spend streaming with forecasts, and a tamper-evident audit log with export to object storage and SIEM tools.

Skills Git Sync will gain the external scanner inside the sync, commit diffs in the UI, GitLab and Bitbucket sources, and a pull request status check.

For enterprise operations, the plan covers SCIM with group mapping, real multi-tenant isolation, a production Helm profile, a versioned Grafana dashboard with SLOs, and more UI languages.
