// C-01-T36 (TASK-8419): CLS-09 Close plan editor a–f in fixture mode. Row acceptance: "Tallies
// reflow on edit, Raj Malhotra sees Request publish while Priya Raman sees Publish v4, and drafted
// rows cannot be published until adopted."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { copperleafPlan, copperleafPlanDraftV4 } from "../../fixtures/seed/close-book";
import { newQueryClient } from "../../testing/support";
import { CLS09, accountsOf, groupsOf } from "./index";
import { INITIAL, type PlanState, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const COPPERLEAF = "00000000-0000-4000-8000-00000000c001";

function show(state: PlanState): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CLS09
        clientId={COPPERLEAF}
        clientName="Copperleaf Coffee Roasters, Inc."
        initial={INITIAL[state]}
      />
    </QueryClientProvider>,
  );
}

async function ready(): Promise<void> {
  await waitFor(() => {
    expect(document.querySelector("[data-row]")).not.toBeNull();
  });
}

describe("CLS-09 Close plan editor", () => {
  it("counts tie: 21 accounts, 23 = Manager 8 + Senior 15, 8 requests", () => {
    const v3 = copperleafPlan();
    expect(accountsOf(v3.rows)).toBe(21);
    expect(v3.tally).toMatchObject({
      procedures: 23,
      manager: 8,
      senior: 15,
      requests_per_month: 8,
    });
    expect(groupsOf(v3.rows, "class").map((g) => g.key)[0]).toBe("Bank");
  });

  it("a: published v3 is read-only until Edit plan; Publish v4 waits", async () => {
    show("a");
    await ready();
    expect(screen.getByText("Close plan v3")).toBeTruthy();
    expect(screen.getByText("Published Jun 2, 2026 by Priya Raman")).toBeTruthy();
    expect(screen.getByText("8 / month")).toBeTruthy();
    expect(document.querySelectorAll("[data-row]").length).toBe(23);
    const publish = screen.getByRole("button", { name: "Publish v4" });
    expect((publish as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getAllByText("Difference $0.00").length).toBeGreaterThan(0);
  });

  it("a2: hovering a row shows its label-over-value card", async () => {
    show("a2");
    await ready();
    expect(document.querySelector("[data-hover-card] [data-plan-card]")).not.toBeNull();
  });

  it("a3: a row opens the O2 drawer titled with the account", async () => {
    show("a3");
    await ready();
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeTruthy();
    });
    expect(screen.getAllByText("Operating Checking (Front Range Bank) ••4410").length).toBe(2);
  });

  it("b: Raj's draft v4 reflows to 7 requests and offers only Request publish…", async () => {
    expect(copperleafPlanDraftV4("RM").tally.requests_per_month).toBe(7);
    show("b");
    await ready();
    expect(screen.getByText("Draft v4 · 1 change")).toBeTruthy();
    expect(screen.getByText("7 / month")).toBeTruthy();
    expect(document.querySelectorAll("[data-changed]").length).toBe(1);
    expect(screen.getByRole("button", { name: "Request publish…" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Publish v4" })).toBeNull();
  });

  it("b2: Priya publishes v4 from the September close", async () => {
    show("b2");
    await ready();
    await waitFor(() => {
      expect(
        screen.getByText("It applies from the September 2026 close; August stays on v3."),
      ).toBeTruthy();
    });
  });

  it("c: drafted rows carry an outlined tick and the plan cannot publish until adopted", async () => {
    show("c");
    await ready();
    expect(screen.getByText("Draft v1 · Close Planner")).toBeTruthy();
    expect(document.querySelectorAll("[data-adopt]").length).toBe(23);
    expect(document.querySelector("[data-drafting]")?.textContent).toContain("15 of 21 accounts");
    const publish = screen.getByRole("button", { name: "Publish v1" });
    expect((publish as HTMLButtonElement).disabled).toBe(true);
  });

  it("d: no plan yet shows the four templates and Draft from ledger history", async () => {
    show("d");
    await waitFor(() => {
      expect(screen.getByText("No close plan yet")).toBeTruthy();
    });
    await waitFor(() => {
      expect(document.querySelectorAll("[data-template]").length).toBe(4);
    });
    expect(screen.getByRole("button", { name: "Draft from ledger history" })).toBeTruthy();
  });

  it("e: Requests lists the eight templates with business-day due dates", async () => {
    show("e");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-request-template]").length).toBe(8);
    });
    expect(screen.getAllByText("BD 3").length).toBe(8);
  });

  it("f: History reads v3, v2 and the Close Planner's v1", async () => {
    show("f");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-history]").length).toBe(3);
    });
    expect(screen.getByText("Drafted Mar 5, 2026 · Close Planner via Raj Malhotra")).toBeTruthy();
  });
});
