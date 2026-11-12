import { useMemo } from "react";
import type {
  CompatibleKind,
  CredentialItem,
  ProviderCategory,
  ProviderCreateInfo,
  ProviderCredentialFieldMetadata,
} from "@/components/networking";
import { getProviderLogoAndName } from "@/components/provider_info_helpers";
import { useProviderFields } from "./useProviderFields";

export type GridCategory = Exclude<ProviderCategory, "consumer_subscription">;

export const PROVIDER_CATEGORIES: readonly GridCategory[] = ["cloud_api", "enterprise_cloud", "self_hosted"];

export interface CatalogEntry {
  key: string;
  provider: string;
  displayName: string;
  routerId: string;
  category: ProviderCategory;
  logo: string;
  credentialFields: readonly ProviderCredentialFieldMetadata[];
  defaultModelPlaceholder: string | null;
  compatibleCredential: string | null;
}

const COMPATIBLE_PROVIDER: Readonly<Record<CompatibleKind, string>> = {
  openai: "OpenAI_Compatible",
  anthropic: "Anthropic_Compatible",
};

const logoFor = (info: ProviderCreateInfo): string =>
  getProviderLogoAndName(info.hangarllm_provider).logo || getProviderLogoAndName(info.provider).logo;

const toEntry = (info: ProviderCreateInfo): CatalogEntry => ({
  key: info.provider,
  provider: info.provider,
  displayName: info.provider_display_name,
  routerId: info.hangarllm_provider,
  category: info.category,
  logo: logoFor(info),
  credentialFields: info.credential_fields,
  defaultModelPlaceholder: info.default_model_placeholder ?? null,
  compatibleCredential: null,
});

export const buildCatalog = (fields: readonly ProviderCreateInfo[]): CatalogEntry[] => fields.map(toEntry);

export const entryForRouterId = (catalog: readonly CatalogEntry[], providerId: string): CatalogEntry | null => {
  const id = providerId.toLowerCase();
  const byRouterId = catalog.filter((entry) => entry.routerId === id && entry.compatibleCredential === null);
  return (
    byRouterId.find((entry) => entry.provider.toLowerCase() === id) ??
    byRouterId[0] ??
    catalog.find((entry) => entry.provider.toLowerCase() === id && entry.compatibleCredential === null) ??
    null
  );
};

const compatibleEntry = (
  catalog: readonly CatalogEntry[],
  credential: CredentialItem,
  kind: CompatibleKind,
): CatalogEntry => {
  const template = catalog.find((entry) => entry.provider === COMPATIBLE_PROVIDER[kind]);
  const vendor = entryForRouterId(catalog, kind);
  return {
    key: `compatible:${credential.credential_name}`,
    provider: credential.credential_info.custom_llm_provider ?? kind,
    displayName: credential.display_name || credential.credential_name,
    routerId: kind,
    category: "self_hosted",
    logo: template?.logo || vendor?.logo || "",
    credentialFields: template?.credentialFields ?? [],
    defaultModelPlaceholder: template?.defaultModelPlaceholder ?? null,
    compatibleCredential: credential.credential_name,
  };
};

export const resolveCredentialEntry = (
  catalog: readonly CatalogEntry[],
  credential: CredentialItem,
): CatalogEntry | null => {
  const kind = credential.credential_info?.compatible;
  if (kind !== undefined) {
    return compatibleEntry(catalog, credential, kind);
  }
  const stored = credential.credential_info?.custom_llm_provider;
  return stored ? entryForRouterId(catalog, stored) : null;
};

export const useProviderCatalog = () => {
  const { data, isLoading, error } = useProviderFields();
  const catalog = useMemo(() => buildCatalog(data ?? []), [data]);
  return { catalog, isLoading, error };
};
