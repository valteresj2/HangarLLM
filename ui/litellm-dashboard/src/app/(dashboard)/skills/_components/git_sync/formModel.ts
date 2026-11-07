import {
  DEFAULT_GITHUB_API,
  type GitConnection,
  type SourceSettings,
} from "@/components/claude_code_plugins/gitSyncTypes";

export interface SettingsDraft extends SourceSettings {
  name: string;
  skills_path: string;
}

export const POLL_MINUTES = [1, 5, 15, 60] as const;

export const EMPTY_CONNECTION: GitConnection = {
  auth_type: "token",
  api_base_url: DEFAULT_GITHUB_API,
  token: "",
  app_id: "",
  installation_id: "",
  private_key: "",
};

const trimmed = (value: string | null | undefined): string => value?.trim() ?? "";

/** Request body for the API: only the credentials that belong to the chosen auth type. */
export function connectionPayload(connection: GitConnection): GitConnection {
  const base = {
    auth_type: connection.auth_type,
    api_base_url: trimmed(connection.api_base_url) || DEFAULT_GITHUB_API,
  };
  switch (connection.auth_type) {
    case "token":
      return { ...base, token: trimmed(connection.token) };
    case "github_app":
      return {
        ...base,
        app_id: trimmed(connection.app_id),
        installation_id: trimmed(connection.installation_id),
        private_key: connection.private_key ?? "",
      };
    case "none":
      return base;
  }
}

export function connectionComplete(connection: GitConnection): boolean {
  switch (connection.auth_type) {
    case "token":
      return trimmed(connection.token) !== "";
    case "github_app":
      return [connection.app_id, connection.installation_id, connection.private_key].every((v) => trimmed(v) !== "");
    case "none":
      return true;
  }
}

/** Poll interval shown in the select: the stored value when it is one of the options, else 5 minutes. */
export function pollMinutesOption(pollIntervalSeconds: number): number {
  const minutes = Math.round(pollIntervalSeconds / 60);
  return POLL_MINUTES.some((option) => option === minutes) ? minutes : 5;
}
