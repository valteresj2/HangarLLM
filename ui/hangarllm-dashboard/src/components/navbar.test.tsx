import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, waitFor, within } from "../../tests/test-utils";
import Navbar from "./navbar";

// Mock the hooks and utilities
vi.mock("@/components/networking", () => ({
  getProxyBaseUrl: vi.fn(() => "http://localhost:4000"),
  getProxyUISettings: vi.fn().mockResolvedValue({
    PROXY_BASE_URL: "",
    PROXY_LOGOUT_URL: "https://example.com/logout",
  }),
  getUiPageUrl: (url: string) => url,
  serverRootPath: "",
}));

vi.mock("@/app/(dashboard)/hooks/useDisableBouncingIcon", () => ({
  useDisableBouncingIcon: () => false,
}));

const mockUserDropdownData = vi.hoisted(() => ({
  current: () => ({
    userId: "test-user",
    userEmail: "test@example.com",
    userRole: "Admin",
    premiumUser: false,
  }),
}));

vi.mock("./Navbar/UserDropdown/UserDropdown", async (importOriginal) => {
  const React = await import("react");
  const { useState } = React;
  const localStorageUtils = await import("@/utils/localStorageUtils");
  return {
    default: function MockUserDropdown({ onLogout }: { onLogout: () => void }) {
      const { userId, userEmail, userRole, premiumUser } = mockUserDropdownData.current();
      const [open, setOpen] = useState(false);
      return (
        <div>
          <button type="button" aria-label="Open account menu" onClick={() => setOpen(!open)}>
            Account
          </button>
          {open && (
            <div data-testid="user-dropdown-content">
              <span>{userId}</span>
              <span>{userRole}</span>
              <span>{userEmail}</span>
              {premiumUser && <span>Premium</span>}
              <button type="button" onClick={() => onLogout()}>
                Logout
              </button>
              <label>
                <input
                  type="checkbox"
                  aria-label="Toggle hide new feature indicators"
                  onChange={(e) => {
                    if (e.target.checked) {
                      localStorageUtils.setLocalStorageItem("disableShowNewBadge", "true");
                      localStorageUtils.emitLocalStorageChange("disableShowNewBadge");
                    }
                  }}
                />
                Toggle hide new feature indicators
              </label>
            </div>
          )}
        </div>
      );
    },
  };
});

// Create mock functions that can be controlled in tests
let mockUseThemeImpl = (): { logoUrl: string | null; logoUrlDark?: string | null } => ({ logoUrl: null });
let mockUseHealthReadinessDetailsImpl = () => ({ data: null as any });
let mockGetLocalStorageItemImpl = (key: string) => null as string | null;
const mockUseAuthorizedImpl = () => ({
  userId: "test-user",
  userEmail: "test@example.com",
  userRole: "Admin",
  premiumUser: false,
});

const useHealthReadinessDetailsSpy = vi.hoisted(() => vi.fn());

vi.mock("@/contexts/ThemeContext", () => ({
  useTheme: () => mockUseThemeImpl(),
}));

vi.mock("@/app/(dashboard)/hooks/healthReadiness/useHealthReadinessDetails", () => ({
  useHealthReadinessDetails: (accessToken: string | null | undefined) => {
    useHealthReadinessDetailsSpy(accessToken);
    return mockUseHealthReadinessDetailsImpl();
  },
}));

vi.mock("@/app/(dashboard)/hooks/useAuthorized", () => ({
  default: () => mockUseAuthorizedImpl(),
}));

vi.mock("@/utils/localStorageUtils", () => ({
  LOCAL_STORAGE_EVENT: "local-storage-change",
  getLocalStorageItem: (key: string) => mockGetLocalStorageItemImpl(key),
  setLocalStorageItem: vi.fn(),
  removeLocalStorageItem: vi.fn(),
  emitLocalStorageChange: vi.fn(),
}));

vi.mock("@/utils/cookieUtils", () => ({
  clearTokenCookies: vi.fn(),
}));

// Mock window.location.href for logout testing
Object.defineProperty(window, "location", {
  value: { href: "" },
  writable: true,
});

describe("Navbar", () => {
  afterEach(() => {
    mockUseThemeImpl = () => ({ logoUrl: null });
  });

  const defaultProps = {
    accessToken: "test-token",
    isPublicPage: false,
  };

  it("should render without crashing", () => {
    renderWithProviders(<Navbar {...defaultProps} />);

    expect(screen.getByRole("button", { name: /^notifications/i })).toBeInTheDocument();
    expect(screen.getByText("Docs")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open account menu/i })).toBeInTheDocument();
  });

  it("should link the logo to the UI home route rather than the proxy origin", () => {
    renderWithProviders(<Navbar {...defaultProps} />);

    expect(screen.getByRole("link", { name: /^hangarllm$/i })).toHaveAttribute("href", "/ui");
  });

  it("renders the HangarLLM lockup when no custom logo is configured", () => {
    renderWithProviders(<Navbar {...defaultProps} />);

    const brand = screen.getByRole("link", { name: /^hangarllm$/i });
    expect(within(brand).queryByRole("img")).not.toBeInTheDocument();
  });

  it("should display user information in dropdown", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Navbar {...defaultProps} />);

    await user.click(screen.getByRole("button", { name: /open account menu/i }));

    await waitFor(() => {
      expect(screen.getByText("test-user")).toBeInTheDocument();
    });
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.getByText("test@example.com")).toBeInTheDocument();
  });

  it("should show sidebar toggle button when onToggleSidebar is provided", () => {
    const mockToggle = vi.fn();
    renderWithProviders(<Navbar {...defaultProps} onToggleSidebar={mockToggle} />);

    const toggleButton = screen.getByTitle("Collapse sidebar");
    expect(toggleButton).toBeInTheDocument();
  });

  it("should call onToggleSidebar when sidebar button is clicked", async () => {
    const mockToggle = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<Navbar {...defaultProps} onToggleSidebar={mockToggle} />);

    const toggleButton = screen.getByTitle("Collapse sidebar");
    await user.click(toggleButton);

    expect(mockToggle).toHaveBeenCalledTimes(1);
  });

  it("should show premium user badge when premiumUser is true", async () => {
    const user = userEvent.setup();
    const originalCurrent = mockUserDropdownData.current;
    mockUserDropdownData.current = () => ({
      userId: "test-user",
      userEmail: "test@example.com",
      userRole: "Admin",
      premiumUser: true,
    });
    renderWithProviders(<Navbar {...defaultProps} />);

    await user.click(screen.getByRole("button", { name: /open account menu/i }));

    await waitFor(() => {
      expect(screen.getByText("Premium")).toBeInTheDocument();
    });

    // Reset mock
    mockUserDropdownData.current = originalCurrent;
  });

  it("should show version badge when health data contains version", () => {
    mockUseHealthReadinessDetailsImpl = () => ({ data: { hangarllm_version: "1.0.0" } });

    renderWithProviders(<Navbar {...defaultProps} />);

    expect(screen.getByText("v1.0.0")).toBeInTheDocument();

    // Reset mock
    mockUseHealthReadinessDetailsImpl = () => ({ data: null });
  });

  it("should forward accessToken to the readiness hook", () => {
    useHealthReadinessDetailsSpy.mockClear();

    renderWithProviders(<Navbar {...defaultProps} accessToken="my-token" />);

    expect(useHealthReadinessDetailsSpy).toHaveBeenCalledWith("my-token");
  });

  it("should forward a null accessToken to the readiness hook (disables the hook)", () => {
    useHealthReadinessDetailsSpy.mockClear();

    renderWithProviders(<Navbar {...defaultProps} accessToken={null} />);

    expect(useHealthReadinessDetailsSpy).toHaveBeenCalledWith(null);
  });

  it.each(["https://example.com/dark-logo.png", null])(
    "should use the configured dark logo %s with the light logo as fallback",
    (logoUrlDark) => {
      const logoUrl = "https://example.com/custom-logo.png";
      mockUseThemeImpl = () => ({ logoUrl, logoUrlDark });

      renderWithProviders(<Navbar {...defaultProps} />);

      const brand = within(screen.getByRole("link", { name: /^hangarllm$/i }));
      const light = brand.getByAltText("HangarLLM");
      const dark = brand.getByAltText("");
      expect(light).toHaveAttribute("src", logoUrl);
      expect(dark).toHaveAttribute("src", logoUrlDark ?? logoUrl);
    },
  );

  it("should show a dark only logo in dark mode and keep the Hangar logo in light mode", () => {
    const logoUrlDark = "https://example.com/dark-logo.png";
    mockUseThemeImpl = () => ({ logoUrl: null, logoUrlDark });

    renderWithProviders(<Navbar {...defaultProps} />);

    const brand = within(screen.getByRole("link", { name: /hangarllm/i }));
    expect(brand.getByAltText("")).toHaveAttribute("src", logoUrlDark);
    expect(brand.queryByAltText("HangarLLM")).not.toBeInTheDocument();
    expect(brand.getByText("Hangar").parentElement).toHaveClass("dark:hidden");
  });

  it("should hide user dropdown and notifications on public pages", () => {
    const publicPageProps = { ...defaultProps, isPublicPage: true };
    renderWithProviders(<Navbar {...publicPageProps} />);

    expect(screen.queryByRole("button", { name: /open account menu/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^notifications/i })).not.toBeInTheDocument();
  });

  it("should handle hide new feature indicators toggle", async () => {
    const user = userEvent.setup();

    // Initially disabled
    mockGetLocalStorageItemImpl = (key: string) => {
      if (key === "disableShowNewBadge") return "false";
      return null;
    };

    renderWithProviders(<Navbar {...defaultProps} />);

    await user.click(screen.getByRole("button", { name: /open account menu/i }));

    await waitFor(() => {
      expect(screen.getByText("test-user")).toBeInTheDocument();
    });

    // Find and click the toggle switch
    const toggleSwitch = screen.getByLabelText("Toggle hide new feature indicators");
    await user.click(toggleSwitch);

    // The functions are mocked globally, so we can check if they were called
    // by accessing them through the mock registry
    const localStorageUtils = vi.mocked(await import("@/utils/localStorageUtils"));
    expect(localStorageUtils.setLocalStorageItem).toHaveBeenCalledWith("disableShowNewBadge", "true");
    expect(localStorageUtils.emitLocalStorageChange).toHaveBeenCalledWith("disableShowNewBadge");

    // Reset mock
    mockGetLocalStorageItemImpl = (key: string) => null;
  });

  it("should handle logout functionality", async () => {
    const user = userEvent.setup();

    renderWithProviders(<Navbar {...defaultProps} />);

    await user.click(screen.getByRole("button", { name: /open account menu/i }));

    await waitFor(() => {
      expect(screen.getByText("test-user")).toBeInTheDocument();
    });

    // Click logout
    await user.click(screen.getByText("Logout"));

    const cookieUtils = vi.mocked(await import("@/utils/cookieUtils"));
    expect(cookieUtils.clearTokenCookies).toHaveBeenCalled();
    await waitFor(() => {
      expect(window.location.href).toBe("https://example.com/logout");
    });
  });

  it("should not render dark mode toggle slider", () => {
    renderWithProviders(<Navbar {...defaultProps} />);

    // DO NOT RENDER THIS UNTIL ALL COMPONENTS ARE CONFIRMED TO SUPPORT DARK MODE STYLES. IT IS AN ISSUE IF THIS TEST FAILS.
    expect(screen.queryByTestId("dark-mode-toggle")).not.toBeInTheDocument();
  });
});
