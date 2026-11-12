# Providers page

Status: draft 3. Revised after a Goldfish review, and the author chose an option for every decision. Waiting for approval to implement.

## Problem

Adding a model today means filling one long form, `ui/hangarllm-dashboard/src/components/add_model/AddModelForm.tsx`, inside the "Add Model" tab of the "Models + Endpoints" page. The admin picks a provider from a searchable list of 153 entries, types model names, picks or creates a credential, opens advanced settings and presses "Test Connect". Nothing on screen answers the questions an admin asks first: which providers already have a credential, which credentials are failing, and which providers have models in use.

A provider's state is spread over three places: the "LLM Credentials" tab (`llm-credentials`), the "All Models" tab and the "Health" tab. There is no way to test a saved credential on its own and no way to test every credential at once. The Health tab checks one model at a time (`ui/hangarllm-dashboard/src/components/model_dashboard/HealthCheckComponent.tsx`, `GET /health?model_id=`), and each check sends a real completion.

[9router](https://github.com/decolua/9router) solves the same problem with a Providers page: a grid of provider cards grouped by type, each card showing how many connections work or fail, a "Test All" button per group, a detail page per provider, and buttons to add an OpenAI compatible or Anthropic compatible endpoint. Its fork [n9router](https://github.com/nightwalker89/n9router) adds self-hosted speech and embedding providers that must name their own base URL.

## Terms

* Credential: a row of `HangarLLM_CredentialsTable`. The page shows credentials, so this document uses the word credential throughout. It does not use "connection", which the code already uses for per-user OAuth connections (`/credentials/user_connections`).
* Configured provider: a provider with at least one credential.
* Healthy credential: a credential whose latest test passed. Failing credential: its latest test failed. Untested credential: no stored test result.

## Goals

1. One page that shows every provider the gateway can use, grouped by type, configured providers first.
2. Each provider card shows how many of its credentials are healthy and how many are failing, the error of the latest failure, and how many models use the provider.
3. A provider detail view that lists the provider's credentials and models, and lets an admin add, test, edit and delete credentials, and add a model already bound to the provider and one of its credentials.
4. A "Test All" action per group that tests the group's credentials.
5. Adding an OpenAI compatible or Anthropic compatible endpoint from the page with a name, base URL and key, shown as its own card.
6. A compatible endpoint can never be saved without a base URL, so it cannot fall back to the vendor's public API.

## Non-goals

1. OAuth login to consumer subscriptions (Claude Code, Codex, Copilot, Cursor, Kiro and similar) used as a shared API. Their terms of use limit them to the individual user.
2. Rotating many accounts of one provider to stay under quotas (9router "Token Rotate" and "Token Swap Pool").
3. A MITM proxy, a local root CA, or a DNS redirect.
4. Providers that drive a provider's chat website with a browser session.
5. Per-user OAuth connections (`/credentials/user_connections`). They keep their current panel.
6. Changing how requests are routed. Editing a model's existing `order` (D6) uses the routing that exists today.

## Current state

Facts the design relies on. Paths are relative to the repo root.

1. Provider metadata comes from `GET /public/providers/fields` (`hangarllm/proxy/public_endpoints/public_endpoints.py:468`), which serves the hand-edited `hangarllm/proxy/public_endpoints/provider_create_fields.json`. Each of its 153 entries has `provider` (a display key such as `OpenAI_Compatible`), `provider_display_name`, `hangarllm_provider` (the router id such as `openai`), `credential_fields` and `default_model_placeholder`. There is no category and no auth type. 146 entries have an `api_key` field and 122 have an `api_base` field.
2. The entry `OpenAI_Compatible` has `hangarllm_provider` `openai`, the same id as OpenAI. There is no Anthropic compatible entry. The `Anthropic` entry already accepts an `api_base`.
3. A second provider list, the `Providers` enum in `ui/hangarllm-dashboard/src/components/provider_info_helpers.tsx:79`, feeds `CredentialModal`, `AddModelPanel.tsx`, `ModelHubProviders.tsx`, `DecisionModelGarden.tsx` and the search tools components. It can disagree with the JSON.
4. Logos are static files in `ui/hangarllm-dashboard/public/assets/logos` resolved by `getProviderLogoAndName` in `ui/hangarllm-dashboard/src/components/molecules/logo/Logo.tsx`.
5. `HangarLLM_CredentialsTable` has `credential_name` (unique), `display_name`, `credential_values`, `credential_info` and audit fields. It has no enabled flag. The provider is stored in `credential_info.custom_llm_provider` in the dashboard's display casing (for example `Anthropic`), and `stored_credential_provider` in `hangarllm/proxy/common_utils/credential_hydration.py:56` turns it into the router id by lowercasing it. `CredentialView.source` (`hangarllm/models/credentials.py:40`) tells config defined credentials, which are read only, from stored ones.
6. `POST /health/test_connection` (`hangarllm/proxy/health_endpoints/_health_endpoints.py:2491`) tests an unsaved model and already accepts `hangarllm_credential_name` to use a stored credential. It sends a request of the chosen mode, so a chat test costs one completion.
7. `get_valid_models` (`hangarllm/utils.py:9144`) can list a provider's models through its API, but it returns an empty list on any error and caches results, so it cannot tell a bad key from a provider with no models. About 25 provider configs implement a model list call.
8. `HangarLLM_HealthCheckTable` (`hangarllm/proxy/schema.prisma:1425`) stores health results per model (status, error message, response time, checked at, checked by).
9. The router already orders deployments of one model name through the deployment `order` parameter (`get_order_filtered_deployments`, `hangarllm/utils.py:6374`).
10. `AddModelPanel.tsx` prefills `provider` and `hangarllm_model` from the URL (`PREFILL_URL_PARAMS`), but not a credential.
11. The DockWorker agent in the dashboard calls the management API with the signed-in admin's token through tools built from `/openapi.json`. Its deny list (`ui/hangarllm-dashboard/src/components/liteadmin/openapiOperations.ts`, `DENIED_OPERATION_PATHS`) blocks every path containing `credential`.

## Proposed design

### Page

The Providers view shows three groups of cards in this order.

1. Cloud API: providers whose credential fields include an API key and no cloud identity fields.
2. Enterprise cloud: AWS Bedrock, Vertex AI, Azure OpenAI, Azure AI, SageMaker, Watsonx and others that authenticate with cloud identity or several fields.
3. Self-hosted and compatible: Ollama, hosted vLLM, LM Studio, llama.cpp server, text embeddings inference, whisper servers, and every compatible endpoint the admin added.

Which provider goes in which group is decision D2. Inside a group, configured providers come first, then the rest by display name. A search box filters every group, and a "Configured only" toggle hides providers without credentials.

Each card shows the logo, the display name, and a status line built from the counts, for example "2 healthy · 1 failing (401)". When every credential is untested it says "Not tested", and a provider without credentials says "Not configured". The error shown is the HTTP status of the latest failure, or "timeout" or "network". A second line shows "M models".

A model counts toward a provider when its `hangarllm_params.model` prefix, or its credential's provider, resolves to that provider's router id. A compatible endpoint card counts only the models that use one of its own credentials.

### Provider detail

Clicking a card opens a detail view with two sections.

Credentials lists the credentials whose provider resolves to this provider's router id, using `stored_credential_provider`. Each row shows the display name, the latest test result with latency and time, and actions to test, edit and delete. Rows whose `source` is config show a "From config" badge, can be tested, and have no edit or delete. "Add credential" opens a form built from the provider's `credential_fields`, tests the values before saving, and saves only when the test passes, unless the admin chooses "Save without testing". A credential that has not passed a test is saved as untested.

Models lists the models that count toward the provider, with their health status and `order`. "Add model" opens the existing model form with the provider and the chosen credential filled in. This needs `hangarllm_credential_name` added to `PREFILL_URL_PARAMS`.

### Testing a credential

A test checks that a credential reaches the provider and is accepted. The design extends `POST /health/test_connection` rather than adding a new route:

* It accepts `hangarllm_credential_name` with no model, plus an optional model.
* For providers that implement a model list call, it calls that call directly, without the `get_valid_models` cache, and passes the provider's error through, so a 401 shows as a failure.
* For other providers it needs a model. The admin picks one test model per credential, stored with the credential in `credential_info.test_model`. Until one is picked, the credential stays untested and the row asks for a model.
* It returns ok or error, the HTTP status, a short message and the latency. It never returns key values.
* Calls that name a stored credential require a proxy admin, enforced through the existing route checks.
* A completion test is billed and logged like today's "Test Connect", under the caller's key.

"Test All" on a group tests every credential in the group, at most 5 at a time, with a 20 second timeout per test, and shows progress per card. The Health tab's per model "Run all checks" stays.

### Compatible endpoints

"Add OpenAI compatible" and "Add Anthropic compatible" ask for a display name, a base URL, an API key and an optional list of model names.

* They create a credential with `custom_llm_provider` `OpenAI` or `Anthropic` in the dashboard's casing, `api_base` set to the URL, `display_name` set to the name given, and `credential_info.compatible` set to `openai` or `anthropic`.
* The `compatible` marker makes the page show the credential as its own card named after `display_name`, and keeps it out of the OpenAI and Anthropic cards.
* The backend rejects creating or updating a credential with a `compatible` marker and an empty `api_base`, so a compatible endpoint cannot send requests and keys to `api.openai.com` or `api.anthropic.com`.

Self-hosted providers keep their current behavior. Ollama, hosted vLLM and LM Studio already default to localhost or their own environment variable, so no request-time change is needed.

### DockWorker

`POST /health/test_connection` is not on the DockWorker deny list. Because it is a POST, the agent shows it as a change and runs it only after the admin approves the card. Credential create, update and value routes stay denied. The agent never sees key values because the credential routes that return them stay blocked.

## Alternatives considered

1. Improve the existing tabs instead of building a page: add health and test columns to the LLM Credentials tab and a provider filter to All Models. Less code, but it keeps a provider's state in three places, which is the problem this design exists to fix, and it is not what was asked for.
2. Store credentials per provider as a new "connection" entity with priority, as 9router does. It duplicates `HangarLLM_CredentialsTable` and the router's `order`, so it is not proposed.

## Risks and mitigations

1. Test All on many credentials hits provider rate limits or costs money. Mitigation: a limit of 5 parallel tests, a 20 second timeout, model list tests where available, and completion tests only with an explicit test model.
2. A test result that looks healthy while completions fail (for example a key that can list models but has no billing). Mitigation: the row says which kind of test ran, and the Health tab still runs real model checks.
3. Writing test results next to secrets. Mitigation: decision D3 offers storage outside the credentials row.
4. Two provider lists disagreeing. Mitigation: Step 1 makes the JSON the only list for the new page and for `CredentialModal`.
5. Key leakage through the test route. Mitigation: the response carries no key values, and route tests assert that the key never appears in the response or logs.

## Decisions

### D1. Where the page lives. Chosen: option 2

1. Replace the "Add Model" tab with the Providers view and reach the model form from a provider. Fewer entry points, one more click for admins who only want the form.
2. Add a "Providers" tab next to "Add Model" and keep both. Nothing breaks, two entry points for the same task.
3. A top level "Providers" sidebar entry outside "Models + Endpoints", as in 9router. Separates provider setup from the models list.

### D2. Where a provider's group comes from. Chosen: option 1

1. A `category` field on every entry of `provider_create_fields.json`. One list served by the backend, but every entry needs a value and the generator or editor that maintains the file must keep it.
2. A mapping in the UI. Quick to change, a third list next to the JSON and the enum.
3. Derive it from credential fields. No list to maintain, but with 122 entries having `api_base`, a rule based on that field misplaces most cloud providers, so it needs a curated exception list.

### D3. Where test results are stored. Chosen: option 1

1. Add a nullable `credential_name` column to `HangarLLM_HealthCheckTable` and store credential tests there. Reuses the table that already holds health results, one schema change, history kept.
2. Store the latest result in `credential_info` on the credential row. No schema change, but every test writes to the row that holds secrets.
3. Keep results in Redis with a 24 hour TTL. No schema change, shared by workers, lost on restart.

### D4. What "Test All" tests. Chosen: option 1

1. Credentials only. Cheaper, can miss billing or model level errors.
2. Every model of the group through the existing `/health` check. Real requests, one completion per model.
3. Credentials by default, with a "Also run model checks" option. Both, at the cost of more UI.

### D5. Turning a credential off. Chosen: option 1

1. Leave it out. The admin deletes a credential or blocks models in the All Models tab.
2. "Disable" blocks every model that uses the credential, through the existing model `blocked` flag, and "Enable" unblocks them. No schema change, but it also blocks models an admin blocked for other reasons unless the page remembers which ones it blocked.
3. Add an `enabled` column to the credential, and make the router skip deployments whose credential is disabled. Exact semantics, but a schema change and a routing change with their own tests.

### D6. Order between credentials of one provider. Chosen: option 2

1. Show each model's existing `order` read only in the detail view.
2. Let the admin edit `order` on the models from the detail view, using `/model/update`.

## Detailed Implementation Plan

The plan follows the chosen options: a Providers tab next to Add Model (D1-2), a `category` field in the catalog (D2-1), test results in `HangarLLM_HealthCheckTable` (D3-1), Test All on credentials only (D4-1), no disable action (D5-1), and editable `order` (D6-2).

### Step 1. Provider catalog

* Modify `hangarllm/proxy/public_endpoints/provider_create_fields.json` and its TypeScript type in `ui/hangarllm-dashboard/src/components/networking.tsx` to add `category` to every entry and an `Anthropic_Compatible` entry. Add a unit test that fails when an entry has no valid category. Create `ui/hangarllm-dashboard/src/app/(dashboard)/hooks/providers/useProviderCatalog.ts`, which joins provider fields, logos and categories and resolves a credential to a catalog entry through the lowercased provider id.
* Modify `CredentialModal.tsx` to take its provider list from the catalog. The `Providers` enum stays for its other users.
* Tests in `useProviderCatalog.test.ts`: every JSON entry lands in exactly one group, a credential stored as `Anthropic` resolves to the Anthropic entry, and a credential with `compatible` resolves to its own entry.

### Step 2. Credential tests

* Modify `hangarllm/proxy/health_endpoints/_health_endpoints.py` so `test_model_connection` accepts a credential name without a model, calls the provider's model list directly when the provider implements one, and otherwise uses `credential_info.test_model`. Add a batch form, `POST /health/test_connection/batch`, with a list of names, a limit of 5 parallel tests and a 20 second timeout per test.
* Store results in `HangarLLM_HealthCheckTable`. Add the column to all three schema copies (`schema.prisma`, `hangarllm/proxy/schema.prisma`, `hangarllm-proxy-extras/hangarllm_proxy_extras/schema.prisma`) with a schema-only migration, following the migration rules in `AGENTS.md`.
* Tests in `tests/unit/proxy/health_endpoints/`: a valid and an invalid key against a stubbed provider (the invalid one reports its 401), a provider without a model list and no test model (untested), a config defined credential, a non admin caller rejected, a batch that respects the parallel limit, and a key that never appears in the response or the captured logs.

### Step 3. Providers view

* Create `ui/hangarllm-dashboard/src/components/providers/ProvidersView.tsx` with groups, search, the "Configured only" toggle, cards and "Test All". Modify `ui/hangarllm-dashboard/src/app/(dashboard)/models-and-endpoints/page.tsx` to add a `providers` tab next to `add`.
* Card counts come from `GET /credentials`, the stored test results and `GET /v2/model/info`.
* Tests in `ProvidersView.test.tsx`: configured providers come first, the status line for healthy, failing, untested and not configured, Test All progress, and a failure shown on the card.

### Step 4. Provider detail

* Create `ui/hangarllm-dashboard/src/components/providers/ProviderDetail.tsx` with the credentials section (test, edit, delete, "From config" read only from `source`, "Add credential" that tests first) and the models section, where each model's `order` can be edited through `/model/update`.
* Modify `ui/hangarllm-dashboard/src/app/(dashboard)/models-and-endpoints/panels/AddModelPanel.tsx` to add `hangarllm_credential_name` to `PREFILL_URL_PARAMS`.
* Tests in `ProviderDetail.test.tsx`: a credential that fails its test is not saved unless "Save without testing" is chosen, config rows have no edit or delete, "Add model" opens the form with provider and credential filled in, and a changed `order` is sent to `/model/update`.

### Step 5. Compatible endpoints

* Create the two "Add compatible" forms in `ui/hangarllm-dashboard/src/components/providers/AddCompatibleModal.tsx`.
* Modify the credential create and update handlers in `hangarllm/proxy/credential_endpoints/endpoints.py` to reject a `compatible` credential with an empty `api_base`.
* Tests: the compatible endpoint shows as its own card and is absent from the OpenAI card, and create or update without `api_base` returns 400.

### Rollout

Steps 1 and 2 ship first and change no screen. Steps 3 to 5 add the Providers tab. The Add Model tab and its form stay as they are.
