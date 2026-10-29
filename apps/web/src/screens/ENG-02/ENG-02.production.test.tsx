// ENG-02 in a production build (P-07-T28): "the production build shows only the live tabs".
// PLANNED_VISIBLE folds to false in production, so the Dashboard, Board and Budget tabs and the
// gear are not drawn at all; Overview, Work items, Team and Letter & terms remain, and P-07-T61
// adds the live Activity tab (DEC-822).
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ENG02 } from ".";
import { OPENS, scenarios } from "./scenarios";

vi.mock("../../app-core/planned", () => ({ PLANNED_VISIBLE: false }));

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

describe("ENG-02 production build", () => {
  it("shows only the live tabs: Overview · Work items · Team · Letter & terms · Activity; no gear", async () => {
    restore = installFixtureMode(scenarios.a);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <ENG02 engagementId={OPENS.a} tab="overview" onTab={() => undefined} />
      </QueryClientProvider>,
    );
    await screen.findByRole("heading", { name: /2026 Close/ });
    const list = screen.getByRole("tablist", { name: "Engagement sections" });
    await waitFor(() => {
      expect(
        within(list)
          .getAllByRole("tab")
          .map((t) => t.textContent),
      ).toEqual(["Overview", "Work items12", "Team3", "Letter & terms", "Activity"]);
    });
    expect(screen.queryByRole("button", { name: "Engagement settings" })).toBeNull();
    expect(screen.queryByText(/Opens ENG-1[02]/)).toBeNull();
  });

  it("a planned tab asked for in production falls back to Overview", async () => {
    restore = installFixtureMode(scenarios.g);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <ENG02 engagementId={OPENS.g} tab="board" onTab={() => undefined} />
      </QueryClientProvider>,
    );
    await screen.findByRole("heading", { name: /2026 Close/ });
    expect(document.querySelector("[data-planned-tab]")).toBeNull();
    const list = screen.getByRole("tablist", { name: "Engagement sections" });
    expect(within(list).getByRole("tab", { name: "Overview" }).getAttribute("aria-selected")).toBe(
      "true",
    );
  });
});
