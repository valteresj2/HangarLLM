# MCP gateway security and governance

Status: draft 3. Draft 1 was reviewed by three fresh reviewers (a design critic that checked the code, a comprehension reader that saw only the document, and a zoom-out reviewer), and the plan by a fourth that checked it against the code. The author chose an option for each of the five decisions, and the Detailed Implementation Plan follows from them. Waiting for approval to implement.

## Problem

HangarLLM already runs an MCP gateway. It federates many MCP servers behind `/mcp`, authenticates clients with virtual keys, JWT and OAuth 2.1, signs in to upstream servers with stored or per-user credentials, filters tools per key, team, user and organization, scans tool descriptions with guardrails, and prices tool calls. A company that wants every MCP server it uses behind this gateway, both servers it builds and public ones from the MCP registry that GitHub shows at https://github.com/mcp, still hits six gaps.

1. Public servers are mostly local programs started with `npx` or `uvx`. The gateway can start them (stdio transport) but runs them as child processes of the gateway worker, inside the gateway container. Such a process can read the gateway's files, reach the database and Redis over the container network, and call any host on the internet. The only control is a list of allowed launcher commands, and the code itself says a launcher such as `python` can still run any code through its arguments.
2. Nothing stops a server or a tool quickly. If a public server turns hostile, an admin has to edit it and hope every worker picks the change up, and there is no audit record of create, update or delete.
3. The gateway keeps MCP sessions in the memory of one worker. The compose stack runs 4 workers, so a follow-up request that lands on another worker silently loses its session and is served as a new stateless request. Upstream session reuse, subscriptions and server-to-client requests (elicitation, sampling) break for that client without an error.
4. Access to MCP tools is decided by tool name only. There is no rule like "this team may call `create_issue` only in repositories under `my-org/`", no rule that uses claims from the caller's token, and no different treatment for tools that change or delete data. The codebase has a tool permission guardrail with argument patterns, but it acts on LLM requests and is not wired to `/mcp` calls.
5. Results from public servers reach the model unfiltered by default. They are the main path for prompt injection and for data leaving the company.
6. The list of known public servers is a static file with 32 entries. `/server/import` accepts Claude Desktop style JSON, but nothing searches the registry or pins what is imported.

Two open source projects solve parts of this. The Envoy MCP router filter (https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/mcp_router_filter) federates servers at the proxy layer and keeps sessions in a signed ID the client carries. The Kuadrant MCP Gateway (https://docs.kuadrant.io/1.4.x/mcp-gateway/docs/guides/overview/) builds on Envoy and Kubernetes, authorizes each tool call with a CEL expression over the caller's token, offers "virtual servers" with a curated subset of tools, and injects per-user upstream credentials read from Vault. Its documentation calls it an early preview that is not ready for production.

## Terms

* Upstream server: an MCP server the gateway calls on behalf of a client. It is remote (the gateway calls its URL) or local (a program has to be run for it).
* Local server: an upstream server that speaks MCP over stdin and stdout.
* Runner: the component that starts local servers and exposes each one to the gateway over HTTP. Introduced by this design as the `mcp-runner` service (D1).
* Server instance: one running process of a local server. Instances are keyed by server and credential binding (see Phase 1a).
* Credential binding: the set of secrets used for one server instance. For a server with shared credentials there is one binding. For a server with per-user credentials there is one binding per user.
* Gateway session: the session a client opens with the gateway, identified by the `mcp-session-id` header.
* Upstream session: a session the gateway opens with one upstream server on behalf of one gateway session.
* Tool rule: a rule that allows or denies a tool call based on who calls, which tool, and the call's arguments. Rules are `ToolPermissionGuardrail` rules (D3).
* Destructive tool: following the MCP specification, a tool is treated as able to change data unless its annotations set `readOnlyHint` to true. Among those, a tool whose `destructiveHint` is true or missing is destructive. Admins can override both per tool, because annotations come from the server and a hostile server can lie.
* Registry: the MCP registry at `registry.modelcontextprotocol.io`, which the GitHub MCP page lists.

## Goals

1. Local servers never run inside the gateway process or container. Each server instance runs without access to the gateway's files, database, Redis or the runner's control API, with outbound network limited to hosts the admin allows, with CPU, memory and process limits, and from a package pinned by version and integrity hash.
2. Per-user secrets of one user are never present in a process that serves another user.
3. An admin can disable a server or one tool, and within 5 seconds every worker refuses new calls to it and the runner stops its instances.
4. Every create, update, delete and disable of an MCP server, toolset, tool rule and credential binding writes an audit record, and deleting a server removes its grants everywhere.
5. After the Redis session store (D2) is built, a gateway session works on any worker for every MCP feature, including server-to-client requests, and a session ID unknown to the whole cluster gets HTTP 404 so the client starts a new session. Until then, every downgrade to a stateless session is logged and counted.
6. Admins can write tool rules that use the caller's identity and token claims, the tool name, and argument values. Destructive tools follow a stricter default than read-only tools.
7. Servers imported from the registry get result scanning with the configured guardrails by default, and arguments and results in logs can be redacted per server.
8. Admins can search the registry from the dashboard and import a server into the existing review flow, with the package pinned and the first connection made under the same isolation as normal use.

## Non-goals

1. Replacing the HangarLLM MCP gateway with Envoy or Kuadrant. See Alternatives.
2. Kubernetes custom resources for MCP servers. They can come later on top of the management API.
3. Hosting third-party remote MCP servers.
4. Scanning the code of public packages for malware. This is acceptable only because Goal 1 limits what the code can reach and pins what runs.
5. Changing the existing auth methods for clients or upstream servers.
6. Deleting MCP logs. Logs are kept like request logs and are covered by the existing backup. Goal 7 redacts values before they are written.
7. Charging runner CPU and memory to budgets. Tool calls stay priced as today.
8. Stream resume after a dropped connection (an MCP EventStore). It is listed under Later.

## Current state

Facts the design relies on. Paths are relative to the repo root.

1. Upstream transports are `sse`, `http` and `stdio` (`hangarllm/types/mcp.py:27`). For stdio, `MCPClient._create_transport_context` (`hangarllm/mcp_client/client.py:613`) calls the MCP SDK `stdio_client`, which starts the command as a child of the gateway worker.
2. stdio is off unless `HANGARLLM_ENABLE_MCP_STDIO` is set (`hangarllm/proxy/mcp_server/stdio_gate.py`), and the compose file does not set it. Allowed launchers are `npx`, `uvx`, `python`, `python3`, `node`, `docker` and `deno`, extendable with `HANGARLLM_MCP_STDIO_EXTRA_COMMANDS` (`hangarllm/constants.py:295`). The check is `_stdio_config` (`hangarllm/proxy/mcp_server/upstream.py:167`).
3. When a server defines `env`, the child gets exactly that environment. Otherwise it gets a short allowlist of the parent's variables (`_get_safe_stdio_env`, `hangarllm/mcp_client/client.py:667`). There is no filesystem, network or resource isolation.
4. Stateful gateway sessions use the MCP SDK `StreamableHTTPSessionManager` with `event_store=None` (`hangarllm/proxy/mcp_server/server.py:712`). Session owners live in the in-memory dict `_stateful_session_owners` (`server.py:724`). `_handle_stale_mcp_session` (`server.py:1718`) strips an unknown session ID so the request is served as a new stateless session, answers 404 for sessions an admin terminated, and answers 200 to a DELETE of an unknown ID. All three depend on the memory of one worker.
5. Upstream sessions are kept in `MCPServerManager._upstream_sessions`, keyed by gateway session, server, auth fingerprint and settings (`hangarllm/proxy/mcp_server/mcp_server_manager.py:2052` and `:6435`). stdio servers never get a persistent upstream session.
6. The compose stack runs `NUM_WORKERS: ${HANGARLLM_WORKERS:-4}` (`docker-compose.yml:53`) and already has Redis configured as `coordination_redis` (`docker/hangarllm-config.yaml`).
7. Pagination cursors are stateless and encrypted with keys derived from `HANGARLLM_SALT_KEY`, so they work across replicas (`hangarllm/proxy/mcp_server/README.md`).
8. MCP tool permissions are lists of tool names per server, intersected across key, team, end user, user, agent and organization (`hangarllm/proxy/mcp_server/auth/user_api_key_auth_mcp.py:3330`). Servers also have `allowed_tools`, `disallowed_tools` and `allowed_params`, a list of argument names with no value checks (`mcp_server_manager.py:5964`). Toolsets group tools under `/toolset/{name}/mcp` (`hangarllm/proxy/management_endpoints/mcp_management_endpoints.py:3533`).
9. Two tool guardrails exist for LLM requests. `ToolPermissionGuardrail` (`hangarllm/proxy/guardrails/guardrail_hooks/tool_permission.py:496`) has allow and deny rules with regex tool names and `allowed_param_patterns`, regex checks on argument paths. `tool_policy_guardrail.py` with `HangarLLM_ToolTable` (`hangarllm/proxy/schema.prisma:1562`) has an input policy (`trusted`, `untrusted`, `blocked`) and an output policy (`trusted`, `untrusted`) per tool. Both run on the `pre_call` event of LLM requests. Neither is wired to the `pre_mcp_call` event that `/mcp` tool calls use.
10. No code reads the `readOnlyHint` or `destructiveHint` tool annotations.
11. Tool descriptions and schemas pass through every configured pre-call guardrail at discovery, and a tool that fails is hidden (`hangarllm/proxy/mcp_server/tool_catalog_guard.py:158`). Admins can pin a server's tools, and a change raises the `mcp_pinned_tools_changed` alert (`mcp_server_manager.py:5785`).
12. Tool calls pass through `pre_mcp_call`, `during_mcp_call` and `post_mcp_call` guardrail hooks (`hangarllm/types/guardrails.py:945`). `post_mcp_call` lets a text guardrail mask values in a result (`hangarllm/proxy/utils.py`, `post_mcp_call_hook`). Rate limits exist per key and per team per server, not per tool (`hangarllm/proxy/hooks/parallel_request_limiter_v3.py:2591`).
13. The known server list is `hangarllm/proxy/mcp_registry.json` with 32 entries (22 stdio), each with a `registry_url`. It is read from disk and served by `/discover` (`mcp_management_endpoints.py:3409`). `POST /server/import` (`mcp_management_endpoints.py:2115`) imports Claude Desktop `mcpServers` and Anthropic `mcp_servers` JSON. Non-admin users can submit servers, and admins approve or reject them (`mcp_management_endpoints.py:1587` to `:1880`).
14. Audit records for create, update and delete of a server are TODO (`mcp_management_endpoints.py:2073`, `:2626`, `:3336`). Deleting a server does not remove its grants (`mcp_management_endpoints.py:2630`). The agent kill switch (`hangarllm/proxy/agent_endpoints/kill_switch.py`) already writes audit records with `create_audit_log_for_update`.
15. Server health is checked only on `/server/health` (`mcp_management_endpoints.py:1521`).
16. Tool calls are logged with arguments and results (`StandardLoggingMCPToolCall`, `hangarllm/types/utils.py:3149`), counted in Prometheus (`hangarllm/integrations/prometheus.py:1132`) and traced with OpenTelemetry spans (`hangarllm/integrations/otel/model/spans.py:73`).

## Proposed design

Four phases. Phase 1a removes the risk that exists as soon as someone turns stdio on. Phase 1b fixes the session bug. Phase 2 adds governance. Later lists work that waits for demand.

Each phase is controlled by a setting in `general_settings`, named in its section, whose default keeps today's behaviour. The exception is the session error in Phase 1b, which replaces a silent downgrade that is a bug.

### Phase 1a. Isolation, kill switch, audit

#### Local servers run outside the gateway

Setting `mcp_local_server_mode`, values `in_process` (today, the default) and `runner`. When both this setting and `HANGARLLM_ENABLE_MCP_STDIO` are set, this setting wins and `in_process` logs a startup warning that names the risk.

Outside `in_process`, the gateway never starts a process. It asks the runner for a server instance and then talks to it over Streamable HTTP like a remote server, which also gives local servers persistent upstream sessions and health checks.

The runner follows these rules.

* Instances are keyed by server id and credential binding. The credential binding is the environment the gateway resolves for the call with `build_stdio_env` (`mcp_server_manager.py:4132`), so the instance key is the SHA-256 of the server id and the canonical JSON (sorted keys) of that environment. Two users with different per-user values get different instances, so Goal 2 holds. Secrets reach an instance only as those environment variables.
* An instance starts on its first call and stops after `idle_timeout_seconds` (default 600) with no call. A stop in the middle of a gateway session makes the next call open a new upstream session, as a restarted remote server would.
* The gateway authenticates to the runner with a bearer token, `HANGARLLM_MCP_RUNNER_TOKEN`, a random secret set in the environment of both services. It is separate from `HANGARLLM_SALT_KEY` so the runner never holds a key that decrypts database secrets. Instances cannot reach the runner's control API, the gateway, the database or Redis. Each instance runs under bubblewrap with its own network namespace that has only a loopback interface, and the runner talks to it over stdin and stdout, then serves it to the gateway as Streamable HTTP. Outbound traffic leaves through a Unix socket bind-mounted into the sandbox, behind a small forwarder on `127.0.0.1:3128` that the instance sees through `HTTPS_PROXY` and `HTTP_PROXY`.
* Outbound traffic goes through an egress proxy in the runner that allows `CONNECT` only to hosts in the server's `egress_allow_hosts`, checked against the TLS SNI name, after resolving DNS once per connection. Denied connections are logged with the server id.
* Packages are fetched by the runner before the first start, not by the instance. The runner installs `npx` packages with `npm ci --ignore-scripts` from a lockfile it generates at import, and `uvx` packages with `uv pip install --require-hashes`. The lockfile and hashes are stored with the server, so the code that runs is the code an admin approved. Registry access for this fetch is a rule of the runner, never of the instance. In `runner` mode, saving a stdio server asks the runner to generate the lock, and a server saved earlier without a lock does not start until an admin locks it with `POST /v1/mcp/server/{server_id}/lock`.
* Default limits are 1 CPU, 512 MB of memory, 64 processes and a 64 MB scratch directory, set per server in `resource_limits`.
* In `runner` mode, saving a server whose launcher is `docker` is refused, and an existing one is refused when called, because an instance must not control containers. A server distributed only as an image is registered as a remote server that the admin runs.

#### Kill switch

A new table, `HangarLLM_MCPServerControlTable`, keyed by server id, holds a `disabled` flag and per-tool `tool_overrides`. It is separate from the server table so servers defined in the config file can be disabled too. Setting a flag writes an audit record and publishes `{"server_id": "...", "tool_name": "..." or null, "disabled": true}` on a dedicated coordination Redis channel, `hangarllm_proxy.mcp_control`, whose subscriber applies the change at once (the config sync channel waits up to 16 seconds by design, so it is not reused). Workers keep the server in their registry and check the flag when they list tools and when they run a call, so callers get "Disabled by an administrator" instead of "not found". The gateway also asks the runner to stop the server's instances. Calls in flight finish. Without Redis, each worker reloads the table every 30 seconds. A runbook section in the MCP docs shows how to find the sessions, keys and calls that used the server in the logs.

#### Audit and cleanup

Create, update, delete and disable of MCP servers, toolsets, tool rules and credential bindings write audit records with `create_audit_log_for_update`, the helper the agent kill switch uses. Grants live in four places. `HangarLLM_ObjectPermissionTable.mcp_servers` and `.mcp_tool_permissions` cover keys, teams, organizations, users, end users and agents. `HangarLLM_AccessGroupTable.access_mcp_server_ids` and `.mcp_tool_permissions` cover access groups, and `HangarLLM_MCPToolsetTable.tools` holds toolset entries. Deleting a server keeps today's rule in `delete_mcp_server` (`hangarllm/proxy/mcp_server/db.py:1011`), where the server row delete is the commit point and cleanup after it is best effort, table by table. Cleanup runs `array_remove` on the arrays, removes the server id key from the JSON permission maps, and drops toolset entries with that server id. A failed cleanup is logged with the table name, and leftover ids point at a server that no longer exists, so they grant nothing.

### Phase 1b. Sessions across workers

Step one, shipped first, makes the silent downgrade visible without changing what clients get. When `_handle_stale_mcp_session` strips an unknown session ID, it logs a warning with the worker id and counts `hangarllm_mcp_session_rejected_total`. Answering 404 at this point would be worse than today, because with 4 workers about three requests in four would land on a worker that does not know the session, and the MCP Python client turns a 404 into a "Session terminated" error instead of reinitializing.

Step two is the Redis session store (D2), which makes the session serve every MCP feature on any worker. With it in place, an ID unknown to the whole cluster (expired, terminated or forged) gets HTTP 404 with a JSON-RPC error body, and an `initialize` that carries a stale ID starts a new session. The store keeps the session bound to the owner fingerprint the gateway already computes (`_owner_fingerprint_for`), and opens upstream sessions on first use, so `initialize` does not wait for slow upstreams. `initialize` returns the capabilities of the gateway, merged from the servers the caller may use, as today.

Server-to-client requests follow the client's open stream. When several upstreams share one gateway session, the gateway rewrites the JSON-RPC id of a server-to-client request to `<server id>:<original id>` and restores it on the client's answer. Server ids are UUIDs, so the separator cannot occur in them.

### Phase 2. Tool rules, destructive tools, result scanning, registry

#### Tool rules

Rules are `ToolPermissionGuardrail` rules (D3), wired to the `pre_mcp_call` event and extended with conditions on token claims. The guardrail keeps its current meaning, so LLM requests behave as today.

* A rule matches a tool name with a regex (`tool_name`, as today), gains an optional `mcp_server_ids` list that limits it to calls on those servers, and has a `decision` of `allow` or `deny`.
* Rules are checked in order and the first rule that matches decides, as today. On an MCP call, a guardrail whose rules name none of the call's servers in `mcp_server_ids` does not decide, so its `default_action` applies only to servers it has rules for. A server with no rules in any attached guardrail keeps today's behaviour.
* A rule adds to today's name-based permissions and can only narrow them.
* Rules are scoped by where the guardrail is attached today: globally with `default_on`, or on a team or a key through its guardrail list. Every attached guardrail must allow the call.
* Conditions are `allowed_param_patterns` (regex per argument path, as today) and the new `claim_patterns` (regex per claim path in the caller's JWT or OAuth token). Arguments are compared as given, with no path normalization, and a pattern on a missing argument or claim does not match.
* A rule with `hide_from_list: true` also removes matching tools from `tools/list` for the callers it denies. Without it the tool is listed and the call is refused, because a condition on arguments cannot be decided at listing time.
* A refused call returns a JSON-RPC error with code `-32003`, checked not to collide with codes the MCP SDK uses, and the message "Denied by tool rule". The rule name is included only when `mcp_tool_rule_show_reason` is true, so rule contents do not leak by default.
* Upstream listing pages are cached per server in `_DiscoveryCache` (`hangarllm/proxy/mcp_server/catalog.py:1337`), and the caller's permissions are applied after the cache on every request (`hangarllm/proxy/mcp_server/README.md`). Rules filter at that same point, so the cache needs no per-caller key. Rule changes are published on the coordination Redis so every worker reloads its rules.

#### Destructive tools

Setting per server, `destructive_tools`, values `allow` (today), `deny` and `confirm`. `deny` hides destructive tools. `confirm` holds a destructive call until a person confirms it, by asking the client through MCP elicitation (D4). The confirmation is bound to a hash of server id, tool name and arguments, so the call that runs is the call that was confirmed. Existing servers default to `allow`. Servers imported from the registry default to `confirm`. A client that did not declare the elicitation capability gets the call refused, because nobody can confirm it.

Tool annotations become part of a pinned tool list, so a server that changes a tool from read-only to destructive raises `mcp_pinned_tools_changed`. `PinnedMCPTool` gets an optional `annotations` field, and a pin saved before this change, which has none, does not compare annotations, so upgrading raises no alerts.

#### Result scanning and log redaction

Each server gets `result_guardrails`, a list of guardrail names that run on the `post_mcp_call` event for that server's results, in addition to guardrails attached elsewhere. Servers imported from the registry are created with the list in `general_settings.mcp_default_result_guardrails`, for example a Presidio guardrail that masks PII and secrets, so results are masked before they reach the model. Per server, `log_redaction` (`none`, `arguments`, `results`, `both`) masks those values before the tool call is logged. Logs are not deleted.

#### Rate limits per tool

The limiter gets a per-tool limit next to the per-server one. Today's per-server limit is `metadata.mcp_rpm_limit` on keys and teams, keyed by server name (`parallel_request_limiter_v3.py:2608`). The new `metadata.mcp_tool_rpm_limit` follows it, keyed by `<server name>:<tool name>`.

#### Registry import

The dashboard's MCP page gets a "Browse registry" view that searches the daily copy of the registry (D5). Importing a server reuses the code behind `POST /server/import` and creates a submission with status `pending_review`, with these values set.

* The package version shown in the registry, and the lockfile or hashes the runner generates.
* `destructive_tools: confirm`, `result_guardrails` from `mcp_default_result_guardrails`, and `egress_allow_hosts` empty. For a remote server the URL host is recorded but not trusted until the admin approves.
* Approval is by a proxy admin. After approval the runner starts the instance with empty egress, the gateway runs `tools/list`, the tool description guardrails run, and the tool list is pinned. The server becomes visible only after that. The admin then adds egress hosts, using the denied connections the runner logged.

The 32-entry `mcp_registry.json` stays as the offline fallback for `/discover`.

#### Health and counters

One worker at a time, holding a lock on the coordination Redis, checks each active server every 5 minutes with `initialize` plus `tools/list` and stores the result. Local servers with no running instance are skipped, so health checks do not keep idle instances alive. Without Redis, only health on demand stays.

New Prometheus counters: `hangarllm_mcp_session_rejected_total`, `hangarllm_mcp_tool_call_denied_total` (label `reason`: `rule`, `destructive`, `disabled`, `rate_limit`), `hangarllm_mcp_upstream_failure_total` (label `server`) and `hangarllm_mcp_runner_instances` (gauge).

### Later

1. Upstream credentials stored in Vault, AWS Secrets Manager or GCP Secret Manager by reference.
2. `X-Mcp-Virtualserver: <toolset name>` on `/mcp` as an alias of `/toolset/<name>/mcp`, for clients written for Kuadrant.
3. A documented setup with Envoy in front of HangarLLM calling it through `ext_authz`. `ext_authz` does not see the request body by default, so this needs `with_request_body` and only covers rules on tool names unless the body is sent.
4. Stream resume with an MCP EventStore.
5. Signature or provenance checks on registry entries.
6. A `/tool-rules/evaluate` endpoint to test a rule against a sample call.

## Success measures

1. With `mcp_local_server_mode` set, a test local server cannot read `/app`, cannot connect to the database, Redis or the runner API, and cannot reach a host outside its list. Each is an automated test.
2. Two users with per-user secrets on one local server get different instances, checked by the process list in the runner.
3. Disabling a server stops new calls on all 4 workers within 5 seconds in the compose stack.
4. With 4 workers and the Redis session store, a client that sends 20 tool calls in one session gets all 20 served in that session, and an elicitation raised during one of them reaches the client.
5. A registry server imported with defaults has its results masked by the configured guardrail and its destructive tools held.

## Alternatives considered

1. Replace federation with the Envoy MCP router and keep HangarLLM for auth through `ext_authz`. Rejected because per-user credentials, token exchange, cost per tool call, guardrails on results and tool description scanning all need the request body and the HangarLLM database. Envoy would add a hop and a second place to configure servers while HangarLLM still parses every call.
2. Adopt Kuadrant. Rejected because it requires Kubernetes, Istio and Keycloak, its docs call it an early preview, and it refuses tools only at call time without hiding them from the tool list.
3. Keep stdio in-process and harden the launcher list. Rejected because any allowed launcher runs arbitrary code through its arguments (`hangarllm/constants.py:297`), and an unpinned `npx` package can change between two runs.

## Risks and mitigations

1. The runner is a new service to deploy. Mitigation: same image with another entrypoint, included in compose and Helm.
2. Egress lists break servers that call hosts nobody expected. Mitigation: denied connections are logged per server and shown next to the server.
3. Pinned packages do not get fixes on their own. Mitigation: the registry view shows newer versions, and an upgrade goes through the same review.
4. A tool can accept the same value under another argument name and dodge an argument condition. Mitigation: combine rules with `allowed_params` to refuse unknown arguments, and document it.
5. One instance per user multiplies processes for popular servers. Mitigation: idle timeout, and a per-server cap on instances that refuses new users with a clear error when reached.
6. A runner that is down stops every local server. Mitigation: the runner restarts with the stack, and the gateway reports `upstream unavailable` instead of hanging.
7. A local server whose HTTP client ignores `HTTPS_PROXY` cannot reach anything, because the sandbox has no other route. Mitigation: the runner sets `NODE_USE_ENV_PROXY=1` for Node, the denied attempt shows up as a failed upstream call with the server id, and the docs list the fix per runtime.
8. Rebuilding the MCP SDK session on another worker (D2) touches SDK internals that can change between SDK versions. Mitigation: Step 6 starts with a spike, the SDK version is pinned, and a contract test fails on an SDK upgrade that breaks the restore.


## Decisions

Draft 2 listed the options without ranking. The author chose one for each.

### D1. How local servers are isolated. Chosen: option 1, runner container with a sandbox per instance

The runner is one more compose service, and only it gets the user namespace rights the sandbox needs, so the gateway keeps none. Per-user instances mean many processes, and a sandboxed process starts in milliseconds where a container takes seconds. Not chosen: one container per instance, which needs a component holding the right to create containers, and remote only, which leaves isolation, pinning and per-user instances to each admin. Revisit for Kubernetes deployments with many isolated tenants, where one container per instance fits the platform.

### D2. How a session serves requests on any worker. Chosen: option 2, shared session store in Redis

Redis is already required for router state, spend and rate limits, so the extra dependency is small. It is the only option where elicitation and sampling work on any worker, and D4 relies on elicitation. The 404 fix ships first and covers the gap until the store is ready. Not chosen: the encrypted token, which keeps server-to-client requests tied to one worker, and sticky routing, which drops sessions on worker restart and needs per-platform load balancer setup.

### D3. Where tool rules live. Chosen: option 1, extend `ToolPermissionGuardrail`

It already matches tool names by regex and checks argument values with `allowed_param_patterns`. Wiring it to `pre_mcp_call` and adding conditions on token claims gives one engine for LLM tool calls and MCP calls. Not chosen: CEL, which would leave two engines, and an external decision point, which adds a network call per tool call. CEL can be added later as a condition type if the rule format proves too narrow.

### D4. How a destructive call is confirmed. Chosen: option 1, MCP elicitation

An approval queue does not fit MCP clients, which give up on a call after seconds, and no confirmation leaves only allow or deny. A client without the elicitation capability gets destructive calls refused, and tools that must never run get a `deny` rule.

### D5. How the registry list is fetched. Chosen: option 1, daily sync

Search keeps working while the registry is down, and the bundled 32-entry file stays as the fallback without outbound access. Not chosen: search on demand, which breaks with the registry, and a curated file, which hides new public servers until a release.

## API contract

* `HangarLLM_MCPServerTable` gets nullable columns `package_version`, `package_lock` (JSON with the lockfile or hashes), `egress_allow_hosts` (text array), `resource_limits` (JSON with `cpu`, `memory_mb`, `max_processes`, `max_instances`, `idle_timeout_seconds`), `destructive_tools` (text, default `allow`), `log_redaction` (text, default `none`) and `result_guardrails` (text array). `hangarllm/types/mcp_server/mcp_server_manager.py` (`MCPServer`) and `hangarllm/types/mcp.py` gain the same fields.
* New table `HangarLLM_MCPServerControlTable` with `server_id` (primary key, not a foreign key, so config servers fit), `disabled` (boolean, default false), `tool_overrides` (JSON map from tool name to `read_only`, `destructive` and `disabled`), `updated_at` and `updated_by`.
* New table `HangarLLM_MCPRegistryEntry` with `name`, `version`, `title`, `description`, `packages` (JSON), `remotes` (JSON), `is_latest` and `synced_at`, unique on `name` and `version`.
* `POST /v1/mcp/server/{server_id}/disable` and `/enable`, `POST /v1/mcp/server/{server_id}/tool/{tool_name}/disable` and `/enable`, and `POST /v1/mcp/server/{server_id}/lock`. Proxy admin only. Each writes an audit record.
* `GET /v1/mcp/registry/search?q=&cursor=` searches `HangarLLM_MCPRegistryEntry`. `POST /v1/mcp/registry/import` with `{"name": "...", "version": "..."}` creates a submission and returns its server id.
* `ToolPermissionRule` (`hangarllm/types/proxy/guardrails/guardrail_hooks/tool_permission.py`) gains optional `mcp_server_ids` (list of server ids), `claim_patterns` (map from claim path to regex) and `hide_from_list` (boolean). Rules are managed through the guardrail endpoints that exist.
* A refused call returns JSON-RPC error code `-32003`. The message is "Denied by tool rule", "Disabled by an administrator", "Confirmation required" or "Rate limit exceeded for tool". `data.rule` is added only when `general_settings.mcp_tool_rule_show_reason` is true.
* Runner internal API, reachable only on the runner network and authenticated with `HANGARLLM_MCP_RUNNER_TOKEN`.
  * `POST /v1/packages/lock` takes a launcher (`npx` or `uvx`), a package and a version, and returns the lock to store on the server.
  * `PUT /v1/instances/{instance_key}` starts an instance or returns the running one. The body has the server id, command, args, environment, limits, egress hosts and package lock.
  * `DELETE /v1/instances/{instance_key}` and `DELETE /v1/servers/{server_id}/instances` stop instances.
  * `GET /v1/instances` lists instances with server id, start time and last call time, without environment values.
  * `/v1/instances/{instance_key}/mcp` is Streamable HTTP to the instance.

## Detailed Implementation Plan

Each step is one pull request against the default branch. Every step adds tests that fail before the change and pass after it, as `AGENTS.md` asks, and steps that change behaviour come with a live before and after run against a proxy with 2 workers and Redis. Every migration is a new directory under `hangarllm-proxy-extras/hangarllm_proxy_extras/migrations/` whose first statement is `SET LOCAL lock_timeout = '10s';`, only adds tables or columns, and comes with the same change in the three `schema.prisma` copies (repo root, `hangarllm/proxy/`, `hangarllm-proxy-extras/hangarllm_proxy_extras/`).

### Step 1. Audit, grant cleanup and kill switch

1. Migration `<timestamp>_mcp_server_control` adds `HangarLLM_MCPServerControlTable`.
2. In `hangarllm/proxy/management_endpoints/mcp_management_endpoints.py`, replace the audit TODOs at create, update and delete with `create_audit_log_for_update`, and add audit records to the toolset endpoints and to the per-user credential and env var endpoints.
3. In `delete_mcp_server` (`hangarllm/proxy/mcp_server/db.py:1011`), add the best-effort grant cleanup described in Phase 1a, and remove the `delete_mcp_server_from_team` and `delete_mcp_server_from_virtualkey` stubs it replaces.
4. Add the disable and enable endpoints, the `hangarllm_proxy.mcp_control` channel with an immediate subscriber, a 30 second reload when Redis is absent, and the flag check in the tool call path of `hangarllm/proxy/mcp_server/server.py` and in `_get_tools_from_mcp_servers` (`hangarllm/proxy/mcp_server/operations.py:1239`). Count refusals in `hangarllm_mcp_tool_call_denied_total` with `reason="disabled"`.
5. Tests: a deleted server's id is gone from an object permission, an access group and a toolset that had it, and a failure in one table still cleans the others. An update writes an audit row with before and after values. With two managers on a fake Redis, disabling a tool on one makes the other refuse it with "Disabled by an administrator" and hide it from the list, and a config-defined server can be disabled.

### Step 2. Count the silent session downgrade

1. In `_handle_stale_mcp_session` (`server.py:1718`), log a warning with the worker id and count `hangarllm_mcp_session_rejected_total` when an unknown session ID is stripped. The response does not change.
2. Tests: stripping a stale ID increments the counter, and a known ID does not.

### Step 3. Runner

1. New package `hangarllm/mcp_runner/` with `python -m hangarllm.mcp_runner` as entrypoint, one module per concern: the internal API, the instance table, the bubblewrap launcher, the stdio to Streamable HTTP bridge built on the MCP SDK, the egress proxy with the host allowlist, package locking, and idle shutdown.
2. The `Dockerfile` runtime stage installs `bubblewrap`. Compose gets an `mcp-runner` service from the same image with the runner entrypoint, on a new internal network shared only with the `hangarllm` service, with `security_opt` set to a seccomp profile at `docker/mcp-runner/seccomp.json` (Docker's default profile plus the namespace flags of `clone`, `clone3` and `unshare` that bubblewrap needs) and no added capabilities. On hosts whose AppArmor blocks unprivileged user namespaces, the docs show the AppArmor profile to load. The Helm chart in `helm/hangarllm` gets the same as an optional Deployment and NetworkPolicy.
3. The first task of this step is a spike that runs bubblewrap with the profile in the compose stack on Docker Desktop and on a Linux host. If no profile works without `CAP_SYS_ADMIN`, stop and bring it back to the author.
4. Tests: `tests/unit/mcp_runner/` covers host matching in the egress proxy (exact host, subdomain, IP literal refused, SNI that differs from the CONNECT host refused) and instance keys. `tests/integration/mcp_runner/` starts the runner and a test server written for it, and checks the first success measure (no access to `/app`, the database, Redis, the runner API, or a host outside the list), following `tests/integration/AGENTS.md`.

### Step 4. Gateway uses the runner

1. Migration `<timestamp>_mcp_server_packaging` adds `package_version`, `package_lock`, `egress_allow_hosts` and `resource_limits`.
2. Add `general_settings.mcp_local_server_mode` (`in_process` by default, or `runner`) and `HANGARLLM_MCP_RUNNER_URL`. In `hangarllm/proxy/mcp_server/upstream.py`, when the mode is `runner`, compute the instance key from `build_stdio_env`, call `PUT /v1/instances/{key}`, and build an HTTP client to the instance URL instead of `_stdio_config`. Refuse `docker` when saving and when calling, and lock packages on save through `POST /v1/packages/lock`.
3. Remove the stdio exclusion from persistent upstream sessions for runner instances (`mcp_server_manager.py:6454`).
4. Make the Step 1 disable handler call `DELETE /v1/servers/{server_id}/instances`. Count `hangarllm_mcp_upstream_failure_total` and export `hangarllm_mcp_runner_instances` from `GET /v1/instances`.
5. Tests: two users with different per-user env values get two instance keys and two processes, a shared-credential server gets one, a runner that is down gives an MCP error naming the server instead of a hang, a server without a lock refuses to start in `runner` mode, and disabling a server stops its instances.

### Step 5. Tool rules on MCP calls

1. In `hangarllm/proxy/guardrails/guardrail_hooks/tool_permission.py`, handle the `pre_mcp_call` event, read `mcp_server_ids`, `claim_patterns` and `hide_from_list`, and skip guardrails whose rules name none of the call's servers, as Phase 2 describes. The claims come from the auth result the MCP request already carries (`hangarllm/proxy/mcp_server/auth/user_api_key_auth_mcp.py`).
2. Filter `tools/list` by `hide_from_list` rules in `_get_tools_from_mcp_servers`, after the cache. Count refusals with `reason="rule"`. Check that the guardrail endpoints write audit records for rule changes and add them if they do not.
3. Tests: a rule allowing `create_issue` only when `repo` matches `^my-org/` allows one call and refuses another, a claim pattern on `groups` decides access, a hidden tool is absent from the list for the denied caller and present for another, and a guardrail with rules only for server A does not affect server B. A regression guard checks that the same guardrail on an LLM request behaves as before.

### Step 6. Session store in Redis

1. The first task is a spike that restores an MCP SDK server session on a second worker from stored state (initialized flag, client capabilities, protocol version). If the SDK cannot do it without a fork, stop and bring the finding back to the author.
2. Store per session in Redis the owner fingerprint, client capabilities, protocol version, and the upstream session id per server, with a sliding expiry equal to the current idle timeout. Admin termination deletes the record.
3. Upstream sessions on several workers. Streamable HTTP lets any worker send a POST with a stored upstream session id, so each worker opens its own HTTP connection with that id. Messages that an upstream sends in the response stream of a POST arrive on the worker that sent it. The upstream's standalone GET stream is opened by one worker that holds a lease in Redis, renewed every 10 seconds and taken over by another worker when it lapses.
4. Server-to-client requests go through a Redis channel per session to the worker holding the client's stream, with the id rewrite `<server id>:<original id>`, and the client's answer comes back through a channel to the worker waiting on it.
5. Switch `_handle_stale_mcp_session` to answer 404 with a JSON-RPC error body for IDs unknown to Redis, and let `initialize` with a stale ID start a new session. Replace `test_strips_stale_session_id_for_non_delete` and `test_stale_mcp_session_id_is_stripped` in `tests/unit/proxy/mcp_server/test_mcp_stale_session.py`.
6. Tests: with two managers on a fake Redis, a session opened on one serves a tool call on the other, an elicitation raised by an upstream reaches the client stream on the first and the answer reaches the upstream, a terminated session gets 404 on both, and the 404 body is a JSON-RPC error. The test client calls `initialize` again itself, because the MCP Python client does not.

### Step 7. Destructive tools

1. Migration `<timestamp>_mcp_server_destructive_tools` adds `destructive_tools`. Classify tools from annotations and `tool_overrides` in the control table, and add the optional `annotations` field to `PinnedMCPTool` (`hangarllm/types/mcp_server/mcp_server_manager.py:79`).
2. For `confirm`, call elicitation on the client session with the server, the tool and a summary of the arguments before forwarding, and refuse the call when the client has no elicitation capability or declines. Count refusals with `reason="destructive"`.
3. Tests: a tool with no annotations is destructive, a tool with `readOnlyHint` true is not, an override wins, a declined confirmation never reaches the upstream, a pin without annotations raises no alert after upgrade, and a pin with annotations alerts when one changes.

### Step 8. Result guardrails, log redaction, per-tool limits

1. Migration `<timestamp>_mcp_server_result_handling` adds `log_redaction` and `result_guardrails`.
2. Run the server's `result_guardrails` in `post_mcp_call_hook` (`hangarllm/proxy/utils.py`) next to the guardrails attached elsewhere, and add `general_settings.mcp_default_result_guardrails`.
3. Apply `log_redaction` when `StandardLoggingMCPToolCall` is built. Logs stay, only values are masked.
4. Add `metadata.mcp_tool_rpm_limit` to the limiter in `parallel_request_limiter_v3.py`, keyed by `<server name>:<tool name>`, and count refusals with `reason="rate_limit"`.
5. Tests: a server with a result guardrail gets its result masked while another server's result is not, a server with `log_redaction: both` logs masked arguments and results, and a per-tool limit refuses calls past the limit while another tool of the same server still works.

### Step 9. Registry sync and import

1. Migration `<timestamp>_mcp_registry_entry` adds `HangarLLM_MCPRegistryEntry`.
2. A daily task holding a Redis lock pulls the registry's versioned `/servers` endpoint, with the API version pinned in one constant, into the table.
3. Import reuses the `/server/import` code, sets the Phase 2 defaults, locks the package through the runner, and creates a `pending_review` submission. Approval starts the instance with empty egress, lists tools, runs the description guardrails and pins the list.
4. Dashboard: a "Browse registry" view on the MCP page in `ui/hangarllm-dashboard/src/app/(dashboard)/mcp-servers`, with search and an import button, and the denied egress hosts shown on the server detail.
5. Tests: a sync with a fake registry response fills the table and marks the latest version, an import creates a pending submission with the defaults, and approval pins the tool list.

### Step 10. Background health checks

1. One worker per interval, holding a Redis lock, checks each active server every 5 minutes with `initialize` plus `tools/list`, skips runner servers with no running instance, and stores the result where `/server/health` reads it.
2. Tests: with two managers on a fake Redis only one runs the check in an interval, and an idle runner server is not started by it.

### Files

New: `hangarllm/mcp_runner/` (package), `docker/mcp-runner/seccomp.json`, `tests/unit/mcp_runner/`, `tests/integration/mcp_runner/`, and one migration directory per step that adds schema. Changed: `docker-compose.yml`, `Dockerfile`, `helm/hangarllm/`, the three `schema.prisma` copies, `hangarllm/types/mcp.py`, `hangarllm/types/mcp_server/mcp_server_manager.py`, `hangarllm/types/proxy/guardrails/guardrail_hooks/tool_permission.py`, `hangarllm/proxy/mcp_server/{server.py,operations.py,upstream.py,db.py,mcp_server_manager.py}`, `hangarllm/proxy/management_endpoints/mcp_management_endpoints.py`, `hangarllm/proxy/guardrails/guardrail_hooks/tool_permission.py`, `hangarllm/proxy/hooks/parallel_request_limiter_v3.py`, `hangarllm/proxy/utils.py`, `hangarllm/integrations/prometheus.py`, `tests/unit/proxy/mcp_server/test_mcp_stale_session.py` and the dashboard MCP pages.

### Rollout

Steps 1 and 2 ship first, since they need no new component and change no client behaviour. Steps 3 and 4 ship together, with `mcp_local_server_mode` left at `in_process` by default until the runner has run in the compose stack. Step 5 follows, then step 6 after its spike. Step 6 is the first step that changes what a client sees on another worker, from a silent stateless session to the same session, and an ID unknown to the cluster starts returning 404. Steps 7, 8, 9 and 10 follow. Step 7 depends on step 6 for elicitation across workers, and step 9 depends on step 4 for package locking and the first connection.
