"use client";

import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { GitSource } from "@/components/claude_code_plugins/gitSyncTypes";

import { sourcesNeedingAttention, type AttentionItem } from "./attention";

const MAX_LINES = 3;

function useAttentionLine() {
  const { t } = useTranslation();
  return (item: AttentionItem): string => {
    switch (item.kind) {
      case "failed":
        return t("skills.gitSync.banner.failed", { repository: item.repository });
      case "pending_approval":
        return t("skills.gitSync.banner.pending_approval", { repository: item.repository });
      case "quarantined":
        return t("skills.gitSync.banner.quarantined", { count: item.count, repository: item.repository });
      case "warnings":
        return t("skills.gitSync.banner.warnings", { repository: item.repository });
    }
  };
}

interface GitSyncAttentionBannerProps {
  enabled: boolean;
  sources: readonly GitSource[];
  onReview: () => void;
}

export default function GitSyncAttentionBanner({ enabled, sources, onReview }: GitSyncAttentionBannerProps) {
  const { t } = useTranslation();
  const line = useAttentionLine();
  const items = sourcesNeedingAttention(sources);
  if (!enabled || items.length === 0) return null;
  const hidden = items.length - MAX_LINES;
  return (
    <Alert className="mb-4 border-warning/40 bg-warning/5" data-testid="git-sync-attention">
      <AlertTriangle className="text-warning" />
      <AlertTitle>{t("skills.gitSync.banner.title")}</AlertTitle>
      <AlertDescription>
        <ul className="list-disc pl-4">
          {items.slice(0, MAX_LINES).map((item) => (
            <li key={`${item.sourceId}-${item.kind}`}>
              {line(item)}
              {item.message && item.kind === "failed" && (
                <span className="text-muted-foreground"> ({item.message})</span>
              )}
            </li>
          ))}
        </ul>
        {hidden > 0 && <p className="text-muted-foreground">{t("skills.gitSync.banner.more", { count: hidden })}</p>}
      </AlertDescription>
      <AlertAction>
        <Button size="sm" variant="outline" onClick={onReview}>
          {t("skills.gitSync.banner.review")}
        </Button>
      </AlertAction>
    </Alert>
  );
}
