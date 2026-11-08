import type {
  GitConnection,
  GitRepository,
  GitSourceCreate,
  GitSourceUpdate,
  GitSource,
} from "@/components/claude_code_plugins/gitSyncTypes";

import { connectionComplete, type SettingsDraft } from "./formModel";

export type WizardStep = "connection" | "repository" | "done";

export const DEFAULT_SETTINGS: SettingsDraft = {
  name: "",
  skills_path: "",
  scope: "access_group",
  publish_mode: "auto",
  remove_policy: "unpublish",
  auto_sync: true,
  poll_interval_seconds: 300,
};

export interface PublicRepoDraft {
  owner: string;
  name: string;
}

export function publicRepository(draft: PublicRepoDraft): GitRepository {
  const owner = draft.owner.trim();
  const name = draft.name.trim();
  return { full_name: `${owner}/${name}`, owner, name, default_branch: "main", private: false };
}

export function canLeaveConnectionStep(connection: GitConnection, draft: PublicRepoDraft): boolean {
  if (!connectionComplete(connection)) return false;
  if (connection.auth_type !== "none") return true;
  return draft.owner.trim() !== "" && draft.name.trim() !== "";
}

/** Branch the wizard submits: the admin's pick, else the repo default when it exists, else the first branch. */
export function effectiveBranch(
  picked: string | null,
  repository: GitRepository | null,
  branches: readonly string[] | undefined,
): string {
  if (picked) return picked;
  const fallback = repository?.default_branch ?? "main";
  if (!branches || branches.length === 0 || branches.includes(fallback)) return fallback;
  return branches[0];
}

/** Keep a name the admin typed; otherwise follow the selected repository. */
export function nameForRepository(current: string, previous: GitRepository | null, next: GitRepository): string {
  return !current || current === previous?.full_name ? next.full_name : current;
}

export function createPayload(
  settings: SettingsDraft,
  connection: GitConnection,
  repository: GitRepository,
  branch: string,
): GitSourceCreate {
  return {
    ...settings,
    name: settings.name.trim() || repository.full_name,
    skills_path: settings.skills_path.trim(),
    connection,
    owner: repository.owner,
    repository: repository.name,
    branch,
    sync_now: true,
  };
}

export function settingsOf(source: GitSource): SettingsDraft {
  return {
    name: source.name,
    skills_path: source.skills_path,
    scope: source.scope,
    publish_mode: source.publish_mode,
    remove_policy: source.remove_policy,
    auto_sync: source.auto_sync,
    poll_interval_seconds: source.poll_interval_seconds,
  };
}

export function connectionOf(source: GitSource): GitConnection {
  return {
    auth_type: source.auth_type,
    api_base_url: source.api_base_url,
    token: "",
    app_id: source.app_id ?? "",
    installation_id: source.installation_id ?? "",
    private_key: "",
  };
}

export function updatePayload(
  source: GitSource,
  settings: SettingsDraft,
  branch: string,
  connection: GitConnection | null,
): GitSourceUpdate {
  const base: GitSourceUpdate = {
    ...settings,
    name: settings.name.trim() || source.name,
    skills_path: settings.skills_path.trim(),
    branch: branch.trim() || source.branch,
  };
  return connection ? { ...base, connection } : base;
}
