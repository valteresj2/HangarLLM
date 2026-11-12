import type { ReactNode } from "react";
import userEvent from "@testing-library/user-event";
import type { OnUrlUpdateFunction } from "nuqs/adapters/testing";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen, testQueryClient, waitFor, within } from "../../../tests/test-utils";
import { buildCatalog } from "@/app/(dashboard)/hooks/providers/useProviderCatalog";
import type { CredentialSubmission } from "@/components/model_add/credential_form_helpers";
import type { CredentialItem, CredentialTestRequest, CredentialTestResult } from "@/components/networking";
import ProviderDetail from "./ProviderDetail";
import { buildProviderCards, type ProviderModel } from "./providerCards";

const credentialTestCall = vi.fn<(token: string, body: CredentialTestRequest) => Promise<CredentialTestResult>>();
const credentialCreateCall = vi.fn<(token: string, body: Record<string, unknown>) => Promise<unknown>>();
const modelOrderUpdateCall = vi.fn<(token: string, id: string, order: number) => Promise<unknown>>();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  credentialTestCall: (token: string, body: CredentialTestRequest) => credentialTestCall(token, body),
  credentialCreateCall: (token: string, body: Record<string, unknown>) => credentialCreateCall(token, body),
  modelOrderUpdateCall: (token: string, id: string, order: number) => modelOrderUpdateCall(token, id, order),
  latestHealthChecksCall: () => Promise.resolve({ latest_health_checks: { m1: { status: "healthy" } } }),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "at", userId: "u1", userRole: "Admin" }),
}));

const SUBMISSION: CredentialSubmission = {
  credential_name: "openai-new",
  custom_llm_provider: "OpenAI",
  credential_values: { api_key: "sk-test" },
};

vi.mock("@/components/model_add/CredentialModal", () => ({
  default: ({
    mode,
    notice,
    onSubmit,
  }: {
    mode: string;
    notice?: ReactNode;
    onSubmit: (submission: CredentialSubmission, valuesToDelete: readonly string[]) => void;
  }) => (
    <div role="dialog" aria-label={`${mode} credential`}>
      {notice}
      <button type="button" onClick={() => onSubmit(SUBMISSION, [])}>
        Submit credential
      </button>
    </div>
  ),
}));

const catalog = buildCatalog([
  {
    provider: "OpenAI",
    provider_display_name: "OpenAI",
    hangarllm_provider: "openai",
    category: "cloud_api",
    default_model_placeholder: "gpt-4o",
    credential_fields: [],
  },
]);

const credential = (name: string, source: "db" | "config"): CredentialItem => ({
  credential_name: name,
  source,
  credential_values: {},
  credential_info: { custom_llm_provider: "OpenAI" },
});

const MODELS: ProviderModel[] = [
  {
    model_name: "gpt",
    hangarllm_params: { model: "openai/gpt-4o", hangarllm_credential_name: "openai-prod", order: 1 },
    model_info: { id: "m1", db_model: true },
  },
  {
    model_name: "gpt-config",
    hangarllm_params: { model: "openai/gpt-4o-mini", order: 2 },
    model_info: { id: "m2", db_model: false },
  },
];

const result = (overrides: Partial<CredentialTestResult>): CredentialTestResult => ({
  credential_name: null,
  status: "healthy",
  kind: "model_list",
  http_status: null,
  error: null,
  latency_ms: 50,
  checked_at: "2026-11-12T10:00:00Z",
  ...overrides,
});

const renderDetail = (options: { onUrlUpdate?: OnUrlUpdateFunction } = {}) => {
  const [card] = buildProviderCards(
    catalog,
    [credential("openai-prod", "db"), credential("openai-from-yaml", "config")],
    MODELS,
  );
  return renderWithProviders(<ProviderDetail card={card} results={new Map()} onBack={vi.fn()} />, options);
};

const openAddCredential = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole("button", { name: "Add credential" }));
  await user.click(within(screen.getByRole("dialog", { name: "add credential" })).getByText("Submit credential"));
};

describe("ProviderDetail", () => {
  beforeEach(() => {
    testQueryClient.clear();
    vi.clearAllMocks();
    credentialCreateCall.mockResolvedValue({});
    modelOrderUpdateCall.mockResolvedValue({});
  });

  it("does not save a credential whose test fails until the admin chooses Save without testing", async () => {
    credentialTestCall.mockResolvedValue(result({ status: "failing", http_status: 401, error: "Invalid API key" }));
    const user = userEvent.setup();
    renderDetail();

    await openAddCredential(user);

    expect(await screen.findByText("The test failed: Invalid API key")).toBeInTheDocument();
    expect(credentialTestCall).toHaveBeenCalledWith("at", {
      provider: "OpenAI",
      credential_values: { api_key: "sk-test" },
    });
    expect(credentialCreateCall).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Save without testing" }));

    await waitFor(() =>
      expect(credentialCreateCall).toHaveBeenCalledWith("at", {
        credential_name: "openai-new",
        credential_values: { api_key: "sk-test" },
        credential_info: { custom_llm_provider: "OpenAI" },
      }),
    );
  });

  it("saves a credential right away when its test passes", async () => {
    credentialTestCall.mockResolvedValue(result({}));
    const user = userEvent.setup();
    renderDetail();

    await openAddCredential(user);

    await waitFor(() => expect(credentialCreateCall).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("dialog", { name: "add credential" })).not.toBeInTheDocument();
  });

  it("asks for a test model when the provider needs one and stores the picked model with the credential", async () => {
    credentialTestCall
      .mockResolvedValueOnce(result({ status: "untested", kind: null, error: "test model required" }))
      .mockResolvedValueOnce(result({ kind: "completion" }));
    const user = userEvent.setup();
    renderDetail();

    await openAddCredential(user);
    fireEvent.change(await screen.findByLabelText("Test model"), { target: { value: "gpt-4o-mini" } });
    expect(credentialCreateCall).not.toHaveBeenCalled();
    await user.click(screen.getByText("Submit credential"));

    await waitFor(() => expect(credentialCreateCall).toHaveBeenCalledTimes(1));
    expect(credentialTestCall).toHaveBeenLastCalledWith("at", expect.objectContaining({ test_model: "gpt-4o-mini" }));
    expect(credentialCreateCall.mock.calls[0][1]).toMatchObject({
      credential_info: { custom_llm_provider: "OpenAI", test_model: "gpt-4o-mini" },
    });
  });

  it("shows config credentials read only, with a test action but no edit or delete", () => {
    renderDetail();

    const configRow = screen.getByRole("listitem", { name: "openai-from-yaml" });
    expect(configRow).toHaveTextContent("From config");
    expect(within(configRow).getByRole("button", { name: "Test" })).toBeInTheDocument();
    expect(within(configRow).queryByRole("button", { name: "Edit credential" })).not.toBeInTheDocument();
    expect(within(configRow).queryByRole("button", { name: "Delete credential" })).not.toBeInTheDocument();

    const dbRow = screen.getByRole("listitem", { name: "openai-prod" });
    expect(dbRow).not.toHaveTextContent("From config");
    expect(within(dbRow).getByRole("button", { name: "Edit credential" })).toBeInTheDocument();
    expect(within(dbRow).getByRole("button", { name: "Delete credential" })).toBeInTheDocument();
  });

  it("opens the Add Model tab with the provider and chosen credential filled in", async () => {
    const onUrlUpdate = vi.fn<OnUrlUpdateFunction>();
    const user = userEvent.setup();
    renderDetail({ onUrlUpdate });

    await user.click(screen.getByRole("button", { name: "Add model" }));

    await waitFor(() => expect(onUrlUpdate.mock.calls.at(-1)?.[0].searchParams.get("tab")).toBe("add"));
    const params = onUrlUpdate.mock.calls.at(-1)?.[0].searchParams;
    expect(params?.get("provider")).toBe("openai");
    expect(params?.get("hangarllm_credential_name")).toBe("openai-prod");
  });

  it("sends a changed order to /model/update and leaves config models read only", async () => {
    renderDetail();

    const order = screen.getByRole("spinbutton", { name: "Order for gpt" });
    fireEvent.change(order, { target: { value: "3" } });
    fireEvent.blur(order);

    await waitFor(() => expect(modelOrderUpdateCall).toHaveBeenCalledWith("at", "m1", 3));
    expect(screen.queryByRole("spinbutton", { name: "Order for gpt-config" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Order for gpt-config")).toHaveTextContent("2");
  });

  it("does not send an order that is unchanged or not a positive whole number", () => {
    renderDetail();

    const order = screen.getByRole("spinbutton", { name: "Order for gpt" });
    fireEvent.change(order, { target: { value: "1" } });
    fireEvent.blur(order);
    fireEvent.change(order, { target: { value: "0" } });
    fireEvent.blur(order);

    expect(modelOrderUpdateCall).not.toHaveBeenCalled();
    expect(order).toHaveValue(1);
  });
});
