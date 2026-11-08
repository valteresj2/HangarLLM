import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderWithProviders, screen } from "../../../tests/test-utils";
import PremiumLoggingSettings from "./PremiumLoggingSettings";

describe("PremiumLoggingSettings", () => {
  it("renders the logging editor without a premium flag", () => {
    renderWithProviders(<PremiumLoggingSettings value={[]} onChange={vi.fn()} />);

    expect(screen.getByText("Logging Integrations")).toBeInTheDocument();
  });
});
