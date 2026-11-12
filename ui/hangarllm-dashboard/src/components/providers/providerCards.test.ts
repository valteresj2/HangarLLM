import { describe, expect, it } from "vitest";
import { buildCatalog } from "@/app/(dashboard)/hooks/providers/useProviderCatalog";
import type { CredentialItem, CredentialTestResult, ProviderCreateInfo } from "@/components/networking";
import { buildProviderCards, groupProviderCards, providerStatus, type ProviderModel } from "./providerCards";

const field = (provider: string, display: string, routerId: string, category: ProviderCreateInfo["category"]) => ({
  provider,
  provider_display_name: display,
  hangarllm_provider: routerId,
  category,
  credential_fields: [],
});

const catalog = buildCatalog([
  field("OpenAI", "OpenAI", "openai", "cloud_api"),
  field("Anthropic", "Anthropic", "anthropic", "cloud_api"),
  field("Cohere", "Cohere", "cohere", "cloud_api"),
  field("Mistral", "Mistral AI", "mistral", "cloud_api"),
  field("OpenAI_Compatible", "OpenAI-Compatible Endpoints", "openai", "self_hosted"),
]);

const credential = (name: string, info: CredentialItem["credential_info"], displayName?: string): CredentialItem => ({
  credential_name: name,
  display_name: displayName ?? null,
  credential_values: {},
  credential_info: info,
});

const model = (id: string, params: NonNullable<ProviderModel["hangarllm_params"]>): ProviderModel => ({
  model_name: id,
  hangarllm_params: params,
  model_info: { id },
});

const result = (name: string, overrides: Partial<CredentialTestResult>): CredentialTestResult => ({
  credential_name: name,
  status: "healthy",
  kind: "model_list",
  http_status: null,
  error: null,
  latency_ms: 10,
  checked_at: "2026-11-12T10:00:00Z",
  ...overrides,
});

const CREDENTIALS = [
  credential("openai-prod", { custom_llm_provider: "OpenAI" }),
  credential("mistral-main", { custom_llm_provider: "Mistral" }),
  credential("lab", { custom_llm_provider: "OpenAI", compatible: "openai" }, "Lab vLLM"),
];

const cardFor = (key: string, models: ProviderModel[] = []) =>
  buildProviderCards(catalog, CREDENTIALS, models).find((card) => card.entry.key === key)!;

describe("buildProviderCards", () => {
  it("keeps a compatible credential and its models out of the vendor card", () => {
    const models = [
      model("m1", { model: "openai/gpt-4o", hangarllm_credential_name: "openai-prod" }),
      model("m2", { model: "openai/gpt-4o-mini" }),
      model("m3", { model: "openai/qwen", hangarllm_credential_name: "lab" }),
    ];
    const cards = buildProviderCards(catalog, CREDENTIALS, models);
    const openai = cards.find((card) => card.entry.key === "OpenAI")!;
    const lab = cards.find((card) => card.entry.compatibleCredential === "lab")!;

    expect(openai.credentials.map((c) => c.credential_name)).toEqual(["openai-prod"]);
    expect(openai.models.map((m) => m.model_info?.id)).toEqual(["m1", "m2"]);
    expect(lab.entry.displayName).toBe("Lab vLLM");
    expect(lab.entry.category).toBe("self_hosted");
    expect(lab.credentials.map((c) => c.credential_name)).toEqual(["lab"]);
    expect(lab.models.map((m) => m.model_info?.id)).toEqual(["m3"]);
  });

  it("counts a model toward its credential's provider over its model prefix", () => {
    const card = cardFor("Mistral", [
      model("m1", { model: "openai/mistral-large", hangarllm_credential_name: "mistral-main" }),
    ]);
    expect(card.models).toHaveLength(1);
  });

  it("counts a model by its custom_llm_provider when the model name has no prefix", () => {
    const card = cardFor("Anthropic", [model("m1", { model: "claude-x", custom_llm_provider: "anthropic" })]);
    expect(card.models).toHaveLength(1);
  });
});

describe("groupProviderCards", () => {
  const cards = buildProviderCards(catalog, CREDENTIALS, []);
  const names = (options: { search: string; configuredOnly: boolean }, index = 0) =>
    groupProviderCards(cards, options)[index].cards.map((card) => card.entry.displayName);

  it("lists configured providers first, then the rest by display name", () => {
    expect(names({ search: "", configuredOnly: false })).toEqual(["Mistral AI", "OpenAI", "Anthropic", "Cohere"]);
  });

  it("hides providers without credentials when Configured only is on", () => {
    expect(names({ search: "", configuredOnly: true })).toEqual(["Mistral AI", "OpenAI"]);
  });

  it("filters by display name or router id, ignoring case", () => {
    expect(names({ search: "COH", configuredOnly: false })).toEqual(["Cohere"]);
    expect(names({ search: "mistral", configuredOnly: false })).toEqual(["Mistral AI"]);
    expect(names({ search: "lab", configuredOnly: false }, 2)).toEqual(["Lab vLLM"]);
  });
});

describe("providerStatus", () => {
  const threeCredentials = [
    credential("a", { custom_llm_provider: "OpenAI" }),
    credential("b", { custom_llm_provider: "OpenAI" }),
    credential("c", { custom_llm_provider: "OpenAI" }),
  ];
  const card = buildProviderCards(catalog, threeCredentials, []).find((c) => c.entry.key === "OpenAI")!;

  it("reports a provider without credentials as not configured", () => {
    expect(providerStatus(cardFor("Cohere"), new Map())).toEqual({ kind: "not_configured" });
  });

  it("reports not tested while no credential has a pass or a failure", () => {
    expect(providerStatus(card, new Map([["a", result("a", { status: "untested" })]]))).toEqual({
      kind: "not_tested",
    });
  });

  it("counts healthy, failing and untested credentials and names the latest failure's status", () => {
    const results = new Map([
      ["a", result("a", {})],
      ["b", result("b", { status: "failing", http_status: 500, checked_at: "2026-11-12T09:00:00Z" })],
      ["c", result("c", { status: "failing", http_status: 401, checked_at: "2026-11-12T11:00:00Z" })],
    ]);
    const expected = { kind: "counts", healthy: 1, failing: 2, untested: 0, failure: "401" };
    expect(providerStatus(card, results)).toEqual(expected);
  });

  it("names a failure without an HTTP status as timeout or network", () => {
    const timeout = new Map([["a", result("a", { status: "failing", error: "Request timed out after 20s" })]]);
    const network = new Map([["a", result("a", { status: "failing", error: "Connection refused" })]]);
    expect(providerStatus(card, timeout)).toMatchObject({ failure: "timeout", untested: 2 });
    expect(providerStatus(card, network)).toMatchObject({ failure: "network" });
  });
});
