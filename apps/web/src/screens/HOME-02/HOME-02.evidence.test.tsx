// HOME-02 · the evidence pane (I-01-T18). Acceptance: "Evidence rows open SHL-08 on the cited
// region and the a and c evidence fixtures foot to the figures in the screen contract." The
// footing itself is fixtures/approvals-evidence.foot.test.ts; here the pane lays the figures out
// as given, the detail's source rows open the SHL-08 drawer lit on the citation's match, and the
// small segmented moves between the summary and a source in the E5 viewer.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { DECISION_754_CITATIONS, TRANSFER } from "../../fixtures/seed/approvals-detail";
import "../../routes/firm/sheets"; // registers the `?ov=` keys the panes open
import "../../routes/firm/viewer"; // registers `viewer`, SHL-08
import { newQueryClient } from "../../testing/support";
import { HOME02 } from ".";
import { type Home02State, scenarios, selectedGate, summaryOf } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Home02State): { search: () => Record<string, unknown> } {
  restore = installFixtureMode(scenarios[state]);
  const root = createRootRoute({ component: Outlet });
  const router = createRouter({
    routeTree: root.addChildren([
      createRoute({
        getParentRoute: () => root,
        path: "/",
        component: () => <HOME02 gate={selectedGate(state)} summaryOf={summaryOf} />,
      }),
    ]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { search: () => router.state.location.search as Record<string, unknown> };
}

async function pane(): Promise<HTMLElement> {
  return waitFor(() => {
    const found = document.querySelector<HTMLElement>('[data-home02="evidence"]');
    if (found?.querySelector('[data-home02="summary"]') == null) throw new Error("no summary");
    return found;
  });
}

describe("HOME-02 evidence pane", () => {
  it("a: Basis at 12/31/2025: tally, the table with Pell Street II lit, the calc card", async () => {
    show("a");
    const p = await pane();
    expect(within(p).getByRole("heading", { level: 2 }).textContent).toBe(
      "Basis at 12/31/2025 · Ridgeline",
    );
    expect(p.textContent).toContain("OUTSIDE BASIS");
    expect(p.textContent).toContain("17,943,095");
    expect(p.textContent).toContain("17,914,500");
    expect(p.textContent).toContain("4 of 5");
    const table = within(p).getByRole("table", { name: "Basis at 12/31/2025" });
    const lit = table.querySelectorAll("tr[data-lit]");
    expect(lit).toHaveLength(1);
    expect(lit[0]?.textContent).toContain("Pell Street II LLC");
    expect(lit[0]?.querySelector(".text-match-ink")?.textContent).toBe("913,820");
    const total = [...table.querySelectorAll("tbody tr")].at(-1);
    expect(total?.textContent).toBe("TOTAL6,866,20011,048,30017,943,09517,914,50028,595");
    const calc = p.querySelector('[data-home02="calc"]');
    expect(calc?.textContent).toContain("Purchase price paid by Pell Street II LLC360,000");
    expect(calc?.textContent).toContain("= §743(b) placeholder28,595");
    // The segmented: the summary, then the labelled source.
    expect(
      within(p)
        .getAllByRole("tab")
        .map((t) => t.textContent),
    ).toEqual(["Basis", "Transfer agreement"]);
  });

  it("a: an evidence row in the detail opens SHL-08 on the cited region", async () => {
    const { search } = show("a");
    await pane();
    const row = await waitFor(() => {
      const found = document.querySelector<HTMLButtonElement>('[data-home02="source"]');
      if (found === null) throw new Error("no source rows");
      return found;
    });
    fireEvent.click(row);
    const match = DECISION_754_CITATIONS[0]?.match_id ?? "";
    await waitFor(() => {
      expect(String(search().ov)).toContain(`viewer:${TRANSFER}:`);
    });
    expect(match).not.toBe("");
    expect(decodeURIComponent(String(search().ov))).toContain(match.split("#")[1] ?? "");
  });

  it("a: Transfer agreement shows the source in the E5 viewer with Open source", async () => {
    show("a");
    const p = await pane();
    fireEvent.click(within(p).getByRole("tab", { name: "Transfer agreement" }));
    await waitFor(() => {
      expect(p.querySelector('[data-screen="SHL-08"][data-host="dock"]')).not.toBeNull();
    });
    expect(within(p).getByRole("heading", { level: 2 }).textContent).toContain(
      "Membership interest transfer agreement",
    );
    expect(within(p).getByRole("button", { name: /Open source/u })).toBeTruthy();
  });

  it("c: Capital Accounts: rollforward, Schedule L, off 6,200 and the agent's fix without a control", async () => {
    show("c");
    const p = await pane();
    expect(within(p).getByRole("heading", { level: 2 }).textContent).toBe(
      "Capital Accounts · Ridgeline",
    );
    const table = within(p).getByRole("table", { name: "Capital rollforward · 2025" });
    expect(table.textContent).toContain("Ending capital per rollforward6,860,000");
    expect(table.textContent).toContain("(600,000)");
    expect(p.textContent).toContain("off 6,200");
    const fix = within(p).getByRole("region", {
      name: "Proposed by Accrued Agent · awaits Samuel Ito",
    });
    expect(within(fix).queryAllByRole("button")).toEqual([]);
    expect(fix.querySelector('[data-actor="agent"]')).not.toBeNull();
  });

  it("d: the preparer memo on its paper", async () => {
    show("d");
    const p = await pane();
    const paper = p.querySelector('[data-home02="paper"]');
    expect(paper?.textContent).toContain(
      "Ridgeline Property Partners, LP — 2025 Form 1065 preparer memo",
    );
    expect(paper?.textContent).toContain("Prepared by Olivia Brandt · Reviewed by Samuel Ito");
    expect(paper?.querySelectorAll("p.text-dense")).toHaveLength(4);
  });

  it("g: the K-1 items and what is cited on it", async () => {
    show("g");
    const p = await pane();
    expect(within(p).getByRole("heading", { level: 2 }).textContent).toBe(
      "2025 Schedule K-1 · Feld",
    );
    expect(p.textContent).toContain("Nonpassive");
    expect(
      within(p).getByRole("region", { name: "Cited on the 2025 Schedule K-1" }).textContent,
    ).toContain("Box 2 · Net rental real estate income (loss)");
  });

  it("without an owner's summary a gate shows its cited sources only", async () => {
    restore = installFixtureMode(scenarios.a);
    const root = createRootRoute({ component: Outlet });
    const router = createRouter({
      routeTree: root.addChildren([
        createRoute({
          getParentRoute: () => root,
          path: "/",
          component: () => <HOME02 gate={selectedGate("a")} />,
        }),
      ]),
      history: createMemoryHistory({ initialEntries: ["/"] }),
    });
    render(
      <QueryClientProvider client={newQueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    await waitFor(() => {
      expect(document.querySelector('[data-screen="SHL-08"]')).not.toBeNull();
    });
    expect(document.querySelector('[data-home02="summary"]')).toBeNull();
    expect(screen.getAllByRole("tab").length).toBeGreaterThan(1);
  });
});
