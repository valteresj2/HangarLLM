import { zodFunction } from "openai/helpers/zod";
import { z } from "zod";
import { apiClient } from "@/components/networking";
import i18n from "@/i18n/i18n";
import { ApiError } from "@/lib/http/client";
import type { components } from "@/lib/http/schema";
import {
  createOpenApiCatalogCache,
  findOperations,
  GENERIC_METHODS,
  resolveOperation,
  type GenericMethod,
  type OpenApiCatalogCache,
} from "./openapiOperations";
import { generatedKey, projectToolResult, type ResultKind } from "./toolResults";
import {
  buildUsageChart,
  usageChartRequestSchema,
  usageChartSource,
  type UsageChart,
  type UsageChartSource,
} from "./usageChart";

export interface LiteAdminAction {
  id: string;
  name: string;
  title: string;
  arguments: Record<string, unknown>;
  destructive: boolean;
}

export type ActionResult = { status: "completed"; key?: string } | { status: "unknown"; message: string };

export type AriaAccess =
  | { mode: "admin" }
  | { mode: "usage"; scope: { type: "global" } | { type: "user"; userId: string } };

export interface OperationContext {
  access: AriaAccess;
  accessToken: string;
  signal: AbortSignal;
  assertCurrent: () => void;
  beforeTool: () => void;
  confirm: (action: LiteAdminAction) => Promise<boolean>;
  onResult: (action: LiteAdminAction, result: ActionResult) => void;
  onChart: (chart: UsageChart) => void;
  openApiCache?: OpenApiCatalogCache;
}

type OperationMode = "read" | "write" | "delete";
const METHOD_MODES: Record<GenericMethod, OperationMode> = {
  GET: "read",
  HEAD: "read",
  POST: "write",
  PUT: "write",
  PATCH: "write",
  DELETE: "delete",
};

type Schemas = components["schemas"];
const text = z.string().min(1).max(200);
const hash = z.string().regex(/^[a-f0-9]{64}$/i, "Use the key hash from a lookup, not a raw API key.");
const optional = <Schema extends z.ZodType<unknown>>(schema: Schema) => schema.nullable();
type NullsStripped<T> = { [K in keyof T]: Exclude<T[K], null> };
const stripNulls = <T extends Record<string, unknown>>(args: T): NullsStripped<T> =>
  Object.fromEntries(
    Object.entries(args).map(([key, value]) => [key, value === null ? undefined : value]),
  ) as NullsStripped<T>;
const optionalText = optional(text);
const amount = optional(z.number().finite().nonnegative());
const limit = optional(z.number().int().nonnegative());
const models = optional(z.array(text).max(50));
const page = z.number().int().min(1);
const pageSize = z.number().int().min(1).max(50);
const limits = { max_budget: amount, budget_duration: optionalText, rpm_limit: limit, tpm_limit: limit };
const keyFields = {
  key_alias: optionalText,
  team_id: optionalText,
  user_id: optionalText,
  models,
  ...limits,
  budget_id: optionalText,
  duration: optionalText,
};
const teamFields = { team_alias: optionalText, organization_id: optionalText, models, ...limits };
const userFields = {
  user_email: optional(z.email().max(200)),
  user_alias: optionalText,
  user_role: optional(z.enum(["proxy_admin", "proxy_admin_viewer", "internal_user", "internal_user_viewer"])),
  models,
  ...limits,
};
const object = <Shape extends z.ZodRawShape>(shape: Shape) => z.strictObject(shape);
const dated = <Shape extends z.ZodRawShape>(shape: Shape) =>
  object({ start_date: z.iso.date(), end_date: z.iso.date(), ...shape }).refine((value: Record<string, unknown>) => {
    if (typeof value.start_date !== "string" || typeof value.end_date !== "string") return false;
    const days = (Date.parse(value.end_date) - Date.parse(value.start_date)) / 86_400_000;
    return days >= 0 && days <= 366;
  }, "Choose an ordered date range of at most 366 days.");

const keysListFields = {
  page,
  page_size: pageSize,
  search: optionalText,
  team_id: optionalText,
  user_id: optionalText,
};
const teamsListFields = { page, page_size: pageSize, search: optionalText, organization_id: optionalText };
const teamMemberAddFields = {
  team_id: text,
  member: object({ user_id: text, role: z.enum(["admin", "user"]) }),
  max_budget_in_team: amount,
  budget_duration: optionalText,
};
const teamMemberUpdateFields = {
  team_id: text,
  user_id: text,
  role: optional(z.enum(["admin", "user"])),
  max_budget_in_team: amount,
  budget_duration: optionalText,
  rpm_limit: limit,
  tpm_limit: limit,
};
const spendReportFields = {
  group_by: z.enum(["team", "customer", "api_key"]),
  api_key: optional(hash),
  team_id: optionalText,
  internal_user_id: optionalText,
  customer_id: optionalText,
};
const requestLogsFields = {
  page,
  page_size: pageSize,
  request_id: optionalText,
  team_id: optionalText,
  user_id: optionalText,
  model: optionalText,
  status_filter: optional(z.enum(["success", "failure"])),
};
const namedValue = object({ name: text, value: z.string().max(2_000) });
const callOperationFields = {
  method: z.enum(GENERIC_METHODS),
  path: z.string().min(1).max(300),
  path_params: optional(z.array(namedValue).max(10)),
  query: optional(z.array(namedValue).max(30)),
  body: optional(z.string().max(20_000)),
};

function parseJsonBody(body: string | undefined): { ok: true; value: unknown } | { ok: false } {
  if (body === undefined || !body.trim()) return { ok: true, value: undefined };
  try {
    return { ok: true, value: JSON.parse(body) };
  } catch {
    return { ok: false };
  }
}

export function createLiteAdminOperations(context: OperationContext) {
  const usageSources = new Map<string, UsageChartSource>();
  const active = () => {
    context.signal.throwIfAborted();
    context.assertCurrent();
  };
  const auth = { accessToken: context.accessToken, signal: context.signal };
  const chartDefinition = {
    name: "render_usage_chart",
    description:
      "Show one chart with the answer using the source_id of a successful usage lookup in this turn. Choose daily_spend for spend over time, model_spend or provider_spend for cost comparisons, daily_requests or daily_tokens for trends, or token_breakdown for input/output/cache analysis. Values come directly from that lookup. Follow with a short explanation, not a duplicate table. A later chart replaces the earlier chart for this answer. Read-only.",
    parameters: usageChartRequestSchema,
    function: (rawArgs: unknown) => {
      active();
      context.beforeTool();
      const args = usageChartRequestSchema.parse(rawArgs);
      const source = usageSources.get(args.source_id);
      if (!source) return { success: false, message: "Fetch usage first and use the source_id from that result." };
      const chart = buildUsageChart(source, args.view);
      if (!chart)
        return { success: false, message: "No recorded data is available for this chart. Explain that in text." };
      context.onChart(chart);
      return { success: true, chart };
    },
  };
  const renderChart = zodFunction(chartDefinition);
  const perform = async (
    { name, title, mode, kind }: { name: string; title: string; mode: OperationMode; kind: ResultKind },
    args: Record<string, unknown>,
    actionArguments: Record<string, unknown>,
    execute: () => Promise<unknown>,
  ) => {
    const action: LiteAdminAction | undefined =
      mode === "read"
        ? undefined
        : { id: crypto.randomUUID(), name, title, arguments: actionArguments, destructive: mode === "delete" };
    if (action) {
      const approved = await context.confirm(action);
      active();
      if (!approved) throw new Error("Action cancelled. No change was sent.");
    }
    const outcome = await Promise.resolve()
      .then(() => {
        active();
        return execute();
      })
      .then(
        (value) => ({ ok: true, value }) as const,
        (error: unknown) => ({ ok: false, error }) as const,
      );
    active();
    if (!outcome.ok) {
      if (action) {
        const result: ActionResult = {
          status: "unknown",
          message: i18n.t("aria.actions.unverified"),
        };
        context.onResult(action, result);
        throw new Error(result.message);
      }
      return {
        operation: name,
        success: false,
        status: outcome.error instanceof ApiError ? outcome.error.status : undefined,
        message: "The gateway could not complete this lookup.",
      };
    }
    const key = name === "key_create" || name === "user_create" ? generatedKey(outcome.value) : undefined;
    if (action) context.onResult(action, { status: "completed", ...(key ? { key } : {}) });
    const result = projectToolResult(kind, outcome.value, [context.accessToken, ...(key ? [key] : [])]);
    let reportScope: "Gateway usage" | "All teams" | "All tags" = "Gateway usage";
    if (name === "get_team_usage_data") reportScope = "All teams";
    if (name === "get_tag_usage_data") reportScope = "All tags";
    const source = kind === "usage" ? usageChartSource(result, args, context.access, reportScope) : undefined;
    const sourceId = source ? crypto.randomUUID() : undefined;
    if (source && sourceId) usageSources.set(sourceId, source);
    return {
      operation: name,
      success: true,
      result,
      ...(sourceId ? { source_id: sourceId } : {}),
    };
  };
  const operation =
    (mode: OperationMode, kind: ResultKind, extraArguments?: Record<string, unknown>) =>
    <Schema extends z.ZodType<Record<string, unknown>>>(
      name: string,
      title: string,
      schema: Schema,
      execute: (args: NullsStripped<z.output<Schema>>) => Promise<unknown>,
    ) => {
      const definition = {
        name,
        description: `${title}. Null means omitted or unchanged. ${mode === "read" ? "Read-only." : "Requires the administrator to review and confirm the change."}`,
        parameters: schema,
        function: async (rawArgs: unknown) => {
          const args = stripNulls(rawArgs as z.output<Schema>);
          active();
          context.beforeTool();
          const actionArguments = {
            ...Object.fromEntries(Object.entries(args).filter(([, value]) => value !== undefined)),
            ...extraArguments,
          };
          return perform({ name, title, mode, kind }, args, actionArguments, () =>
            execute({ ...args, ...extraArguments } as NullsStripped<z.output<Schema>>),
          );
        },
      };
      return zodFunction(definition);
    };
  const openApiCache = context.openApiCache ?? createOpenApiCatalogCache();
  const loadCatalog = () =>
    openApiCache
      .load(() => apiClient.get<unknown>("/openapi.json", auth))
      .then(
        (catalog) => ({ ok: true, catalog }) as const,
        () => ({ ok: false }) as const,
      );
  const catalogUnavailable = (name: string) => ({
    operation: name,
    success: false,
    message: "The gateway API description could not be loaded.",
  });
  const findOperation = zodFunction({
    name: "find_operation",
    description:
      "Search the gateway's management API for tasks the dedicated tools do not cover. Returns a few matching operations with their method, path template, parameters and request body schema. Read-only.",
    parameters: object({ query: text }),
    function: async (rawArgs: unknown) => {
      const { query } = z.object({ query: text }).parse(rawArgs);
      active();
      context.beforeTool();
      const loaded = await loadCatalog();
      active();
      if (!loaded.ok) return catalogUnavailable("find_operation");
      return { operation: "find_operation", success: true, result: findOperations(loaded.catalog, query) };
    },
  });
  const callOperation = zodFunction({
    name: "call_operation",
    description:
      "Call one gateway API operation returned by find_operation, using its exact method and path template. path_params fill the {placeholders}, query holds query parameters, and body is the JSON request body as text. GET and HEAD are read-only. POST, PUT, PATCH and DELETE require the administrator to review and confirm the exact request.",
    parameters: object(callOperationFields),
    function: async (rawArgs: unknown) => {
      const args = stripNulls(z.object(callOperationFields).parse(rawArgs));
      active();
      context.beforeTool();
      const loaded = await loadCatalog();
      active();
      if (!loaded.ok) return catalogUnavailable("call_operation");
      const resolved = resolveOperation(loaded.catalog, args);
      if (!resolved.ok) return { operation: "call_operation", success: false, message: resolved.message };
      const body = parseJsonBody(args.body);
      if (!body.ok) return { operation: "call_operation", success: false, message: "body must be valid JSON text." };
      const mode = METHOD_MODES[resolved.method];
      if (mode === "read" && body.value !== undefined) {
        return { operation: "call_operation", success: false, message: "GET and HEAD requests take no body." };
      }
      const pairs = args.query ?? [];
      const query = Object.fromEntries(
        [...new Set(pairs.map(({ name }) => name))].map((name) => {
          const values = pairs.filter((pair) => pair.name === name).map(({ value }) => value);
          return [name, values.length === 1 ? values[0] : values];
        }),
      );
      const hasQuery = Object.keys(query).length > 0;
      const actionArguments = {
        method: resolved.method,
        path: resolved.path,
        ...(hasQuery ? { query } : {}),
        ...(body.value !== undefined ? { body: body.value } : {}),
      };
      const title = `${resolved.method} ${resolved.path}${resolved.summary ? ` (${resolved.summary})` : ""}`;
      return perform({ name: "call_operation", title, mode, kind: "generic" }, args, actionArguments, () =>
        apiClient.request<unknown>(resolved.method, resolved.path, {
          ...auth,
          ...(hasQuery ? { query } : {}),
          ...(body.value !== undefined ? { body: body.value } : {}),
        }),
      );
    },
  });

  if (context.access.mode === "usage" && context.access.scope.type === "user") {
    const userId = context.access.scope.userId;
    return [
      renderChart,
      operation("read", "usage")(
        "get_usage_data",
        "View your dated usage totals, daily trends, and top models, providers and keys with prompt, completion, cache-read and cache-creation token counts when available. Do not add cache counts to total_tokens",
        dated({}),
        (a) => {
          if (!userId.trim()) throw new Error("A signed-in user is required to query usage.");
          return apiClient.get<unknown>("/user/daily/activity/aggregated", {
            ...auth,
            query: { ...a, user_id: userId, api_key_limit: 20 },
          });
        },
      ),
    ];
  }

  const usageOperations = [
    renderChart,
    operation("read", "usage")(
      "get_usage_data",
      "View dated global or user usage totals, daily trends, and top models, providers and keys with prompt, completion, cache-read and cache-creation token counts when available. Do not add cache counts to total_tokens",
      dated({ user_id: optionalText }),
      (a) => apiClient.get<unknown>("/user/daily/activity/aggregated", { ...auth, query: { ...a, api_key_limit: 20 } }),
    ),
    operation("read", "usage")(
      "get_team_usage_data",
      "View dated usage by team, including model and provider breakdowns with prompt, completion, cache-read and cache-creation token counts when available. Do not add cache counts to total_tokens. Omit team_ids for all teams",
      dated({ team_ids: optionalText }),
      (a) => apiClient.get<unknown>("/team/daily/activity/aggregated", { ...auth, query: { ...a, api_key_limit: 20 } }),
    ),
    operation("read", "usage")(
      "get_tag_usage_data",
      "View dated usage by tag, including model and provider breakdowns with prompt, completion, cache-read and cache-creation token counts when available. Do not add cache counts to total_tokens. Omit tags for all tags",
      dated({ tags: optionalText }),
      (a) => apiClient.get<unknown>("/tag/daily/activity/aggregated", { ...auth, query: { ...a, api_key_limit: 20 } }),
    ),
  ];
  if (context.access.mode === "usage") return usageOperations;

  return [
    operation("read", "key")("keys_list", "List virtual keys", object(keysListFields), (a) =>
      apiClient.get<unknown>("/key/list", {
        ...auth,
        query: {
          page: a.page,
          size: a.page_size,
          search: a.search,
          team_id: a.team_id,
          user_id: a.user_id,
          return_full_object: true,
        },
      }),
    ),
    operation("read", "key")("key_info", "View a virtual key", object({ key: hash }), (a) =>
      apiClient.get<unknown>("/key/info", { ...auth, query: a }),
    ),
    operation("write", "key")("key_create", "Create a virtual key", object(keyFields), (a) =>
      apiClient.post<unknown>("/key/generate", { ...auth, body: a satisfies Partial<Schemas["GenerateKeyRequest"]> }),
    ),
    operation("write", "key")("key_update", "Update a virtual key", object({ key: hash, ...keyFields }), (a) =>
      apiClient.post<unknown>("/key/update", { ...auth, body: a satisfies Partial<Schemas["UpdateKeyRequest"]> }),
    ),
    operation("write", "key", { team_id: null })(
      "key_detach_from_team",
      "Remove a virtual key from its team without deleting the key",
      object({ key: hash }),
      (a) =>
        apiClient.post<unknown>("/key/update", { ...auth, body: a satisfies Partial<Schemas["UpdateKeyRequest"]> }),
    ),
    operation("delete", "key")(
      "key_delete",
      "Delete virtual keys",
      object({ keys: z.array(hash).min(1).max(20) }),
      (a) => apiClient.post<unknown>("/key/delete", { ...auth, body: a satisfies Schemas["KeyRequest"] }),
    ),
    operation("write", "key")("key_block", "Block a virtual key", object({ key: hash }), (a) =>
      apiClient.post<unknown>("/key/block", { ...auth, body: a satisfies Schemas["BlockKeyRequest"] }),
    ),
    operation("write", "key")("key_unblock", "Unblock a virtual key", object({ key: hash }), (a) =>
      apiClient.post<unknown>("/key/unblock", { ...auth, body: a satisfies Schemas["BlockKeyRequest"] }),
    ),
    operation("read", "team")("teams_list", "List teams", object(teamsListFields), (a) =>
      apiClient.get<unknown>("/v2/team/list", { ...auth, query: a }),
    ),
    operation("read", "team")("team_info", "View a team and its members", object({ team_id: text }), (a) =>
      apiClient.get<unknown>("/team/info", { ...auth, query: { ...a, key_limit: 20 } }),
    ),
    operation("write", "team")("team_create", "Create a team", object(teamFields), (a) =>
      apiClient.post<unknown>("/team/new", { ...auth, body: a satisfies Partial<Schemas["NewTeamRequest"]> }),
    ),
    operation("write", "team")("team_update", "Update a team", object({ team_id: text, ...teamFields }), (a) =>
      apiClient.post<unknown>("/team/update", { ...auth, body: a satisfies Schemas["UpdateTeamRequest"] }),
    ),
    operation("delete", "team")(
      "team_delete",
      "Delete teams",
      object({ team_ids: z.array(text).min(1).max(20) }),
      (a) => apiClient.post<unknown>("/team/delete", { ...auth, body: a satisfies Schemas["DeleteTeamRequest"] }),
    ),
    operation("write", "team")("team_member_add", "Add a team member", object(teamMemberAddFields), (a) =>
      apiClient.post<unknown>("/team/member_add", { ...auth, body: a satisfies Schemas["TeamMemberAddRequest"] }),
    ),
    operation("write", "team")("team_member_update", "Update a team member", object(teamMemberUpdateFields), (a) =>
      apiClient.post<unknown>("/team/member_update", {
        ...auth,
        body: a satisfies Schemas["TeamMemberUpdateRequest"],
      }),
    ),
    operation("delete", "team")(
      "team_member_delete",
      "Remove a team member",
      object({ team_id: text, user_id: text }),
      (a) =>
        apiClient.post<unknown>("/team/member_delete", {
          ...auth,
          body: a satisfies Schemas["TeamMemberDeleteRequest"],
        }),
    ),
    operation("read", "user")(
      "users_list",
      "List users",
      object({ page, page_size: pageSize, search: optionalText }),
      (a) => apiClient.get<unknown>("/user/list", { ...auth, query: a }),
    ),
    operation("read", "user")("user_info", "View a user", object({ user_id: text }), (a) =>
      apiClient.get<unknown>("/v2/user/info", { ...auth, query: a }),
    ),
    operation("write", "user", { auto_create_key: false })(
      "user_create",
      "Create a user without a key",
      object({ user_id: optionalText, ...userFields }),
      (a) => apiClient.post<unknown>("/user/new", { ...auth, body: a satisfies Partial<Schemas["NewUserRequest"]> }),
    ),
    operation("write", "user")("user_update", "Update a user", object({ user_id: text, ...userFields }), (a) =>
      apiClient.post<unknown>("/user/update", { ...auth, body: a satisfies Partial<Schemas["UpdateUserRequest"]> }),
    ),
    operation("delete", "user")(
      "user_delete",
      "Delete users",
      object({ user_ids: z.array(text).min(1).max(20) }),
      (a) => apiClient.post<unknown>("/user/delete", { ...auth, body: a satisfies Schemas["DeleteUserRequest"] }),
    ),
    operation("read", "budget")(
      "budgets_list",
      "List budgets",
      object({ page, page_size: pageSize, search: optionalText }),
      (a) =>
        apiClient.get<unknown>("/management/v1/budgets", {
          ...auth,
          query: { page: a.page, page_size: a.page_size, q: a.search },
        }),
    ),
    operation("read", "budget")("budget_info", "View budgets", object({ budgets: z.array(text).min(1).max(20) }), (a) =>
      apiClient.post<unknown>("/budget/info", { ...auth, body: a satisfies Schemas["BudgetRequest"] }),
    ),
    operation("write", "budget")(
      "budget_create",
      "Create a budget",
      object({ budget_id: optionalText, ...limits }),
      (a) => apiClient.post<unknown>("/budget/new", { ...auth, body: a satisfies Schemas["BudgetNewRequest"] }),
    ),
    operation("write", "budget")("budget_update", "Update a budget", object({ budget_id: text, ...limits }), (a) =>
      apiClient.post<unknown>("/budget/update", { ...auth, body: a satisfies Schemas["BudgetNewRequest"] }),
    ),
    operation("delete", "budget")("budget_delete", "Delete a budget", object({ id: text }), (a) =>
      apiClient.post<unknown>("/budget/delete", { ...auth, body: a satisfies Schemas["BudgetDeleteRequest"] }),
    ),
    operation("read", "spend")(
      "spend_report",
      "View spend by date and group (requires an enterprise license)",
      dated(spendReportFields),
      (a) => apiClient.get<unknown>("/global/spend/report", { ...auth, query: a }),
    ),
    operation("read", "spend")(
      "team_spend_report",
      "View a team's spend by model and key (requires an enterprise license)",
      dated({ team_id: text }),
      (a) => apiClient.get<unknown>("/team/spend/report", { ...auth, query: a }),
    ),
    operation("read", "spend")(
      "key_spend_report",
      "View a key's spend by model (requires an enterprise license)",
      dated({ api_key: hash }),
      (a) => apiClient.get<unknown>("/key/spend/report", { ...auth, query: a }),
    ),
    ...usageOperations,
    operation("read", "log")(
      "request_logs",
      "List request cost, timing and status, excluding prompts and responses",
      dated(requestLogsFields),
      (a) =>
        apiClient.get<unknown>("/spend/logs/ui", {
          ...auth,
          query: { ...a, start_date: `${a.start_date} 00:00:00`, end_date: `${a.end_date} 23:59:59` },
        }),
    ),
    findOperation,
    callOperation,
  ];
}
