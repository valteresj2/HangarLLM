import { describe, expect, it } from "vitest";
import { gatewayTraceFromHeaders } from "./reply_trace";

describe("gatewayTraceFromHeaders", () => {
  it("reads routing, timing, cost and guardrail details from the gateway headers", () => {
    const headers = new Headers([
      ["x-hangarllm-call-id", "call-1"],
      ["x-hangarllm-model-group", "fast"],
      ["x-hangarllm-model-id", "deployment-1"],
      ["x-hangarllm-model-name", "provider/model-a"],
      ["x-hangarllm-model-api-base", "https://provider.test/v1"],
      ["x-hangarllm-attempted-fallbacks", "1"],
      ["x-hangarllm-attempted-retries", "2"],
      ["x-hangarllm-overhead-duration-ms", "12.5"],
      ["x-hangarllm-response-duration-ms", "840"],
      ["x-hangarllm-response-cost", "0.0004"],
      ["x-hangarllm-applied-guardrails", "pii-mask, toxicity"],
      ["x-hangarllm-applied-policies", "strict"],
      ["x-hangarllm-cache-key", "abc"],
    ]);
    const trace = gatewayTraceFromHeaders(headers);

    const expected = {
      callId: "call-1",
      modelGroup: "fast",
      deploymentId: "deployment-1",
      providerModel: "provider/model-a",
      apiBase: "https://provider.test/v1",
      attemptedFallbacks: 1,
      attemptedRetries: 2,
      overheadMs: 12.5,
      responseMs: 840,
      cost: 0.0004,
      appliedGuardrails: ["pii-mask", "toxicity"],
      appliedPolicies: ["strict"],
      cacheHit: true,
    };
    expect(trace).toEqual(expected);
  });

  it("leaves details unset when headers are missing, blank or not numeric", () => {
    const trace = gatewayTraceFromHeaders(
      new Headers({
        "x-hangarllm-model-group": "  ",
        "x-hangarllm-attempted-fallbacks": "none",
        "x-hangarllm-applied-guardrails": " , ",
      }),
    );

    expect(trace.modelGroup).toBeUndefined();
    expect(trace.attemptedFallbacks).toBeUndefined();
    expect(trace.appliedGuardrails).toEqual([]);
    expect(trace.cacheHit).toBe(false);
  });

  it("leaves policies unknown when the gateway's own headers are hidden from the page", () => {
    const hidden = gatewayTraceFromHeaders(new Headers({ "x-hangarllm-applied-guardrails": "pii-mask" }));
    const visible = gatewayTraceFromHeaders(new Headers({ "x-hangarllm-call-id": "call-1" }));

    expect(hidden.appliedGuardrails).toEqual(["pii-mask"]);
    expect(hidden.appliedPolicies).toBeUndefined();
    expect(visible.appliedPolicies).toEqual([]);
  });
});
