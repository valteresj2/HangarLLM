import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders, testQueryClient } from "@/../tests/test-utils";
import { createGitSkillSource, discoverGitBranches, discoverGitRepositories } from "@/components/networking";
import type { GitSourceCreated } from "@/components/claude_code_plugins/gitSyncTypes";

import ConnectRepositoryWizard from "./ConnectRepositoryWizard";

vi.mock("@/components/networking", () => ({
  discoverGitRepositories: vi.fn(),
  discoverGitBranches: vi.fn(),
  createGitSkillSource: vi.fn(),
}));

const mockRepos = vi.mocked(discoverGitRepositories);
const mockBranches = vi.mocked(discoverGitBranches);
const mockCreate = vi.mocked(createGitSkillSource);

const created: GitSourceCreated = {
  source: {
    source_id: "src-1",
    name: "acme/skills",
    api_base_url: "https://api.github.com",
    owner: "acme",
    repository: "skills",
    repository_url: "https://github.com/acme/skills",
    branch: "trunk",
    skills_path: "",
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
    status: "warnings",
    status_message: null,
    last_seen_sha: "f".repeat(40),
    applied_sha: "f".repeat(40),
    last_checked_at: null,
    last_synced_at: null,
    managed_skills: ["deploy"],
    quarantined_skills: ["leaky"],
    webhook_url: "http://localhost:4000/skill-hub/git-sources/src-1/webhook",
    created_at: "2026-11-07T00:00:00Z",
    created_by: "admin",
    updated_at: "2026-11-07T00:00:00Z",
  },
  webhook: {
    url: "http://localhost:4000/skill-hub/git-sources/src-1/webhook",
    secret: "whsec-123",
    content_type: "application/json",
    events: ["push"],
  },
  sync: {
    sync_id: "sync-1",
    source_id: "src-1",
    commit_sha: "f".repeat(40),
    commit_url: null,
    trigger: "create",
    status: "applied_with_warnings",
    report: {
      commit_sha: "f".repeat(40),
      applied: true,
      skills: [],
      issues: [],
      summary: { created: 1, updated: 0, unchanged: 0, removed: 0, quarantined: 1 },
    },
    started_at: "2026-11-07T00:00:00Z",
    finished_at: "2026-11-07T00:00:01Z",
    triggered_by: "admin",
  },
};

const renderWizard = () =>
  renderWithProviders(<ConnectRepositoryWizard accessToken="sk-admin" open onClose={vi.fn()} onCreated={vi.fn()} />);

describe("ConnectRepositoryWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testQueryClient.clear();
    mockRepos.mockResolvedValue({
      repositories: [
        { full_name: "acme/skills", owner: "acme", name: "skills", default_branch: "trunk", private: true },
        { full_name: "acme/website", owner: "acme", name: "website", default_branch: "main", private: false },
      ],
      truncated: false,
    });
    mockBranches.mockResolvedValue({ branches: ["dev", "trunk"] });
    mockCreate.mockResolvedValue(created);
  });

  it("walks from credentials to repository to webhook setup and sends the chosen settings", async () => {
    const user = userEvent.setup();
    renderWizard();
    expect(screen.getByTestId("wizard-step")).toHaveTextContent("Connection");
    const loadButton = screen.getByRole("button", { name: "Load repositories" });
    expect(loadButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Access token"), { target: { value: "github_pat_abc" } });
    await user.click(loadButton);

    expect(await screen.findByTestId("wizard-step")).toHaveTextContent("Repository and rules");
    expect(mockRepos).toHaveBeenCalledWith("sk-admin", {
      auth_type: "token",
      api_base_url: "https://api.github.com",
      token: "github_pat_abc",
    });

    await user.type(screen.getByPlaceholderText("Search repositories"), "skil");
    expect(screen.queryByRole("option", { name: /acme\/website/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: /acme\/skills/ }));
    await screen.findByText("trunk", { selector: "[data-slot=select-value]" });
    expect(mockBranches).toHaveBeenCalledWith(
      "sk-admin",
      expect.objectContaining({ owner: "acme", repository: "skills" }),
    );

    fireEvent.change(screen.getByLabelText("Skills folder"), { target: { value: "skills" } });
    await user.click(screen.getByRole("radio", { name: /^Require admin approval/ }));
    await user.click(screen.getByRole("button", { name: "Connect and sync" }));

    expect(await screen.findByTestId("webhook-secret")).toHaveTextContent("whsec-123");
    expect(screen.getByTestId("wizard-step")).toHaveTextContent("Webhook");
    expect(screen.getByText("Applied with warnings")).toBeInTheDocument();
    expect(mockCreate).toHaveBeenCalledWith(
      "sk-admin",
      expect.objectContaining({
        name: "acme/skills",
        owner: "acme",
        repository: "skills",
        branch: "trunk",
        skills_path: "skills",
        publish_mode: "approval",
        scope: "access_group",
        connection: { auth_type: "token", api_base_url: "https://api.github.com", token: "github_pat_abc" },
      }),
    );
  });

  it("goes straight to the repository step for a public repository without listing repositories", async () => {
    const user = userEvent.setup();
    renderWizard();
    await user.click(screen.getByRole("radio", { name: /^Public repository/ }));
    fireEvent.change(screen.getByLabelText("Owner"), { target: { value: "anthropics" } });
    fireEvent.change(screen.getByLabelText("Repository"), { target: { value: "skills" } });
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("anthropics/skills")).toBeInTheDocument();
    expect(mockRepos).not.toHaveBeenCalled();
    expect(mockBranches).toHaveBeenCalledWith("sk-admin", {
      connection: { auth_type: "none", api_base_url: "https://api.github.com" },
      owner: "anthropics",
      repository: "skills",
    });
  });

  it("stays on the connection step when GitHub rejects the credentials", async () => {
    const user = userEvent.setup();
    mockRepos.mockRejectedValue(new Error("401"));
    renderWizard();
    fireEvent.change(screen.getByLabelText("Access token"), { target: { value: "bad" } });
    await user.click(screen.getByRole("button", { name: "Load repositories" }));
    await vi.waitFor(() => expect(mockRepos).toHaveBeenCalledOnce());
    expect(screen.getByTestId("wizard-step")).toHaveTextContent("Connection");
    expect(mockCreate).not.toHaveBeenCalled();
  });
});
