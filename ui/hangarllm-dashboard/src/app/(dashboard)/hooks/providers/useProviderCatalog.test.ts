import { describe, expect, it } from "vitest";
import type { CredentialItem, ProviderCreateInfo } from "@/components/networking";
import { groupProviderCards, buildProviderCards } from "@/components/providers/providerCards";
import { buildCatalog, resolveCredentialEntry } from "./useProviderCatalog";

const field = (provider: string, display: string, routerId: string, category: ProviderCreateInfo["category"]) => ({
  provider,
  provider_display_name: display,
  hangarllm_provider: routerId,
  category,
  credential_fields: [],
});

const FIELDS: ProviderCreateInfo[] = [
  field("OpenAI_Compatible", "OpenAI-Compatible Endpoints", "openai", "self_hosted"),
  field("OpenAI", "OpenAI", "openai", "cloud_api"),
  field("Anthropic_Compatible", "Anthropic-Compatible Endpoints", "anthropic", "self_hosted"),
  field("Anthropic", "Anthropic", "anthropic", "cloud_api"),
  field("Google_AI_Studio", "Google AI Studio", "gemini", "cloud_api"),
  field("Azure_AI_Studio", "Azure AI Foundry", "azure_ai", "enterprise_cloud"),
  field("Ollama", "Ollama", "ollama", "self_hosted"),
];

const catalog = buildCatalog(FIELDS);

const credential = (name: string, info: CredentialItem["credential_info"], displayName?: string): CredentialItem => ({
  credential_name: name,
  display_name: displayName ?? null,
  credential_values: {},
  credential_info: info,
});

describe("provider catalog", () => {
  it("puts every catalog entry in exactly one group, the one its category names", () => {
    const groups = groupProviderCards(buildProviderCards(catalog, [], []), { search: "", configuredOnly: false });

    const groupsHolding = (provider: string) =>
      groups.filter((group) => group.cards.some((card) => card.entry.provider === provider)).map((g) => g.category);
    const placements = FIELDS.map((info) => groupsHolding(info.provider));
    expect(placements).toEqual(FIELDS.map((info) => [info.category]));
  });

  it("resolves a credential stored in display casing to the vendor entry, not its compatible twin", () => {
    expect(resolveCredentialEntry(catalog, credential("a", { custom_llm_provider: "Anthropic" }))?.key).toBe(
      "Anthropic",
    );
    expect(resolveCredentialEntry(catalog, credential("o", { custom_llm_provider: "openai" }))?.key).toBe("OpenAI");
  });

  it("resolves a router id that differs from the catalog key, and a catalog key that is no router id", () => {
    expect(resolveCredentialEntry(catalog, credential("g", { custom_llm_provider: "gemini" }))?.key).toBe(
      "Google_AI_Studio",
    );
    expect(resolveCredentialEntry(catalog, credential("z", { custom_llm_provider: "Azure_AI_Studio" }))?.key).toBe(
      "Azure_AI_Studio",
    );
  });

  it("returns no entry for a provider the catalog does not know", () => {
    expect(resolveCredentialEntry(catalog, credential("x", { custom_llm_provider: "Nowhere" }))).toBeNull();
  });

  it("resolves a compatible credential to its own self-hosted entry named after its display name", () => {
    const entry = resolveCredentialEntry(
      catalog,
      credential("lab", { custom_llm_provider: "Anthropic", compatible: "anthropic" }, "Lab gateway"),
    );

    const expected = {
      displayName: "Lab gateway",
      routerId: "anthropic",
      category: "self_hosted",
      compatibleCredential: "lab",
    };
    expect(entry).toMatchObject(expected);
    expect(entry?.key).not.toBe("Anthropic");
    expect(entry?.key).not.toBe("Anthropic_Compatible");
  });
});
