import { describe, expect, it } from "vitest";

import type { GitRepository } from "@/components/claude_code_plugins/gitSyncTypes";

import { EMPTY_CONNECTION, connectionComplete, connectionPayload } from "./formModel";
import {
  DEFAULT_SETTINGS,
  canLeaveConnectionStep,
  createPayload,
  effectiveBranch,
  nameForRepository,
  publicRepository,
} from "./wizardModel";

const repo = (full_name: string, default_branch = "main"): GitRepository => {
  const [owner, name] = full_name.split("/");
  return { full_name, owner, name, default_branch, private: true };
};

describe("connectionPayload", () => {
  it("sends only the credentials of the chosen auth type", () => {
    const filled = {
      ...EMPTY_CONNECTION,
      token: " ghp_x ",
      app_id: "1",
      installation_id: "2",
      private_key: "PEM",
    };
    expect(connectionPayload({ ...filled, auth_type: "token" })).toEqual({
      auth_type: "token",
      api_base_url: "https://api.github.com",
      token: "ghp_x",
    });
    expect(connectionPayload({ ...filled, auth_type: "github_app" })).toEqual({
      auth_type: "github_app",
      api_base_url: "https://api.github.com",
      app_id: "1",
      installation_id: "2",
      private_key: "PEM",
    });
    expect(connectionPayload({ ...filled, auth_type: "none" })).toEqual({
      auth_type: "none",
      api_base_url: "https://api.github.com",
    });
  });

  it("falls back to github.com when the enterprise URL is left blank", () => {
    expect(connectionPayload({ ...EMPTY_CONNECTION, api_base_url: "  " }).api_base_url).toBe("https://api.github.com");
  });
});

describe("connectionComplete / canLeaveConnectionStep", () => {
  it("requires every GitHub App field", () => {
    const app = { ...EMPTY_CONNECTION, auth_type: "github_app" as const, app_id: "1", installation_id: "2" };
    expect(connectionComplete(app)).toBe(false);
    expect(connectionComplete({ ...app, private_key: "PEM" })).toBe(true);
  });

  it("requires owner and repository for a public repository", () => {
    const none = { ...EMPTY_CONNECTION, auth_type: "none" as const };
    expect(canLeaveConnectionStep(none, { owner: "anthropics", name: " " })).toBe(false);
    expect(canLeaveConnectionStep(none, { owner: "anthropics", name: "skills" })).toBe(true);
    expect(publicRepository({ owner: " anthropics ", name: "skills " }).full_name).toBe("anthropics/skills");
  });
});

describe("effectiveBranch", () => {
  it("prefers the admin's pick, then the default branch, then the first listed branch", () => {
    expect(effectiveBranch("release", repo("acme/skills"), ["main", "release"])).toBe("release");
    expect(effectiveBranch(null, repo("acme/skills", "trunk"), ["dev", "trunk"])).toBe("trunk");
    expect(effectiveBranch(null, repo("acme/skills", "trunk"), ["dev", "prod"])).toBe("dev");
    expect(effectiveBranch(null, repo("acme/skills", "trunk"), undefined)).toBe("trunk");
  });
});

describe("nameForRepository", () => {
  it("follows the selection until the admin types a name", () => {
    expect(nameForRepository("", null, repo("acme/a"))).toBe("acme/a");
    expect(nameForRepository("acme/a", repo("acme/a"), repo("acme/b"))).toBe("acme/b");
    expect(nameForRepository("Platform skills", repo("acme/a"), repo("acme/b"))).toBe("Platform skills");
  });
});

describe("createPayload", () => {
  it("builds the create request with trimmed fields and an initial sync", () => {
    const body = createPayload(
      { ...DEFAULT_SETTINGS, name: " ", skills_path: " skills/ ", publish_mode: "approval" },
      { auth_type: "token", api_base_url: "https://api.github.com", token: "t" },
      repo("acme/skills"),
      "main",
    );
    expect(body).toMatchObject({
      name: "acme/skills",
      owner: "acme",
      repository: "skills",
      branch: "main",
      skills_path: "skills/",
      publish_mode: "approval",
      scope: "access_group",
      sync_now: true,
    });
  });
});
