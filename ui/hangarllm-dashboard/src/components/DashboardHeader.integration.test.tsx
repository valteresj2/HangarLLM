import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PluginModeProvider } from "@/contexts/PluginModeContext";
import { CommandPaletteProvider } from "@/components/CommandPalette/CommandPaletteProvider";
import { DashboardHeader } from "./DashboardHeader";

vi.mock("next/navigation", () => ({
  usePathname: () => "/ui/logs",
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/get/ui_settings")) return Response.json({ values: {} });
      if (url.endsWith("/hangarllm/.well-known/hangarllm-ui-config")) {
        const config = {
          server_root_path: "",
          proxy_base_url: "",
          is_control_plane: true,
          workers: [
            { worker_id: "primary", name: "Primary worker", url: "http://primary.test" },
            { worker_id: "backup", name: "Backup worker", url: "http://backup.test" },
          ],
        };
        return Response.json(config);
      }
      if (url.endsWith("/api/plugins")) {
        return Response.json([{ name: "metrics", display_name: "Metrics", url: "/metrics" }]);
      }
      if (url.endsWith("/public/hangarllm_blog_posts")) {
        return Response.json({
          posts: [
            {
              title: "Gateway update",
              description: "Release notes",
              date: "2026-01-01",
              url: "https://example.com/update",
            },
          ],
        });
      }
      return Response.json({}, { status: 404 });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

function renderHeader() {
  const user = userEvent.setup();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PluginModeProvider accessToken="test-session">
        <CommandPaletteProvider>
          <DashboardHeader accessToken={null} />
        </CommandPaletteProvider>
      </PluginModeProvider>
    </QueryClientProvider>,
  );
  return { user };
}

describe("dashboard header controls", () => {
  it("opens search from both header controls", async () => {
    const { user } = renderHeader();
    await user.click(screen.getByRole("button", { name: "Search or jump to…" }));
    expect(await screen.findByRole("dialog", { name: "Command palette" })).toBeVisible();
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Search", exact: true }));
    expect(await screen.findByRole("dialog", { name: "Command palette" })).toBeVisible();
  });

  it("offers docs under the bell without third-party community or blog links", async () => {
    const { user } = renderHeader();
    await user.click(screen.getByRole("button", { name: /Notifications/ }));
    const tools = await screen.findByRole("dialog", { name: "What's new" });
    expect(within(tools).getByRole("link", { name: "Docs", exact: true })).toHaveAttribute(
      "href",
      "https://github.com/valteresj2/HangarLLM#readme",
    );
    expect(within(tools).queryByRole("link", { name: /Gateway update/ })).not.toBeInTheDocument();
    expect(within(tools).queryByRole("link", { name: "Discord", exact: true })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Join Slack" })).not.toBeInTheDocument();
  });

  it("allows filtering and selecting a worker", async () => {
    localStorage.setItem("hangarllm_selected_worker_id", "primary");
    const { user } = renderHeader();
    const worker = await screen.findByRole("combobox", { name: "Worker" });
    await user.clear(worker);
    await user.type(worker, "Backup");
    await user.click(await screen.findByRole("option", { name: "Backup worker" }));
    expect(localStorage.getItem("hangarllm_selected_worker_id")).toBeNull();
  });
});
