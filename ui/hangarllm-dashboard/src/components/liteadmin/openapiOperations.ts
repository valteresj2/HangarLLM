import { z } from "zod";

export const GENERIC_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"] as const;
export type GenericMethod = (typeof GENERIC_METHODS)[number];

export const MAX_FOUND_OPERATIONS = 5;
const SCHEMA_DEPTH = 3;
const MAX_PROPERTIES = 25;
const MAX_ENUM_VALUES = 20;
const MAX_DESCRIPTION = 160;

export const DENIED_OPERATION_PATHS: readonly RegExp[] = [
  /encrypt/i,
  /salt/i,
  /master[_-]?key/i,
  /secret/i,
  /vault|kms|cyberark/i,
  /credential/i,
  /user[_-]connection/i,
  /user-env-vars/i,
  /^\/config_overrides(\/|$)/i,
  /^\/key\/leak-report(\/|$)/i,
  /^\/key\/(service-account\/)?generate(\/|$)/i,
  /regenerate/i,
  /^\/user\/new(\/|$)/i,
  /sso/i,
  /login|logout/i,
  /^\/session(\/|$)/i,
  /oauth|authorize|jwks|\.well-known/i,
  /(^|\/)token$/i,
  /auth-token/i,
  /password/i,
  /invitation|onboarding/i,
  /^\/scim(\/|$)/i,
  /^\/config\/(update|field|yaml|reload|delete)(\/|$)/i,
  /^\/config$/i,
  /^\/openapi\.json$/i,
];

export function isDeniedOperationPath(path: string): boolean {
  return DENIED_OPERATION_PATHS.some((pattern) => pattern.test(path));
}

type JsonObject = Record<string, unknown>;
const jsonObject = z.record(z.string(), z.unknown());
const parameterSchema = z.object({
  name: z.string(),
  in: z.string(),
  required: z.boolean().optional(),
  description: z.string().optional(),
  schema: jsonObject.optional(),
});
const operationSchema = z.object({
  summary: z.string().optional(),
  description: z.string().optional(),
  operationId: z.string().optional(),
  tags: z.array(z.string()).optional(),
  parameters: z.array(z.union([parameterSchema, jsonObject])).optional(),
  requestBody: jsonObject.optional(),
});
const specSchema = z.object({
  paths: z.record(z.string(), z.record(z.string(), z.unknown())),
  components: z.object({ schemas: z.record(z.string(), jsonObject).optional() }).optional(),
});

type Parameter = z.infer<typeof parameterSchema>;
interface CatalogOperation {
  method: GenericMethod;
  path: string;
  summary?: string;
  description?: string;
  parameters: Parameter[];
  requestBody?: JsonObject;
  terms: { path: string[]; summary: string[]; tags: string[]; description: string[] };
}
export interface OperationCatalog {
  operations: CatalogOperation[];
  schemas: Record<string, JsonObject>;
}

const normalize = (word: string) => (word.length > 3 ? word.replace(/s$/, "") : word);
const words = (text: string | undefined) =>
  (text ?? "")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((word) => word.length > 1)
    .map(normalize);
const shorten = (text: string | undefined, limit = MAX_DESCRIPTION) =>
  text && text.length > limit ? `${text.slice(0, limit - 1)}…` : text;

export function buildOperationCatalog(spec: unknown): OperationCatalog {
  const parsed = specSchema.parse(spec);
  const operations = Object.entries(parsed.paths).flatMap(([path, methods]) =>
    isDeniedOperationPath(path)
      ? []
      : Object.entries(methods).flatMap(([rawMethod, rawOperation]) => {
          const method = rawMethod.toUpperCase();
          const operation = operationSchema.safeParse(rawOperation);
          if (!GENERIC_METHODS.includes(method as GenericMethod) || !operation.success) return [];
          const { summary, description, operationId, tags, parameters = [], requestBody } = operation.data;
          return [
            {
              method: method as GenericMethod,
              path,
              summary,
              description,
              parameters: parameters.flatMap((parameter) => {
                const valid = parameterSchema.safeParse(parameter);
                return valid.success && ["path", "query"].includes(valid.data.in) ? [valid.data] : [];
              }),
              requestBody,
              terms: {
                path: words(path),
                summary: [...words(summary), ...words(operationId)],
                tags: (tags ?? []).flatMap(words),
                description: words(description?.slice(0, 400)),
              },
            },
          ];
        }),
  );
  return { operations, schemas: parsed.components?.schemas ?? {} };
}

function score(operation: CatalogOperation, query: readonly string[]): number {
  return query.reduce((total, word) => {
    const { path, summary, tags, description } = operation.terms;
    if (path.includes(word)) return total + 4;
    if (summary.includes(word)) return total + 3;
    if (path.some((term) => term.includes(word) || word.includes(term))) return total + 2;
    if (tags.includes(word)) return total + 1.5;
    if (description.includes(word)) return total + 0.5;
    return total;
  }, 0);
}

const refName = (ref: unknown) => (typeof ref === "string" ? ref.split("/").at(-1) : undefined);

function compactSchema(schema: unknown, schemas: Record<string, JsonObject>, depth: number): unknown {
  const node = jsonObject.safeParse(schema);
  if (!node.success) return undefined;
  const value = node.data;
  const reference = refName(value.$ref);
  if (reference) {
    const target = schemas[reference];
    if (!target || depth <= 0) return { $ref: reference };
    return compactSchema(target, schemas, depth - 1);
  }
  const compactList = (list: unknown) =>
    Array.isArray(list) ? list.map((item) => compactSchema(item, schemas, depth)) : undefined;
  const variants = compactList(value.anyOf ?? value.oneOf);
  if (variants) {
    const present = variants.filter((variant) => !(isJsonObject(variant) && variant.type === "null"));
    const nullable = present.length < variants.length;
    const single = present.length === 1 && isJsonObject(present[0]) ? present[0] : undefined;
    if (single) return { ...single, ...(nullable ? { nullable: true } : {}) };
    return { anyOf: present, ...(nullable ? { nullable: true } : {}) };
  }
  const merged = compactList(value.allOf);
  if (merged?.length === 1) return merged[0];
  const properties = jsonObject.safeParse(value.properties);
  const entries = properties.success ? Object.entries(properties.data) : [];
  return {
    ...(typeof value.type === "string" ? { type: value.type } : {}),
    ...(typeof value.format === "string" ? { format: value.format } : {}),
    ...(Array.isArray(value.enum) ? { enum: value.enum.slice(0, MAX_ENUM_VALUES) } : {}),
    ...(value.default !== undefined && typeof value.default !== "object" ? { default: value.default } : {}),
    ...(typeof value.description === "string" ? { description: shorten(value.description) } : {}),
    ...(merged && merged.length > 1 ? { allOf: merged } : {}),
    ...(value.items ? { items: compactSchema(value.items, schemas, depth) } : {}),
    ...(Array.isArray(value.required) ? { required: value.required } : {}),
    ...(entries.length
      ? {
          properties: Object.fromEntries(
            entries.slice(0, MAX_PROPERTIES).map(([name, property]) => [name, compactSchema(property, schemas, depth)]),
          ),
        }
      : {}),
    ...(entries.length > MAX_PROPERTIES ? { omitted_properties: entries.length - MAX_PROPERTIES } : {}),
  };
}

function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function describeOperation(operation: CatalogOperation, schemas: Record<string, JsonObject>) {
  const content = jsonObject.safeParse(operation.requestBody?.content);
  const json = content.success ? jsonObject.safeParse(content.data["application/json"]) : undefined;
  const body = json?.success ? compactSchema(json.data.schema, schemas, SCHEMA_DEPTH) : undefined;
  return {
    method: operation.method,
    path: operation.path,
    summary: operation.summary,
    description: shorten(operation.description),
    parameters: operation.parameters.map((parameter) => ({
      name: parameter.name,
      in: parameter.in,
      required: parameter.required ?? parameter.in === "path",
      schema: compactSchema(parameter.schema, schemas, 1),
      description: shorten(parameter.description),
    })),
    ...(body ? { request_body: body } : {}),
  };
}

export function findOperations(catalog: OperationCatalog, query: string, limit = MAX_FOUND_OPERATIONS) {
  const terms = [...new Set(words(query))];
  if (!terms.length) return [];
  return catalog.operations
    .map((operation) => ({ operation, score: score(operation, terms) }))
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score || a.operation.path.length - b.operation.path.length)
    .slice(0, limit)
    .map(({ operation }) => describeOperation(operation, catalog.schemas));
}

export interface OperationRequest {
  method: GenericMethod;
  path: string;
  path_params?: readonly { name: string; value: string }[];
}

export type ResolvedOperation =
  | { ok: true; method: GenericMethod; path: string; summary?: string }
  | { ok: false; message: string };

export function resolveOperation(catalog: OperationCatalog, request: OperationRequest): ResolvedOperation {
  if (isDeniedOperationPath(request.path)) {
    return {
      ok: false,
      message: "This operation is not available to the agent. Ask the administrator to use the dashboard.",
    };
  }
  const operation = catalog.operations.find(
    (candidate) => candidate.method === request.method && candidate.path === request.path,
  );
  if (!operation) {
    return {
      ok: false,
      message: "Unknown operation. Use find_operation and pass its method and path template exactly.",
    };
  }
  const values = new Map((request.path_params ?? []).map(({ name, value }) => [name, value]));
  const names = [...operation.path.matchAll(/\{([^}]+)\}/g)].map(([, name]) => name);
  const missing = names.filter((name) => !values.get(name)?.trim());
  if (missing.length) return { ok: false, message: `Provide path parameters: ${missing.join(", ")}.` };
  if (names.some((name) => /^\.{1,2}$/.test(values.get(name) ?? ""))) {
    return { ok: false, message: "Path parameters cannot be relative path segments." };
  }
  const path = operation.path.replace(/\{([^}]+)\}/g, (_, name: string) => encodeURIComponent(values.get(name) ?? ""));
  return { ok: true, method: operation.method, path, summary: operation.summary };
}

export interface OpenApiCatalogCache {
  load: (fetchSpec: () => Promise<unknown>) => Promise<OperationCatalog>;
}

export function createOpenApiCatalogCache(): OpenApiCatalogCache {
  let pending: Promise<OperationCatalog> | null = null;
  return {
    load: (fetchSpec) => {
      if (pending) return pending;
      const loading = fetchSpec().then(buildOperationCatalog);
      pending = loading;
      loading.catch(() => {
        if (pending === loading) pending = null;
      });
      return loading;
    },
  };
}
