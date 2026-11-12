import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, testQueryClient, within } from "../../../tests/test-utils";
import type { CredentialItem, CredentialTestResult, CredentialTestResults } from "@/components/networking";
import ProvidersView from "./ProvidersView";

const credentialTestBatchCall = vi.fn<(token: string, names: readonly string[]) => Promise<CredentialTestResults>>();
const credentialTestLatestCall = vi.fn<() => Promise<CredentialTestResults>>();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  credentialTestBatchCall: (token: string, names: readonly string[]) => credentialTestBatchCall(token, names),
  credentialTestLatestCall: () => credentialTestLatestCall(),
  latestHealthChecksCall: () => Promise.resolve({ latest_health_checks: {} }),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "at", userId: "u1", userRole: "Admin" }),
}));

vi.mock("@/app/(dashboard)/hooks/providers/useProviderFields", () => ({
  useProviderFields: () => ({
    data: [
      ["OpenAI", "OpenAI", "openai", "cloud_api"],
      ["Anthropic", "Anthropic", "anthropic", "cloud_api"],
      ["Cohere", "Cohere", "cohere", "cloud_api"],
      ["Mistral", "Mistral AI", "mistral", "cloud_api"],
      ["Bedrock", "Amazon Bedrock", "bedrock", "enterprise_cloud"],
      ["OpenAI_Compatible", "OpenAI-Compatible Endpoints", "openai", "self_hosted"],
    ].map(([provider, provider_display_name, hangarllm_provider, category]) => ({
      provider,
      provider_display_name,
      hangarllm_provider,
      category,
      credential_fields: [],
    })),
    isLoading: false,
    error: null,
  }),
}));

const credential = (name: string, info: CredentialItem["credential_info"], displayName?: string): CredentialItem => ({
  credential_name: name,
  display_name: displayName ?? null,
  credential_values: {},
  credential_info: info,
});

const CREDENTIALS = [
  credential("openai-a", { custom_llm_provider: "OpenAI" }),
  credential("openai-b", { custom_llm_provider: "OpenAI" }),
  credential("openai-c", { custom_llm_provider: "OpenAI" }),
  credential("mistral", { custom_llm_provider: "Mistral" }),
  credential("lab", { custom_llm_provider: "OpenAI", compatible: "openai" }, "Lab vLLM"),
];

vi.mock("@/app/(dashboard)/hooks/credentials/useCredentials", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/app/(dashboard)/hooks/credentials/useCredentials")>()),
  useCredentials: () => ({ data: { credentials: CREDENTIALS } }),
}));

vi.mock("@/app/(dashboard)/hooks/models/useModels", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/app/(dashboard)/hooks/models/useModels")>()),
  useAllModelDeployments: () => ({
    data: [
      { model_name: "gpt", hangarllm_params: { model: "openai/gpt-4o" }, model_info: { id: "m1" } },
      {
        model_name: "qwen",
        hangarllm_params: { model: "openai/qwen", hangarllm_credential_name: "lab" },
        model_info: { id: "m2" },
      },
    ],
  }),
}));

const result = (name: string, overrides: Partial<CredentialTestResult> = {}): CredentialTestResult => ({
  credential_name: name,
  status: "healthy",
  kind: "model_list",
  http_status: null,
  error: null,
  latency_ms: 100,
  checked_at: "2026-11-12T10:00:00Z",
  ...overrides,
});

const group = (name: string) => screen.getByRole("region", { name: new RegExp(`^${name}`) });
const card = (name: string) => screen.getByRole("listitem", { name });

describe("ProvidersView", () => {
  beforeEach(() => {
    testQueryClient.clear();
    vi.clearAllMocks();
    credentialTestLatestCall.mockResolvedValue({
      results: [
        result("openai-a"),
        result("openai-b"),
        result("openai-c", { status: "failing", http_status: 401, error: "Invalid API key" }),
      ],
    });
  });

  it("lists configured providers first in each group, then the rest by name", async () => {
    renderWithProviders(<ProvidersView />);

    await screen.findByText("2 healthy · 1 failing (401)");
    expect(
      within(group("Cloud API"))
        .getAllByRole("listitem")
        .map((item) => item.getAttribute("aria-label")),
    ).toEqual(["Mistral AI", "OpenAI", "Anthropic", "Cohere"]);
  });

  it("builds each card's status line and model count from its credentials, results and models", async () => {
    renderWithProviders(<ProvidersView />);

    expect(await within(card("OpenAI")).findByText("2 healthy · 1 failing (401)")).toBeInTheDocument();
    expect(card("OpenAI")).toHaveTextContent("1 model");
    expect(card("Mistral AI")).toHaveTextContent("Not tested");
    expect(card("Cohere")).toHaveTextContent("Not configured");
    expect(card("Cohere")).toHaveTextContent("0 models");
  });

  it("shows a compatible endpoint as its own self-hosted card, apart from the OpenAI card", async () => {
    renderWithProviders(<ProvidersView />);

    const lab = await within(group("Self-hosted and compatible")).findByRole("listitem", { name: "Lab vLLM" });
    expect(lab).toHaveTextContent("1 model");
    expect(within(group("Cloud API")).queryByRole("listitem", { name: "Lab vLLM" })).not.toBeInTheDocument();
  });

  it("filters cards by search and by Configured only", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProvidersView />);
    await screen.findByText("2 healthy · 1 failing (401)");

    await user.click(screen.getByRole("switch", { name: "Configured only" }));
    expect(screen.queryByRole("listitem", { name: "Cohere" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /^Enterprise cloud/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("switch", { name: "Configured only" }));
    await user.type(screen.getByRole("searchbox", { name: "Search providers" }), "bedrock");
    expect(screen.getAllByRole("listitem").map((item) => item.getAttribute("aria-label"))).toEqual(["Amazon Bedrock"]);
  });

  it("tests a group's providers one card at a time and shows a failure on its card", async () => {
    credentialTestLatestCall.mockResolvedValue({ results: [] });
    const resolvers: Array<(value: CredentialTestResults) => void> = [];
    credentialTestBatchCall.mockImplementation(() => new Promise((resolve) => resolvers.push(resolve)));
    const user = userEvent.setup();
    renderWithProviders(<ProvidersView />);
    await within(card("OpenAI")).findByText("Not tested");

    await user.click(within(group("Cloud API")).getByRole("button", { name: "Test All" }));

    expect(card("Mistral AI")).toHaveTextContent("Testing");
    expect(card("OpenAI")).toHaveTextContent("Waiting to test");
    expect(card("Cohere")).toHaveTextContent("Not configured");
    expect(credentialTestBatchCall).toHaveBeenCalledTimes(1);
    expect(credentialTestBatchCall).toHaveBeenLastCalledWith("at", ["mistral"]);

    resolvers[0]({
      results: [result("mistral", { status: "failing", http_status: null, error: "Request timed out" })],
    });

    expect(await within(card("Mistral AI")).findByText("1 failing (timeout)")).toBeInTheDocument();
    expect(card("OpenAI")).toHaveTextContent("Testing");
    expect(credentialTestBatchCall).toHaveBeenLastCalledWith("at", ["openai-a", "openai-b", "openai-c"]);

    resolvers[1]({
      results: [result("openai-a"), result("openai-b", { status: "failing", http_status: 401 }), result("openai-c")],
    });

    expect(await within(card("OpenAI")).findByText("2 healthy · 1 failing (401)")).toBeInTheDocument();
    expect(within(group("Cloud API")).getByRole("button", { name: "Test All" })).toBeEnabled();
    expect(credentialTestBatchCall).toHaveBeenCalledTimes(2);
  });
});
