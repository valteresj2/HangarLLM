"use client";

import { useTranslation } from "react-i18next";

import { TabsContent, TabsTrigger } from "@/components/ui/tabs";

import GitSyncPanel from "./GitSyncPanel";
import type { useGitSources } from "./useGitSources";

export const GIT_SYNC_TAB = "git-sync";

export function GitSyncTabTrigger({ enabled }: { enabled: boolean }) {
  const { t } = useTranslation();
  if (!enabled) return null;
  return <TabsTrigger value={GIT_SYNC_TAB}>{t("skills.panel.tabs.gitSync")}</TabsTrigger>;
}

interface GitSyncTabContentProps {
  accessToken: string | null;
  enabled: boolean;
  gitSources: ReturnType<typeof useGitSources>;
  onSkillsChanged: () => Promise<void>;
}

export function GitSyncTabContent({ accessToken, enabled, gitSources, onSkillsChanged }: GitSyncTabContentProps) {
  if (!enabled || !accessToken) return null;
  const { query, sources, refresh } = gitSources;
  return (
    <TabsContent value={GIT_SYNC_TAB}>
      <GitSyncPanel
        accessToken={accessToken}
        sources={sources}
        isLoading={query.isLoading}
        isError={query.isError}
        onRetry={() => void query.refetch()}
        onChanged={() => void Promise.all([refresh(), onSkillsChanged()])}
      />
    </TabsContent>
  );
}
