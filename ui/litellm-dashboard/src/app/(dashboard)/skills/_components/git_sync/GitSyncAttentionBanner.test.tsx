import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { GitSource } from "@/components/claude_code_plugins/gitSyncTypes";

import GitSyncAttentionBanner from "./GitSyncAttentionBanner";

const base = {
  api_base_url: "https://api.github.com",
  repository_url: "https://github.com/acme/skills",
  branch: "main",
  skills_path: "skills",
  auth_type: "token",
  app_id: null,
  installation_id: null,
  has_credentials: true,
  scope: "access_group",
  access_group_id: null,
  access_group_name: null,
  publish_mode: "auto",
  remove_policy: "unpublish",
  auto_sync: true,
  poll_interval_seconds: 300,
  last_seen_sha: null,
  applied_sha: null,
  last_checked_at: null,
  last_synced_at: null,
  managed_skills: [],
  webhook_url: "",
  created_at: "2026-11-07T00:00:00Z",
  created_by: null,
  updated_at: "2026-11-07T00:00:00Z",
} as const;

const source = (id: string, repository: string, extra: Partial<GitSource>): GitSource => ({
  ...base,
  source_id: id,
  name: `acme/${repository}`,
  owner: "acme",
  repository,
  status: "healthy",
  status_message: null,
  quarantined_skills: [],
  ...extra,
});

describe("GitSyncAttentionBanner", () => {
  it("tells the admin which repositories need attention and opens the GitHub Sync tab", async () => {
    const onReview = vi.fn();
    render(
      <GitSyncAttentionBanner
        enabled
        onReview={onReview}
        sources={[
          source("1", "skills", { quarantined_skills: ["leaky", "broken"] }),
          source("2", "data", { status: "failed", status_message: "Bad credentials" }),
        ]}
      />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Sync of acme/data failed");
    expect(items[0]).toHaveTextContent("Bad credentials");
    expect(items[1]).toHaveTextContent("2 skills from acme/skills are quarantined");
    await userEvent.click(screen.getByRole("button", { name: "Review" }));
    expect(onReview).toHaveBeenCalledOnce();
  });

  it("summarises items beyond the first three", () => {
    const sources = ["a", "b", "c", "d", "e"].map((name) => source(name, name, { status: "pending_approval" }));
    render(<GitSyncAttentionBanner enabled onReview={vi.fn()} sources={sources} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByText("and 2 more items")).toBeInTheDocument();
  });

  it("stays hidden when nothing needs attention or the viewer is not an admin", () => {
    const { rerender } = render(
      <GitSyncAttentionBanner enabled onReview={vi.fn()} sources={[source("1", "skills", {})]} />,
    );
    expect(screen.queryByTestId("git-sync-attention")).not.toBeInTheDocument();
    rerender(
      <GitSyncAttentionBanner
        enabled={false}
        onReview={vi.fn()}
        sources={[source("1", "skills", { status: "failed" })]}
      />,
    );
    expect(screen.queryByTestId("git-sync-attention")).not.toBeInTheDocument();
  });
});
