import { skipToken, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { listGitSkillSources } from "@/components/networking";
import type { GitSource } from "@/components/claude_code_plugins/gitSyncTypes";

import { anySourceSyncing } from "./attention";

export const GIT_SOURCES_POLL_MS = 15_000;
const NO_SOURCES: readonly GitSource[] = [];
export const gitSourcesKey = (accessToken: string | null) => ["skill-git-sources", accessToken] as const;

export function useGitSources(accessToken: string | null, enabled: boolean) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: gitSourcesKey(accessToken),
    queryFn: accessToken && enabled ? () => listGitSkillSources(accessToken) : skipToken,
    refetchInterval: (current) => (anySourceSyncing(current.state.data?.sources ?? []) ? GIT_SOURCES_POLL_MS : false),
  });
  const refresh = useCallback(
    () => queryClient.invalidateQueries({ queryKey: gitSourcesKey(accessToken), refetchType: "all" }),
    [queryClient, accessToken],
  );
  const sources: readonly GitSource[] = query.data?.sources ?? NO_SOURCES;
  return { query, sources, refresh };
}
