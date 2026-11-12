"use client";

import { useMemo, useState } from "react";
import { parseAsString, useQueryState } from "nuqs";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { Plus, Search } from "lucide-react";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { useCredentials } from "@/app/(dashboard)/hooks/credentials/useCredentials";
import { useAllModelDeployments } from "@/app/(dashboard)/hooks/models/useModels";
import { useProviderCatalog } from "@/app/(dashboard)/hooks/providers/useProviderCatalog";
import {
  useCredentialTestResults,
  useRecordCredentialTests,
} from "@/app/(dashboard)/hooks/providers/useProviderHealth";
import { credentialTestBatchCall, type CompatibleKind, type ProviderCategory } from "@/components/networking";
import { Logo } from "@/components/molecules/logo/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { extractProxyErrorMessage } from "@/lib/http/client";
import { cn } from "@/lib/cva.config";
import { toast } from "@/lib/toast";
import AddCompatibleModal from "./AddCompatibleModal";
import ProviderDetail from "./ProviderDetail";
import {
  buildProviderCards,
  groupProviderCards,
  providerStatus,
  type ProviderCard,
  type ProviderStatus,
  type TestResultsByName,
} from "./providerCards";

type CardProgress = "queued" | "testing";

const GROUP_LABELS = {
  cloud_api: "modelsAndEndpoints.providersView.groups.cloudApi",
  enterprise_cloud: "modelsAndEndpoints.providersView.groups.enterpriseCloud",
  self_hosted: "modelsAndEndpoints.providersView.groups.selfHosted",
} as const satisfies Record<ProviderCategory, string>;

export const statusText = (t: TFunction, status: ProviderStatus): string => {
  if (status.kind === "not_configured") return t("modelsAndEndpoints.providersView.status.notConfigured");
  if (status.kind === "not_tested") return t("modelsAndEndpoints.providersView.status.notTested");
  const parts = [
    status.healthy > 0 ? t("modelsAndEndpoints.providersView.status.healthy", { count: status.healthy }) : null,
    status.failing > 0
      ? t("modelsAndEndpoints.providersView.status.failing", { count: status.failing, reason: status.failure })
      : null,
    status.untested > 0 ? t("modelsAndEndpoints.providersView.status.untested", { count: status.untested }) : null,
  ];
  return parts.filter((part): part is string => part !== null).join(" · ");
};

const statusTone = (status: ProviderStatus): string => {
  if (status.kind !== "counts") return "bg-muted-foreground/40";
  return status.failing > 0 ? "bg-destructive" : "bg-success";
};

interface ProviderCardTileProps {
  card: ProviderCard;
  results: TestResultsByName;
  progress: CardProgress | undefined;
  onOpen: () => void;
}

function ProviderCardTile({ card, results, progress, onOpen }: ProviderCardTileProps) {
  const { t } = useTranslation();
  const status = providerStatus(card, results);
  return (
    <li aria-label={card.entry.displayName}>
      <button
        type="button"
        onClick={onOpen}
        className={cn(
          "flex h-full w-full items-start gap-3 rounded-lg border bg-card p-4 text-left text-card-foreground shadow-xs transition-colors",
          "hover:border-primary/50 hover:bg-accent/40 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
          card.credentials.length === 0 && "opacity-75",
        )}
      >
        <span className="flex size-10 shrink-0 items-center justify-center rounded-md border bg-background">
          <Logo src={card.entry.logo} label={card.entry.displayName} className="size-6" />
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="truncate font-medium">{card.entry.displayName}</span>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {progress === undefined ? (
              <span aria-hidden className={cn("size-2 shrink-0 rounded-full", statusTone(status))} />
            ) : (
              <Spinner className="size-3" />
            )}
            <span className={cn(status.kind === "counts" && status.failing > 0 && "text-destructive")}>
              {progress === undefined
                ? statusText(t, status)
                : t(`modelsAndEndpoints.providersView.progress.${progress}`)}
            </span>
          </span>
          <span className="text-xs text-muted-foreground">
            {t("modelsAndEndpoints.providersView.models", { count: card.models.length })}
          </span>
        </span>
      </button>
    </li>
  );
}

export default function ProvidersView() {
  const { t } = useTranslation();
  const { accessToken } = useAuthorized();
  const { catalog, isLoading, error } = useProviderCatalog();
  const { data: credentialsResponse } = useCredentials();
  const { data: deployments } = useAllModelDeployments();
  const results = useCredentialTestResults();
  const recordTests = useRecordCredentialTests();
  const [detailKey, setDetailKey] = useQueryState("provider_detail", parseAsString);
  const [search, setSearch] = useState("");
  const [configuredOnly, setConfiguredOnly] = useState(false);
  const [compatibleKind, setCompatibleKind] = useState<CompatibleKind | null>(null);
  const [progress, setProgress] = useState<ReadonlyMap<string, CardProgress>>(new Map());

  const credentials = credentialsResponse?.credentials;
  const cards = useMemo(
    () => buildProviderCards(catalog, credentials ?? [], deployments ?? []),
    [catalog, credentials, deployments],
  );
  const groups = useMemo(
    () => groupProviderCards(cards, { search, configuredOnly }).filter((group) => group.cards.length > 0),
    [cards, search, configuredOnly],
  );

  const setCardProgress = (keys: readonly string[], next: CardProgress | null) =>
    setProgress((current) => {
      const updated = new Map(current);
      keys.forEach((key) => (next === null ? updated.delete(key) : updated.set(key, next)));
      return updated;
    });

  const testGroup = async (category: ProviderCategory) => {
    const targets =
      groupProviderCards(cards, { search: "", configuredOnly: true }).find((group) => group.category === category)
        ?.cards ?? [];
    setCardProgress(
      targets.map((card) => card.entry.key),
      "queued",
    );
    for (const card of targets) {
      setCardProgress([card.entry.key], "testing");
      try {
        const response = await credentialTestBatchCall(
          accessToken ?? "",
          card.credentials.map((credential) => credential.credential_name),
        );
        recordTests(response.results);
      } catch (testError) {
        toast.error(extractProxyErrorMessage(testError));
      }
      setCardProgress([card.entry.key], null);
    }
  };

  const detailCard = detailKey === null ? undefined : cards.find((card) => card.entry.key === detailKey);
  if (detailCard !== undefined) {
    return <ProviderDetail card={detailCard} results={results} onBack={() => void setDetailKey(null)} />;
  }

  if (error) {
    return <p className="text-sm text-destructive">{t("modelsAndEndpoints.providersView.loadError")}</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-sm">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            aria-label={t("modelsAndEndpoints.providersView.search")}
            placeholder={t("modelsAndEndpoints.providersView.search")}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="pl-8"
          />
        </div>
        <div className="flex items-center gap-2">
          <Switch id="providers-configured-only" checked={configuredOnly} onCheckedChange={setConfiguredOnly} />
          <Label htmlFor="providers-configured-only" className="text-sm">
            {t("modelsAndEndpoints.providersView.configuredOnly")}
          </Label>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setCompatibleKind("openai")}>
            <Plus className="size-4" />
            {t("modelsAndEndpoints.providersView.addOpenaiCompatible")}
          </Button>
          <Button variant="outline" onClick={() => setCompatibleKind("anthropic")}>
            <Plus className="size-4" />
            {t("modelsAndEndpoints.providersView.addAnthropicCompatible")}
          </Button>
        </div>
      </div>

      {isLoading && <Spinner className="size-5" />}
      {!isLoading && groups.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("modelsAndEndpoints.providersView.empty")}</p>
      )}

      {groups.map((group) => {
        const headingId = `providers-group-${group.category}`;
        const configured = cards.some((card) => card.entry.category === group.category && card.credentials.length > 0);
        const testing = group.cards.some((card) => progress.has(card.entry.key));
        return (
          <section key={group.category} aria-labelledby={headingId} className="flex flex-col gap-3">
            <div className="flex items-center justify-between gap-3">
              <h3 id={headingId} className="text-base font-semibold">
                {t(GROUP_LABELS[group.category])}
                <span className="ml-2 text-sm font-normal text-muted-foreground">{group.cards.length}</span>
              </h3>
              <Button
                variant="outline"
                size="sm"
                disabled={!configured || testing}
                onClick={() => void testGroup(group.category)}
              >
                {testing && <Spinner className="size-3" />}
                {t("modelsAndEndpoints.providersView.testAll")}
              </Button>
            </div>
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {group.cards.map((card) => (
                <ProviderCardTile
                  key={card.entry.key}
                  card={card}
                  results={results}
                  progress={progress.get(card.entry.key)}
                  onOpen={() => void setDetailKey(card.entry.key, { history: "push" })}
                />
              ))}
            </ul>
          </section>
        );
      })}

      {compatibleKind !== null && (
        <AddCompatibleModal kind={compatibleKind} open onClose={() => setCompatibleKind(null)} />
      )}
    </div>
  );
}
