import type { StatusTone } from "@/components/shared/table_cells/status_badge";
import type {
  GitSource,
  IssueSeverity,
  SkillAction,
  SourceStatus,
  SyncStatus,
} from "@/components/claude_code_plugins/gitSyncTypes";

export type AttentionKind = "failed" | "pending_approval" | "quarantined" | "warnings";

export interface AttentionItem {
  sourceId: string;
  sourceName: string;
  repository: string;
  kind: AttentionKind;
  count: number;
  message: string | null;
}

const KIND_ORDER: Record<AttentionKind, number> = { failed: 0, pending_approval: 1, quarantined: 2, warnings: 3 };

function sourceAttention(source: GitSource): AttentionItem[] {
  const base = {
    sourceId: source.source_id,
    sourceName: source.name,
    repository: `${source.owner}/${source.repository}`,
    message: source.status_message,
  };
  const items: AttentionItem[] = [];
  if (source.status === "failed") items.push({ ...base, kind: "failed", count: 1 });
  if (source.status === "pending_approval") items.push({ ...base, kind: "pending_approval", count: 1 });
  if (source.quarantined_skills.length > 0) {
    items.push({ ...base, kind: "quarantined", count: source.quarantined_skills.length });
  } else if (source.status === "warnings") {
    items.push({ ...base, kind: "warnings", count: 1 });
  }
  return items;
}

/** Everything an admin should look at, most urgent first. */
export function sourcesNeedingAttention(sources: readonly GitSource[]): AttentionItem[] {
  return sources.flatMap(sourceAttention).sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind]);
}

export function anySourceSyncing(sources: readonly GitSource[]): boolean {
  return sources.some((source) => source.status === "syncing");
}

export function managedSkillOwners(sources: readonly GitSource[]): ReadonlyMap<string, string> {
  return new Map(sources.flatMap((source) => source.managed_skills.map((skill) => [skill, source.name] as const)));
}

export const SOURCE_STATUS_TONE: Record<SourceStatus, StatusTone> = {
  never_synced: "neutral",
  syncing: "info",
  healthy: "success",
  warnings: "warning",
  failed: "error",
  pending_approval: "warning",
};

export const SYNC_STATUS_TONE: Record<SyncStatus, StatusTone> = {
  applied: "success",
  applied_with_warnings: "warning",
  no_changes: "neutral",
  pending_approval: "warning",
  rejected: "neutral",
  superseded: "neutral",
  failed: "error",
};

export const SKILL_ACTION_TONE: Record<SkillAction, StatusTone> = {
  created: "success",
  updated: "info",
  unchanged: "neutral",
  removed: "neutral",
  quarantined: "error",
  kept_previous: "warning",
};

export const SEVERITY_TONE: Record<IssueSeverity, StatusTone> = { info: "info", warning: "warning", error: "error" };

const ROLLBACK_TARGETS: ReadonlySet<SyncStatus> = new Set(["applied", "applied_with_warnings", "no_changes"]);

export function canRollBackTo(status: SyncStatus, commitSha: string | null, appliedSha: string | null): boolean {
  return ROLLBACK_TARGETS.has(status) && commitSha !== null && commitSha !== appliedSha;
}

export const shortSha = (sha: string | null | undefined): string => (sha ? sha.slice(0, 7) : "");

export const commitUrl = (repositoryUrl: string, sha: string): string => `${repositoryUrl}/commit/${sha}`;
