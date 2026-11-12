# MCP gateway security and governance

Status: draft 2. Revised after three fresh reviewers (a design critic that checked the code, a comprehension reader that saw only this document, and a zoom-out reviewer) read draft 1. The five decisions in the Decisions section are open and wait for the author. The Detailed Implementation Plan is written after they are chosen.

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
* Runner: the component that starts local servers and exposes each one to the gateway over HTTP. Introduced by this design, its shape depends on D1.
* Server instance: one running process of a local server. Instances are keyed by server and credential binding (see Phase 1a).
* Credential binding: the set of secrets used for one server instance. For a server with shared credentials there is one binding. For a server with per-user credentials there is one binding per user.
* Gateway session: the session a client opens with the gateway, identified by the `mcp-session-id` header.
* Upstream session: a session the gateway opens with one upstream server on behalf of one gateway session.
* Tool rule: a rule that allows or denies a tool call based on who calls, which tool, and the call's arguments. D3 decides where rules live.
* Destructive tool: following the MCP specification, a tool is treated as able to change data unless its annotations set `readOnlyHint` to true. Among those, a tool whose `destructiveHint` is true or missing is destructive. Admins can override both per tool, because annotations come from the server and a hostile server can lie.
* Registry: the MCP registry at `registry.modelcontextprotocol.io`, which the GitHub MCP page lists.

## Goals

1. Local servers never run inside the gateway process or container. Each server instance runs without access to the gateway's files, database, Redis or the runner's control API, with outbound network limited to hosts the admin allows, with CPU, memory and process limits, and from a package pinned by version and integrity hash.
2. Per-user secrets of one user are never present in a process that serves another user.
3. An admin can disable a server or one tool, and within 5 seconds every worker refuses new calls to it and the runner stops its instances.
4. Every create, update, delete and disable of an MCP server, toolset, tool rule and credential binding writes an audit record, and deleting a server removes its grants everywhere.
5. A request whose session the gateway cannot serve fails with an error that tells the client to reinitialize. It is never downgraded to a stateless session without notice. After D2 is built, a gateway session works on any worker for tool calls, listing and upstream session reuse.
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

Setting `mcp_local_server_mode`, values `in_process` (today, the default) and the mode D1 picks. When both this setting and `HANGARLLM_ENABLE_MCP_STDIO` are set, this setting wins and `in_process` logs a startup warning that names the risk.

Outside `in_process`, the gateway never starts a process. It asks the runner for a server instance and then talks to it over Streamable HTTP like a remote server, which also gives local servers persistent upstream sessions and health checks.

Rules that hold for every D1 option.

* Instances are keyed by (server id, credential binding). A server with per-user secrets gets one instance per user, so Goal 2 holds. Secrets reach an instance only as the environment variables its server definition names, resolved by the gateway when it asks for the instance.
* An instance starts on its first call and stops after `idle_timeout_seconds` (default 600) with no call. A stop in the middle of a gateway session makes the next call open a new upstream session, as a restarted remote server would.
* The gateway authenticates to the runner with a token derived from `HANGARLLM_SALT_KEY` for that purpose, sent on every request. Instances cannot reach the runner's control API, the gateway, the database or Redis, because each instance has its own network namespace whose only routes go to the egress proxy.
* Outbound traffic goes through an egress proxy in the runner that allows `CONNECT` only to hosts in the server's `egress_allow_hosts`, checked against the TLS SNI name, after resolving DNS once per connection. Denied connections are logged with the server id.
* Packages are fetched by the runner before the first start, not by the instance. The runner installs `npx` packages with `npm ci --ignore-scripts` from a lockfile it generates at import, and `uvx` packages with `uv pip install --require-hashes`. The lockfile and hashes are stored with the server, so the code that runs is the code an admin approved. Registry access for this fetch is a rule of the runner, never of the instance.
* Default limits are 1 CPU, 512 MB of memory, 64 processes and a 64 MB scratch directory, set per server in `resource_limits`.
* The `docker` launcher is not accepted outside `in_process`, because an instance must not control containers. A server distributed as an image is run by the runner as that image when D1 supports it, or registered as a remote server.

#### Kill switch

Each server and each tool gets a `disabled` flag. Setting it writes an audit record, is stored in the database, and is published on the coordination Redis, so every worker refuses new calls within 5 seconds with an MCP error, and the runner stops the server's instances. Calls in flight finish. Without Redis, workers pick the flag up from their next config reload. A runbook section in the MCP docs shows how to find the sessions, keys and calls that used the server in the logs.

#### Audit and cleanup

Create, update, delete and disable of MCP servers, toolsets, tool rules and credential bindings write audit records with `create_audit_log_for_update`, the helper the agent kill switch uses. Deleting a server removes its id from key, team, organization, user, end user, agent and access group permissions in the same transaction.

### Phase 1b. Sessions across workers

Step one, shipped first, is a fix. When `_handle_stale_mcp_session` meets a session ID this worker cannot serve, it answers HTTP 404, which the MCP specification defines as "start a new session". Clients then reinitialize instead of losing state without notice.

Step two is D2, which makes the session serve tool calls, listing and upstream session reuse on any worker. Every D2 option keeps the session bound to the owner fingerprint the gateway already computes (`_owner_fingerprint_for`), and every option opens upstream sessions on first use, so `initialize` does not wait for slow upstreams. `initialize` returns the capabilities of the gateway, merged from the servers the caller may use, as today.

Server-to-client requests follow the client's open stream. When several upstreams share one gateway session, the gateway rewrites the JSON-RPC id of a server-to-client request to `<server id>:<original id>` and restores it on the client's answer. Server ids are UUIDs, so the separator cannot occur in them.

### Phase 2. Tool rules, destructive tools, result scanning, registry

#### Tool rules

D3 picks where rules live. Every option follows the same meaning.

* A rule has a target (server id and a tool name glob, where `*` matches any characters and matching is case sensitive), a scope (global, organization, team or key), a condition and an effect (`allow` or `deny`).
* A rule adds to today's name-based permissions and can only narrow them.
* For one target, if any `allow` rule exists at a scope, calls at that scope are denied unless an `allow` rule matches. `deny` wins over `allow`. A target with no rules keeps today's behaviour.
* Scopes combine by intersection. A call must pass the global, organization, team and key rules that apply to it.
* The condition sees the caller (user id, team ids, organization id, key alias), the claims of the caller's JWT or OAuth token, the server and tool names, the tool's annotations, and the arguments as parsed JSON. Argument strings are compared as given, with no path normalization, and a condition on an argument that is missing evaluates to false.
* A rule with `hide_from_list: true` also removes matching tools from `tools/list` for the callers it denies. Without it the tool is listed and the call is refused, because a condition on arguments cannot be decided at listing time.
* A refused call returns a JSON-RPC error with code `-32003`, checked not to collide with codes the MCP SDK uses, and the message "Denied by tool rule". The rule name is included only when `mcp_tool_rule_show_reason` is true, so rule contents do not leak by default.
* Upstream listing pages are cached per server in `_DiscoveryCache` (`hangarllm/proxy/mcp_server/catalog.py:1337`), and the caller's permissions are applied after the cache on every request (`hangarllm/proxy/mcp_server/README.md`). Rules filter at that same point, so the cache needs no per-caller key. Rule changes are published on the coordination Redis so every worker reloads its rules.

#### Destructive tools

Setting per server, `destructive_tools`, values `allow` (today), `deny` and `confirm`. `deny` hides destructive tools. `confirm` holds a destructive call until a person confirms it, by the mechanism D4 picks. The confirmation is bound to a hash of server id, tool name and arguments, so the call that runs is the call that was confirmed. Existing servers default to `allow`. Servers imported from the registry default to `confirm`, or to `deny` if D4 drops confirmation.

Tool annotations are part of a pinned tool list, so a server that changes a tool from read-only to destructive raises `mcp_pinned_tools_changed`.

#### Result scanning and log redaction

Servers imported from the registry are created with `output_policy: untrusted` and the configured `post_mcp_call` guardrails enabled, so results pass through PII and secret masking before they reach the model. Per server, `log_redaction` (`none`, `arguments`, `results`, `both`) masks those values before the tool call is logged. Logs are not deleted.

#### Rate limits per tool

The limiter gets a per-tool limit next to the per-server limit, set on keys and teams in `mcp_tool_rpm_limits` as a map from `<server id>:<tool name>` to RPM.

#### Registry import

The dashboard's MCP page gets a "Browse registry" view backed by D5. Importing a server reuses the code behind `POST /server/import` and creates a submission with status `pending_review`, with these values set.

* The package version shown in the registry, and the lockfile or hashes the runner generates.
* `destructive_tools` as described above, `output_policy: untrusted`, and `egress_allow_hosts` empty. For a remote server the URL host is recorded but not trusted until the admin approves.
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
4. With 4 workers, a client that sends 20 tool calls in one session never gets a silent stateless session. Before D2 it gets 404 and reinitializes. After D2 all 20 calls succeed.
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

## Decisions

Each decision lists options in no particular order. The author picks one.

### D1. How local servers are isolated

1. Runner container with a sandbox per instance. A separate container on its own network starts each instance under bubblewrap or nsjail with its own network, mount and process namespaces, and exposes it over HTTP. Works wherever containers run. A breakout from one sandbox reaches the other instances in the runner and their secrets, but not the gateway. Needs user namespaces or extra capabilities in the runner container, which some managed platforms refuse.
2. One container per instance. A launcher creates a container per instance through the Docker API or the Kubernetes API, with platform network policy and limits, and can run servers shipped as images. Strongest isolation. The launcher holds the right to create containers, which must never reach the gateway or an instance, and each start takes several seconds.
3. Remote only. Outside `in_process` the gateway refuses stdio, and the project ships a reference compose service that wraps one local server per container behind an MCP HTTP bridge, which admins register as a remote server. No new HangarLLM component. Isolation, pinning, per-user instances and egress lists become the admin's work for each server, and the per-user instance rule of Phase 1a cannot be enforced by the gateway.

### D2. How a session serves requests on any worker

1. Encrypted session token. The gateway issues an `mcp-session-id` that is an authenticated encryption of the owner fingerprint, an issue time, an expiry and a key id, under a key derived from `HANGARLLM_SALT_KEY`. Upstream session IDs are not in it, so each worker opens its own upstream sessions. Admin termination uses a revocation list with a short expiry on the coordination Redis. Needs no shared session state. Server-to-client requests and subscriptions still need the client's stream, which lives on one worker, so they work only when the client's requests return to that worker. Rotating the salt key ends every session.
2. Shared session store in Redis. Owner, upstream session IDs and pending server-to-client requests live in Redis, and a Redis channel delivers messages to the worker holding the client's stream. Covers every MCP feature on any worker and prepares stream resume. Adds Redis round trips to every MCP request, and stateful MCP fails while Redis is down.
3. Sticky routing. The load balancer routes by `mcp-session-id` to one worker, which means running workers as separate processes on separate ports behind Caddy instead of one shared socket. Smallest code change. A worker restart drops its sessions, and Kubernetes and cloud load balancers need their own setup.

### D3. Where tool rules live

1. Extend `ToolPermissionGuardrail`. Wire it to `pre_mcp_call`, add conditions on token claims, and keep its regex `allowed_param_patterns` for arguments. One rule engine for LLM tool calls and MCP calls, configured as a guardrail. Conditions stay limited to what the rule format offers, and rules live in guardrail config rather than a table with its own API.
2. CEL rules. A new table and API for rules whose condition is a CEL expression, the language Kuadrant and Envoy use, checked for types when saved. Expressive and familiar to Kuadrant users. Adds a dependency whose Python implementation is less mature than the Go one, needs a cost limit per evaluation, and leaves two engines (this and `ToolPermissionGuardrail`) that must be documented as "MCP calls use the CEL rules".
3. External decision point. The gateway sends the call context to OPA or another HTTP policy service and follows its answer. Companies with OPA keep one policy store. Adds a network call per tool call, and the gateway has to choose fail-open or fail-closed when the service is down.

### D4. How a destructive call is confirmed

1. MCP elicitation. The gateway asks the client through `elicitation/create`. Immediate and needs no admin. Works only with clients that support elicitation, needs the client's stream (so it depends on D2), and an agent may answer it without a person, so it confirms intent rather than proving a human looked.
2. Approval queue. The call waits while an approver from a configured group approves it in the dashboard, with a timeout. Separates caller and approver. Slow, MCP clients time out after tens of seconds, and a pending call must survive a worker restart, so it is stored and answered as "pending, retry with this approval id".
3. No confirmation. `confirm` is dropped, and destructive tools are allowed or denied per server and by tool rules. Simplest. Leaves no middle ground.

### D5. How the registry list is fetched

1. Daily sync. A background task, holding the Redis lock, pulls the registry API into a table, and the dashboard searches it. Fast and works while the registry is down. Stores entries most deployments never use and needs outbound access to the registry.
2. Search on demand. The dashboard's search calls the registry API through the gateway when an admin searches. No stored copy. Breaks when the registry is down or the gateway has no outbound access.
3. Curated file plus import by name. The bundled file grows to a curated list refreshed at each release, and admins can import any other server by its registry name. Works offline and is reviewed by maintainers. Admins cannot browse servers missing from the file, so Goal 8 becomes "import by name" for those.

## API contract

Draft. Field names may change with the decisions.

* `MCPServer` gets `package_version`, `package_lock` (lockfile or hashes), `egress_allow_hosts`, `resource_limits` (`cpu`, `memory_mb`, `max_processes`, `max_instances`, `idle_timeout_seconds`), `destructive_tools`, `log_redaction`, `disabled`, and per-tool `tool_overrides[tool_name]` with `read_only`, `destructive` and `disabled`.
* `POST /v1/mcp/server/{server_id}/disable` and `/enable`, and the same under `/tool/{tool_name}`.
* Tool rule endpoints depend on D3. With option 1 they are the guardrail endpoints that exist. With option 2 they are `GET`, `POST`, `PATCH`, `DELETE` on `/v1/mcp/tool-rules`. With option 3 there are none.
* `GET /v1/mcp/registry/search?q=` and `POST /v1/mcp/registry/import` (name and version) for D5 options 1 and 2. Option 3 keeps `/discover` and adds `POST /v1/mcp/registry/import`.
* A refused call returns `{"code": -32003, "message": "Denied by tool rule"}`, with `data.rule` only when `mcp_tool_rule_show_reason` is true.

## Detailed Implementation Plan

Written after the decisions are chosen.

### Rollout

Phase 1a first, then 1b step one (the 404 fix), then the D2 work, then Phase 2. Each ships behind its setting with today's behaviour as the default.
