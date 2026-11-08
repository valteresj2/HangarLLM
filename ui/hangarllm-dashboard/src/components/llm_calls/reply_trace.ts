export type GatewayTrace = Readonly<{
  callId?: string;
  modelGroup?: string;
  deploymentId?: string;
  providerModel?: string;
  apiBase?: string;
  attemptedFallbacks?: number;
  attemptedRetries?: number;
  overheadMs?: number;
  responseMs?: number;
  cost?: number;
  appliedGuardrails: readonly string[];
  appliedPolicies?: readonly string[];
  cacheHit: boolean;
}>;

const text = (headers: Headers, name: string): string | undefined => {
  const value = headers.get(name)?.trim();
  return value ? value : undefined;
};

const number = (headers: Headers, name: string): number | undefined => {
  const value = text(headers, name);
  if (value === undefined) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const list = (headers: Headers, name: string): readonly string[] =>
  (text(headers, name) ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item !== "");

export const gatewayTraceFromHeaders = (headers: Headers): GatewayTrace => ({
  callId: text(headers, "x-hangarllm-call-id"),
  modelGroup: text(headers, "x-hangarllm-model-group"),
  deploymentId: text(headers, "x-hangarllm-model-id"),
  providerModel: text(headers, "x-hangarllm-model-name"),
  apiBase: text(headers, "x-hangarllm-model-api-base"),
  attemptedFallbacks: number(headers, "x-hangarllm-attempted-fallbacks"),
  attemptedRetries: number(headers, "x-hangarllm-attempted-retries"),
  overheadMs: number(headers, "x-hangarllm-overhead-duration-ms"),
  responseMs: number(headers, "x-hangarllm-response-duration-ms"),
  cost: number(headers, "x-hangarllm-response-cost"),
  appliedGuardrails: list(headers, "x-hangarllm-applied-guardrails"),
  appliedPolicies: headers.has("x-hangarllm-call-id") ? list(headers, "x-hangarllm-applied-policies") : undefined,
  cacheHit: text(headers, "x-hangarllm-cache-key") !== undefined,
});
