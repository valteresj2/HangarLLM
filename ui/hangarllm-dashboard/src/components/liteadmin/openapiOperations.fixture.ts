export const openApiFixture = {
  openapi: "3.1.0",
  paths: {
    "/guardrails/list": {
      get: { summary: "List Guardrails", operationId: "list_guardrails", tags: ["guardrails"] },
    },
    "/guardrails": {
      post: {
        summary: "Create Guardrail",
        tags: ["guardrails"],
        requestBody: {
          required: true,
          content: { "application/json": { schema: { $ref: "#/components/schemas/CreateGuardrailRequest" } } },
        },
      },
    },
    "/guardrails/{guardrail_id}": {
      get: {
        summary: "Get Guardrail Info",
        tags: ["guardrails"],
        parameters: [{ name: "guardrail_id", in: "path", required: true, schema: { type: "string" } }],
      },
      delete: {
        summary: "Delete Guardrail",
        tags: ["guardrails"],
        parameters: [{ name: "guardrail_id", in: "path", required: true, schema: { type: "string" } }],
      },
    },
    "/model/info": {
      get: {
        summary: "Model Info",
        description: "Lists deployments and mentions guardrails in passing.",
        tags: ["model management"],
        parameters: [
          { name: "model_id", in: "query", schema: { anyOf: [{ type: "string" }, { type: "null" }] } },
          { name: "hangarllm-changed-by", in: "header", schema: { type: "string" } },
        ],
      },
    },
    "/key/leak-report": { post: { summary: "Report Leaked Key", tags: ["key management"] } },
    "/credentials": { get: { summary: "Get Credentials", tags: ["credential management"] } },
  },
  components: {
    schemas: {
      CreateGuardrailRequest: {
        type: "object",
        required: ["guardrail"],
        properties: { guardrail: { $ref: "#/components/schemas/Guardrail" } },
      },
      Guardrail: {
        type: "object",
        required: ["guardrail_name", "hangarllm_params"],
        properties: {
          guardrail_name: { type: "string" },
          hangarllm_params: { $ref: "#/components/schemas/GuardrailParams" },
        },
      },
      GuardrailParams: {
        type: "object",
        properties: {
          mode: { type: "string", enum: ["pre_call", "post_call"] },
          nested: { $ref: "#/components/schemas/Deep" },
        },
      },
      Deep: { type: "object", properties: { deeper: { type: "string" } } },
    },
  },
};
