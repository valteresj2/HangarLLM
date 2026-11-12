import {
  PROVIDER_CATEGORIES,
  entryForRouterId,
  resolveCredentialEntry,
  type CatalogEntry,
} from "@/app/(dashboard)/hooks/providers/useProviderCatalog";
import type { CredentialItem, CredentialTestResult, ProviderCategory } from "@/components/networking";

export interface ProviderModel {
  model_name?: string | null;
  hangarllm_params?: {
    model?: string | null;
    custom_llm_provider?: string | null;
    hangarllm_credential_name?: string | null;
    order?: number | null;
  } | null;
  model_info?: { id?: string | null; db_model?: boolean | null } | null;
}

export interface ProviderCard {
  entry: CatalogEntry;
  credentials: CredentialItem[];
  models: ProviderModel[];
}

export interface ProviderGroup {
  category: ProviderCategory;
  cards: ProviderCard[];
}

export type ProviderStatus =
  | { kind: "not_configured" }
  | { kind: "not_tested" }
  | { kind: "counts"; healthy: number; failing: number; untested: number; failure: string | null };

export type TestResultsByName = ReadonlyMap<string, CredentialTestResult>;

const modelProviderId = (model: ProviderModel): string | null => {
  const params = model.hangarllm_params;
  if (params?.custom_llm_provider) return params.custom_llm_provider;
  const prefix = params?.model?.split("/");
  return prefix !== undefined && prefix.length > 1 ? prefix[0] : null;
};

const modelEntry = (
  catalog: readonly CatalogEntry[],
  credentialEntries: ReadonlyMap<string, CatalogEntry | null>,
  model: ProviderModel,
): CatalogEntry | null => {
  const credentialName = model.hangarllm_params?.hangarllm_credential_name;
  if (credentialName && credentialEntries.has(credentialName)) {
    return credentialEntries.get(credentialName) ?? null;
  }
  const providerId = modelProviderId(model);
  return providerId === null ? null : entryForRouterId(catalog, providerId);
};

export const buildProviderCards = (
  catalog: readonly CatalogEntry[],
  credentials: readonly CredentialItem[],
  models: readonly ProviderModel[],
): ProviderCard[] => {
  const credentialEntries = new Map(
    credentials.map((credential) => [credential.credential_name, resolveCredentialEntry(catalog, credential)]),
  );
  const compatibleEntries = [...credentialEntries.values()].filter(
    (entry): entry is CatalogEntry => entry !== null && entry.compatibleCredential !== null,
  );
  const modelKeys = models.map((model) => modelEntry(catalog, credentialEntries, model)?.key);
  return [...catalog, ...compatibleEntries].map((entry) => ({
    entry,
    credentials: credentials.filter(
      (credential) => credentialEntries.get(credential.credential_name)?.key === entry.key,
    ),
    models: models.filter((_model, index) => modelKeys[index] === entry.key),
  }));
};

const failureReason = (result: CredentialTestResult): string => {
  if (result.http_status !== null) return String(result.http_status);
  return /time(d)?\s?out/i.test(result.error ?? "") ? "timeout" : "network";
};

const latestFirst = (left: CredentialTestResult, right: CredentialTestResult): number =>
  (right.checked_at ?? "").localeCompare(left.checked_at ?? "");

export const providerStatus = (card: ProviderCard, results: TestResultsByName): ProviderStatus => {
  if (card.credentials.length === 0) return { kind: "not_configured" };
  const cardResults = card.credentials
    .map((credential) => results.get(credential.credential_name))
    .filter((result): result is CredentialTestResult => result !== undefined);
  const healthy = cardResults.filter((result) => result.status === "healthy").length;
  const failures = cardResults.filter((result) => result.status === "failing").sort(latestFirst);
  if (healthy === 0 && failures.length === 0) return { kind: "not_tested" };
  return {
    kind: "counts",
    healthy,
    failing: failures.length,
    untested: card.credentials.length - healthy - failures.length,
    failure: failures.length > 0 ? failureReason(failures[0]) : null,
  };
};

const byConfiguredThenName = (left: ProviderCard, right: ProviderCard): number => {
  const configured = Number(right.credentials.length > 0) - Number(left.credentials.length > 0);
  return configured !== 0 ? configured : left.entry.displayName.localeCompare(right.entry.displayName, "en");
};

const matchesSearch = (card: ProviderCard, search: string): boolean => {
  const query = search.trim().toLowerCase();
  return (
    query === "" ||
    card.entry.displayName.toLowerCase().includes(query) ||
    card.entry.routerId.toLowerCase().includes(query)
  );
};

export const groupProviderCards = (
  cards: readonly ProviderCard[],
  options: { search: string; configuredOnly: boolean },
): ProviderGroup[] =>
  PROVIDER_CATEGORIES.map((category) => ({
    category,
    cards: cards
      .filter((card) => card.entry.category === category)
      .filter((card) => !options.configuredOnly || card.credentials.length > 0)
      .filter((card) => matchesSearch(card, options.search))
      .sort(byConfiguredThenName),
  }));
