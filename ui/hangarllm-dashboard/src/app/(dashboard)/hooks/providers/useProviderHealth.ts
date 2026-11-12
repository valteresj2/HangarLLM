import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import {
  credentialTestLatestCall,
  latestHealthChecksCall,
  type CredentialTestResult,
  type CredentialTestResults,
} from "@/components/networking";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { createQueryKeys } from "../common/queryKeysFactory";

const credentialTestKeys = createQueryKeys("credentialTests");
const modelHealthKeys = createQueryKeys("latestModelHealth");

const EMPTY_RESULTS: CredentialTestResults = { results: [] };

export const useCredentialTestResults = (): ReadonlyMap<string, CredentialTestResult> => {
  const { accessToken } = useAuthorized();
  const { data } = useQuery<CredentialTestResults>({
    queryKey: credentialTestKeys.list({}),
    queryFn: async () => await credentialTestLatestCall(accessToken!),
    enabled: Boolean(accessToken),
  });
  return useMemo(
    () =>
      new Map(
        (data ?? EMPTY_RESULTS).results.flatMap((result) =>
          result.credential_name === null ? [] : [[result.credential_name, result] as const],
        ),
      ),
    [data],
  );
};

export const useRecordCredentialTests = (): ((results: readonly CredentialTestResult[]) => void) => {
  const queryClient = useQueryClient();
  return useCallback(
    (results) => {
      const named = new Set(results.map((result) => result.credential_name));
      queryClient.setQueryData<CredentialTestResults>(credentialTestKeys.list({}), (current) => ({
        results: [
          ...(current ?? EMPTY_RESULTS).results.filter((result) => !named.has(result.credential_name)),
          ...results,
        ],
      }));
    },
    [queryClient],
  );
};

interface LatestModelHealth {
  latest_health_checks?: Record<string, { status?: string | null } | null>;
}

export const useLatestModelHealth = (): ReadonlyMap<string, string> => {
  const { accessToken } = useAuthorized();
  const { data } = useQuery<LatestModelHealth>({
    queryKey: modelHealthKeys.list({}),
    queryFn: async () => await latestHealthChecksCall(accessToken!),
    enabled: Boolean(accessToken),
  });
  return useMemo(
    () =>
      new Map(
        Object.entries(data?.latest_health_checks ?? {}).flatMap(([modelId, check]) =>
          check?.status ? [[modelId, check.status] as const] : [],
        ),
      ),
    [data],
  );
};
