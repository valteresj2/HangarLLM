import { describe, expect, it, vi } from "vitest";
import {
  buildOperationCatalog,
  createOpenApiCatalogCache,
  findOperations,
  isDeniedOperationPath,
  MAX_FOUND_OPERATIONS,
  resolveOperation,
} from "./openapiOperations";
import { openApiFixture } from "./openapiOperations.fixture";

const catalog = buildOperationCatalog(openApiFixture);

describe("operation deny list", () => {
  it.each([
    "/credentials",
    "/credentials/{credential_name}",
    "/credentials/migrate-encryption",
    "/hangarllm/salt_key/rotate",
    "/master_key/rotate",
    "/config_overrides/hashicorp_vault",
    "/key/leak-report",
    "/key/generate",
    "/key/{key}/regenerate",
    "/user/new",
    "/sso/key/generate",
    "/get/sso_settings",
    "/v2/login",
    "/session/logout",
    "/user/password/change",
    "/.well-known/openid-configuration",
    "/authorize",
    "/token",
    "/{mcp_server_name}/token",
    "/v1/realtime/client_secrets",
    "/skill-hub/git-sources/{source_id}/webhook-secret/rotate",
    "/v1/mcp/server/{server_id}/user-credential",
    "/scim/v2/Users",
    "/config/update",
    "/config/field/update",
  ])("denies %s", (path) => {
    expect(isDeniedOperationPath(path)).toBe(true);
  });

  it.each([
    "/team/update",
    "/guardrails/{guardrail_id}",
    "/model/new",
    "/key/info",
    "/user/daily/activity/aggregated",
    "/utils/token_counter",
    "/config/pass_through_endpoint",
    "/v1/messages/count_tokens",
  ])("allows %s", (path) => {
    expect(isDeniedOperationPath(path)).toBe(false);
  });
});

describe("findOperations", () => {
  it("ranks path and summary matches above passing mentions", () => {
    const paths = findOperations(catalog, "delete guardrail").map(({ method, path }) => `${method} ${path}`);
    expect(paths[0]).toBe("DELETE /guardrails/{guardrail_id}");
    expect(paths.indexOf("GET /model/info")).toBeGreaterThan(paths.indexOf("GET /guardrails/list"));
  });

  it("returns path and query parameters but not headers", () => {
    const [modelInfo] = findOperations(catalog, "model info");
    expect(modelInfo).toMatchObject({ method: "GET", path: "/model/info" });
    expect(modelInfo.parameters).toEqual([
      expect.objectContaining({
        name: "model_id",
        in: "query",
        required: false,
        schema: { type: "string", nullable: true },
      }),
    ]);
  });

  it("resolves request body references a few levels deep", () => {
    const [create] = findOperations(catalog, "create guardrail");
    expect(create.path).toBe("/guardrails");
    expect(create.request_body).toEqual({
      type: "object",
      required: ["guardrail"],
      properties: {
        guardrail: {
          type: "object",
          required: ["guardrail_name", "hangarllm_params"],
          properties: {
            guardrail_name: { type: "string" },
            hangarllm_params: {
              type: "object",
              properties: { mode: { type: "string", enum: ["pre_call", "post_call"] }, nested: { $ref: "Deep" } },
            },
          },
        },
      },
    });
  });

  it("never returns denied operations even when the spec lists them", () => {
    const paths = findOperations(catalog, "credentials leak report key").map(({ path }) => path);
    expect(paths).not.toContain("/credentials");
    expect(paths).not.toContain("/key/leak-report");
  });

  it("caps the number of results and ignores empty queries", () => {
    const many = buildOperationCatalog({
      paths: Object.fromEntries(
        Array.from({ length: 20 }, (_, index) => [`/team/${index}/info`, { get: { summary: "Team info" } }]),
      ),
    });
    expect(findOperations(many, "team info")).toHaveLength(MAX_FOUND_OPERATIONS);
    expect(findOperations(many, "?!")).toEqual([]);
  });
});

describe("resolveOperation", () => {
  it("fills and encodes path parameters of a known operation", () => {
    expect(
      resolveOperation(catalog, {
        method: "DELETE",
        path: "/guardrails/{guardrail_id}",
        path_params: [{ name: "guardrail_id", value: "pii/mask me" }],
      }),
    ).toEqual({ ok: true, method: "DELETE", path: "/guardrails/pii%2Fmask%20me", summary: "Delete Guardrail" });
  });

  it.each([
    { method: "POST", path: "/team/update" },
    { method: "PUT", path: "/guardrails/list" },
    { method: "GET", path: "/guardrails/pii" },
  ] as const)("rejects $method $path because the spec does not define it", (request) => {
    expect(resolveOperation(catalog, request)).toMatchObject({
      ok: false,
      message: expect.stringContaining("Unknown"),
    });
  });

  it.each([
    { method: "POST", path: "/key/leak-report" },
    { method: "GET", path: "/credentials" },
  ] as const)("rejects denied $path even though the spec defines it", (request) => {
    expect(resolveOperation(catalog, request)).toMatchObject({
      ok: false,
      message: expect.stringContaining("not available"),
    });
  });

  it.each([[[]], [[{ name: "guardrail_id", value: " " }]], [[{ name: "guardrail_id", value: ".." }]]])(
    "rejects missing or relative path parameters %j",
    (path_params) => {
      expect(resolveOperation(catalog, { method: "GET", path: "/guardrails/{guardrail_id}", path_params }).ok).toBe(
        false,
      );
    },
  );
});

describe("createOpenApiCatalogCache", () => {
  it("loads the spec once and retries after a failed load", async () => {
    const cache = createOpenApiCatalogCache();
    const fetchSpec = vi
      .fn<() => Promise<unknown>>()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue(openApiFixture);

    await expect(cache.load(fetchSpec)).rejects.toThrow("offline");
    const [first, second] = await Promise.all([cache.load(fetchSpec), cache.load(fetchSpec)]);

    expect(first).toBe(second);
    expect(first.operations.map(({ path }) => path)).toContain("/guardrails/list");
    expect(fetchSpec).toHaveBeenCalledTimes(2);
  });
});
