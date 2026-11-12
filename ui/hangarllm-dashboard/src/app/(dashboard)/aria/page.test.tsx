import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LegacyAriaPage from "./page";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/components/liteadmin/LiteAdmin", () => ({ LiteAdminPage: () => null }));

describe("legacy Aria page", () => {
  beforeEach(() => {
    replace.mockReset();
    window.history.replaceState(null, "", "/ui/aria?from=bookmark#latest");
  });

  it("forwards old links to the DockWorker page with their query and hash", () => {
    render(<LegacyAriaPage />);
    expect(replace).toHaveBeenCalledExactlyOnceWith("/ui/dockworker?from=bookmark#latest");
  });
});
