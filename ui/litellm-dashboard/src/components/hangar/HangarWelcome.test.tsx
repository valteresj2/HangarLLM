import React from "react";
import { describe, expect, it } from "vitest";
import { renderWithProviders, screen, within } from "../../../tests/test-utils";
import { uiHref } from "@/utils/uiHref";
import { HangarWelcome } from "./HangarWelcome";

describe("HangarWelcome", () => {
  it("links each quick action to its dashboard page", () => {
    renderWithProviders(<HangarWelcome />);

    const links = within(screen.getByRole("navigation", { name: "Hangar quick links" }));
    expect(links.getByRole("link", { name: "Models" })).toHaveAttribute("href", uiHref("models-and-endpoints"));
    expect(links.getByRole("link", { name: "Agents" })).toHaveAttribute("href", uiHref("agents"));
    expect(links.getByRole("link", { name: "MCP servers" })).toHaveAttribute("href", uiHref("mcp-servers"));
    expect(links.getByRole("link", { name: "Guardrails" })).toHaveAttribute("href", uiHref("guardrails"));
  });
});
