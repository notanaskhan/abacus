// ENG-13 in a production build (P-07-T60): "production shows only the v1 carry categories".
// PLANNED_VISIBLE folds to false in production, so the handoff's attest and structure rows, the
// bridge-letter toggle, learned context and the template conflicts are never drawn, even when a
// preview is passed; "Create & draft letter" (N-02) is not drawn either.
import { client } from "@abacus/api-client/client";
import { cleanup, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { ENG13 } from ".";
import { type Eng13State, OPENS, PREVIEWS, freshScenario } from "./scenarios";

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

function show(state: Eng13State, step: "carry" | "template" | "review"): void {
  restore = installFixtureMode(freshScenario(state));
  renderRoutes([
    {
      path: "/",
      component: () => (
        <ENG13
          sourceId={OPENS[state].source}
          draftId={OPENS[state].draft}
          initialStep={step}
          preview={PREVIEWS[state]}
        />
      ),
    },
  ]);
}

describe("ENG-13 production build", () => {
  it("What to carry draws the four v1 rows and nothing from the preview", async () => {
    show("a", "carry");
    await screen.findByRole("heading", { name: /What to carry into SOC 2 Type 2/ });
    expect(screen.getAllByRole("tablist").map((t) => t.getAttribute("aria-label"))).toEqual([
      "Carry or skip Team",
      "Carry or skip Template version",
      "Carry or skip Request list",
      "Carry or skip Prior-year notes",
    ]);
    expect(document.querySelector("[data-preview]")).toBeNull();
    expect(screen.queryByText("Scope and controls")).toBeNull();
    expect(screen.queryByText(/learned-context/)).toBeNull();
    const card = screen.getByRole("region", { name: "Carrying" });
    expect(card.textContent).toContain("212 requests as Draft");
    expect(card.textContent).not.toContain("213");
    expect(card.textContent).toContain("0 evidence copied");
  });

  it("the Northwind source shows only its v1 rows", async () => {
    show("d", "carry");
    await screen.findByText("24, as Draft; the client sees nothing until you send");
    expect(screen.queryByText(/26 workpapers/)).toBeNull();
    expect(screen.getAllByRole("tablist")).toHaveLength(4);
  });

  it("a changed template draws no conflicts and never holds Next", async () => {
    show("c", "template");
    await screen.findByText("BH Audit Methodology · FS");
    expect(screen.queryByText(/Template changed since FY2026/)).toBeNull();
    expect(screen.getByText("Nothing to reconcile.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Next" }).hasAttribute("disabled")).toBe(false);
  });

  it("Review offers Create only; Create & draft letter waits for N-02", async () => {
    show("e", "review");
    await screen.findByRole("button", { name: "Create" });
    expect(screen.queryByRole("button", { name: "Create & draft letter" })).toBeNull();
  });
});
