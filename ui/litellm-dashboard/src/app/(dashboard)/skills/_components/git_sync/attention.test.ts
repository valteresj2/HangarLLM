import { describe, expect, it } from "vitest";

import type { GitSource } from "@/components/claude_code_plugins/gitSyncTypes";

import { anySourceSyncing, canRollBackTo, managedSkillOwners, sourcesNeedingAttention } from "./attention";

const source = (overrides: Partial<GitSource>): GitSource => ({
  source_id: "src-1",
  name: "acme/skills",
  api_base_url: "https://api.github.com",
  owner: "acme",
  repository: "skills",
  repository_url: "https://github.com/acme/skills",
  branch: "main",
  skills_path: "skills",
  auth_type: "token",
  app_id: null,
  installation_id: null,
  has_credentials: true,
  scope: "access_group",
  access_group_id: "ag-1",
  access_group_name: "git:acme/skills",
  publish_mode: "auto",
  remove_policy: "unpublish",
  auto_sync: true,
  poll_interval_seconds: 300,
  status: "healthy",
  status_message: null,
  last_seen_sha: "a".repeat(40),
  applied_sha: "a".repeat(40),
  last_checked_at: null,
  last_synced_at: null,
  managed_skills: [],
  quarantined_skills: [],
  webhook_url: "http://localhost:4000/skill-hub/git-sources/src-1/webhook",
  created_at: "2026-11-07T00:00:00Z",
  created_by: "admin",
  updated_at: "2026-11-07T00:00:00Z",
  ...overrides,
});

describe("sourcesNeedingAttention", () => {
  it("ignores healthy and never-synced sources", () => {
    expect(sourcesNeedingAttention([source({}), source({ source_id: "src-2", status: "never_synced" })])).toEqual([]);
  });

  it("reports quarantined skills with their count, even when the sync otherwise succeeded", () => {
    const items = sourcesNeedingAttention([
      source({ status: "warnings", quarantined_skills: ["leaky-skill", "bad-name"] }),
    ]);
    expect(items).toEqual([expect.objectContaining({ kind: "quarantined", count: 2, repository: "acme/skills" })]);
  });

  it("orders failures before approvals before quarantines before warnings", () => {
    const items = sourcesNeedingAttention([
      source({ source_id: "warn", status: "warnings" }),
      source({ source_id: "quarantine", quarantined_skills: ["x"] }),
      source({ source_id: "approval", status: "pending_approval" }),
      source({ source_id: "failed", status: "failed", status_message: "401 Bad credentials" }),
    ]);
    expect(items.map((item) => item.kind)).toEqual(["failed", "pending_approval", "quarantined", "warnings"]);
    expect(items[0].message).toBe("401 Bad credentials");
  });
});

describe("managedSkillOwners", () => {
  it("maps every managed skill to the display name of its source", () => {
    const owners = managedSkillOwners([
      source({ name: "Platform skills", managed_skills: ["deploy", "review"] }),
      source({ source_id: "src-2", name: "Data skills", managed_skills: ["sql"] }),
    ]);
    expect(Object.fromEntries(owners)).toEqual({
      deploy: "Platform skills",
      review: "Platform skills",
      sql: "Data skills",
    });
  });
});

describe("anySourceSyncing", () => {
  it("is true only while a source is syncing", () => {
    expect(anySourceSyncing([source({}), source({ status: "syncing" })])).toBe(true);
    expect(anySourceSyncing([source({ status: "failed" })])).toBe(false);
  });
});

describe("canRollBackTo", () => {
  const applied = "b".repeat(40);
  it("allows rolling back to an earlier successful commit", () => {
    expect(canRollBackTo("applied", "c".repeat(40), applied)).toBe(true);
    expect(canRollBackTo("no_changes", "c".repeat(40), applied)).toBe(true);
  });

  it("refuses the current commit, unsuccessful syncs and syncs without a commit", () => {
    expect(canRollBackTo("applied", applied, applied)).toBe(false);
    expect(canRollBackTo("failed", "c".repeat(40), applied)).toBe(false);
    expect(canRollBackTo("pending_approval", "c".repeat(40), applied)).toBe(false);
    expect(canRollBackTo("applied", null, applied)).toBe(false);
  });
});
