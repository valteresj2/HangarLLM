// Mirrors litellm/hangar/skill_sync/types.py (Skills Hub Git Sync API contract).

export type GitAuthType = "none" | "token" | "github_app";
export type SyncScope = "all_keys" | "access_group";
export type PublishMode = "auto" | "approval";
export type RemovePolicy = "unpublish" | "keep";
export type SourceStatus = "never_synced" | "syncing" | "healthy" | "warnings" | "failed" | "pending_approval";
export type SyncTrigger = "create" | "manual" | "webhook" | "poll" | "approval" | "rollback";
export type SyncStatus =
  | "applied"
  | "applied_with_warnings"
  | "no_changes"
  | "pending_approval"
  | "rejected"
  | "superseded"
  | "failed";
export type IssueSeverity = "info" | "warning" | "error";
export type SkillAction = "created" | "updated" | "unchanged" | "removed" | "quarantined" | "kept_previous";

export const DEFAULT_GITHUB_API = "https://api.github.com";

export interface GitConnection {
  auth_type: GitAuthType;
  api_base_url: string;
  token?: string | null;
  app_id?: string | null;
  installation_id?: string | null;
  private_key?: string | null;
}

export interface GitRepository {
  full_name: string;
  owner: string;
  name: string;
  default_branch: string;
  private: boolean;
  description?: string | null;
}

export interface RepositoryList {
  repositories: GitRepository[];
  truncated: boolean;
}

export interface BranchQuery {
  connection: GitConnection;
  owner: string;
  repository: string;
}

export interface BranchList {
  branches: string[];
}

export interface SourceSettings {
  scope: SyncScope;
  publish_mode: PublishMode;
  remove_policy: RemovePolicy;
  auto_sync: boolean;
  poll_interval_seconds: number;
}

export interface GitSourceCreate extends SourceSettings {
  name: string;
  connection: GitConnection;
  owner: string;
  repository: string;
  branch: string;
  skills_path: string;
  sync_now: boolean;
}

export type GitSourceUpdate = Partial<SourceSettings> & {
  name?: string;
  connection?: GitConnection;
  branch?: string;
  skills_path?: string;
};

export interface SyncIssue {
  severity: IssueSeverity;
  code: string;
  message: string;
  file?: string | null;
}

export interface SkillOutcome {
  name: string | null;
  path: string;
  action: SkillAction;
  version?: string | null;
  digest?: string | null;
  issues: SyncIssue[];
}

export interface SyncSummary {
  created: number;
  updated: number;
  unchanged: number;
  removed: number;
  quarantined: number;
}

export interface SyncReport {
  commit_sha: string | null;
  applied: boolean;
  skills: SkillOutcome[];
  issues: SyncIssue[];
  summary: SyncSummary;
  error?: string | null;
}

export interface GitSync {
  sync_id: string;
  source_id: string;
  commit_sha: string | null;
  commit_url: string | null;
  trigger: SyncTrigger;
  status: SyncStatus;
  report: SyncReport;
  started_at: string;
  finished_at: string | null;
  triggered_by: string | null;
}

export interface GitSyncList {
  syncs: GitSync[];
}

export interface GitSource extends SourceSettings {
  source_id: string;
  name: string;
  api_base_url: string;
  owner: string;
  repository: string;
  repository_url: string;
  branch: string;
  skills_path: string;
  auth_type: GitAuthType;
  app_id: string | null;
  installation_id: string | null;
  has_credentials: boolean;
  access_group_id: string | null;
  access_group_name: string | null;
  status: SourceStatus;
  status_message: string | null;
  last_seen_sha: string | null;
  applied_sha: string | null;
  last_checked_at: string | null;
  last_synced_at: string | null;
  managed_skills: string[];
  quarantined_skills: string[];
  webhook_url: string;
  created_at: string;
  created_by: string | null;
  updated_at: string;
}

export interface GitSourceList {
  sources: GitSource[];
}

export interface WebhookSetup {
  url: string;
  secret: string;
  content_type: "application/json";
  events: string[];
}

export interface GitSourceCreated {
  source: GitSource;
  webhook: WebhookSetup;
  sync: GitSync | null;
}

export type SyncDecision = "approve" | "reject" | "rollback";
