import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen, testQueryClient, waitFor } from "../../../tests/test-utils";
import type { Model } from "@/components/networking";
import AddCompatibleModal from "./AddCompatibleModal";

const credentialCreateCall = vi.fn<(token: string, body: Record<string, unknown>) => Promise<unknown>>();
const modelCreateCall = vi.fn<(token: string, body: Model) => Promise<unknown>>();

vi.mock("@/components/networking", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/networking")>()),
  credentialCreateCall: (token: string, body: Record<string, unknown>) => credentialCreateCall(token, body),
  modelCreateCall: (token: string, body: Model) => modelCreateCall(token, body),
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => ({ accessToken: "at", userId: "u1", userRole: "Admin" }),
}));

const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe("AddCompatibleModal", () => {
  beforeEach(() => {
    testQueryClient.clear();
    vi.clearAllMocks();
    credentialCreateCall.mockResolvedValue({});
    modelCreateCall.mockResolvedValue({});
  });

  it("refuses to save without a base URL", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<AddCompatibleModal kind="openai" open onClose={onClose} />);

    fill("Display name", "Lab vLLM");
    fill("API key", "sk-lab");
    fill("Base URL", "   ");
    await user.click(screen.getByRole("button", { name: "Save endpoint" }));

    expect(await screen.findByText("Base URL is required")).toBeInTheDocument();
    expect(screen.getByLabelText("Base URL")).toHaveAttribute("aria-invalid", "true");
    expect(credentialCreateCall).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("saves an Anthropic compatible credential marked compatible, then adds each listed model on it", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<AddCompatibleModal kind="anthropic" open onClose={onClose} />);

    fill("Display name", "Team Gateway");
    fill("Base URL", " https://gw.internal/anthropic ");
    fill("API key", "sk-gw");
    fill("Model names (optional)", "claude-a, claude-b\nclaude-a");
    await user.click(screen.getByRole("button", { name: "Save endpoint" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const expectedCredential = {
      credential_name: "anthropic-compatible-team-gateway",
      display_name: "Team Gateway",
      credential_values: { api_base: "https://gw.internal/anthropic", api_key: "sk-gw" },
      credential_info: { custom_llm_provider: "Anthropic", compatible: "anthropic" },
    };
    expect(credentialCreateCall).toHaveBeenCalledWith("at", expectedCredential);
    expect(modelCreateCall.mock.calls.map(([, body]) => body)).toEqual(
      ["claude-a", "claude-b"].map((name) => ({
        model_name: name,
        hangarllm_params: {
          model: `anthropic/${name}`,
          custom_llm_provider: "anthropic",
          hangarllm_credential_name: "anthropic-compatible-team-gateway",
        },
        model_info: {},
      })),
    );
  });

  it("adds no model when no model names are given", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<AddCompatibleModal kind="openai" open onClose={onClose} />);

    fill("Display name", "Local");
    fill("Base URL", "http://localhost:8000/v1");
    await user.click(screen.getByRole("button", { name: "Save endpoint" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(credentialCreateCall.mock.calls[0][1]).toMatchObject({
      credential_values: { api_base: "http://localhost:8000/v1" },
      credential_info: { custom_llm_provider: "OpenAI", compatible: "openai" },
    });
    expect(modelCreateCall).not.toHaveBeenCalled();
  });
});
