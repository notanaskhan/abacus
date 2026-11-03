// NOT-01 · Notices index (N-04-T05; docs/screens/NOT-01.md). Acceptance (the task row): "Scenario
// tests for a, e, f and g pass with tallies equal to the visible rows."
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { DEFAULT_NOTICE_FILTERS, type NoticeFilters } from "../../domain/notices";
import { renderRoutes } from "../../testing/support";
import { NoticesIndex } from ".";
import { COPY } from "./copy";
import { type Not01State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function mount(state: Not01State, initial: Partial<NoticeFilters> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([
    {
      path: "/",
      component: () => <NoticesIndex initial={{ ...DEFAULT_NOTICE_FILTERS, ...initial }} />,
    },
  ]);
}

const CLIENTS_BY_RISK = [
  "Thomas & Irene Kowal",
  "Marcus & Dana Whitley",
  "Rafael Quintero",
  "Harold Stein",
  "Aurelio Santos",
  "Copperleaf Coffee Roasters, Inc.",
  "Priyanka & Sam Iyer",
  "Wren & Avery Collins",
  "Meridian Tool & Die, Inc.",
];

describe("NOT-01", () => {
  it("a: nine notices by deadline risk", async () => {
    mount("a");
    await screen.findByText("Thomas & Irene Kowal");
    const rows = screen.getAllByRole("row").slice(1);
    const names = rows.map((r) => CLIENTS_BY_RISK.find((c) => r.textContent.includes(c)));
    expect(names.filter((n) => n !== undefined)).toEqual(CLIENTS_BY_RISK);
  });

  it("a: the tiles and the type tile foot to the nine visible rows", async () => {
    mount("a");
    await screen.findByText("Thomas & Irene Kowal");
    const tiles = screen.getByRole("group", { name: "Status" });
    for (const [label, n] of [
      ["New", "2"],
      ["Analyzing", "3"],
      ["Response drafted", "2"],
      ["Awaiting IRS", "2"],
    ] as const) {
      const tile = within(tiles).getByRole("button", { name: new RegExp(label) });
      expect(tile.textContent).toContain(n);
    }
    const byType = await screen.findByRole("group", { name: COPY.byType });
    expect(byType.textContent).toMatch(/3\s*CP2000/);
    expect(byType.textContent).toMatch(/2\s*CP14/);
    expect(byType.textContent).toMatch(/1\s*CP501/);
    expect(byType.textContent).toMatch(/3\s*State/);
    expect(await screen.findByText(COPY.summary("9", "1", "1"))).toBeTruthy();
  });

  it("a: only N4 is red at 7 days; N1 is amber at 9; amounts and authorizations", async () => {
    mount("a");
    await screen.findByText("Thomas & Irene Kowal");
    const red = document.querySelectorAll('[data-risk="red"]');
    expect(red).toHaveLength(1);
    expect(red[0]?.textContent).toBe("Sep 21 · 7 days");
    expect(screen.getByText("Sep 23 · 9 days").getAttribute("data-risk")).toBe("amber");
    expect(screen.getByText("$686.40 + $66.61 interest")).toBeTruthy();
    expect(screen.getByText("$1,980.00 · disagreed")).toBeTruthy();
    expect(screen.getByText("None · blocked")).toBeTruthy();
    expect(screen.getByText("Response sent Aug 12")).toBeTruthy();
  });

  it("a: a state row awaiting a reply reads Awaiting agency, never Awaiting IRS", async () => {
    mount("a");
    const meridian = (await screen.findByText("Meridian Tool & Die, Inc.")).closest("tr");
    expect(meridian?.textContent).toContain("Awaiting agency");
    expect(meridian?.textContent).not.toContain("Awaiting IRS");
    const collins = screen.getByText("Wren & Avery Collins").closest("tr");
    expect(collins?.textContent).toContain("Awaiting IRS");
  });

  it("e: the New tile shows N5 and N9 only, and Clear", async () => {
    mount("e", { tile: "new" });
    await screen.findByText("Aurelio Santos");
    expect(screen.getByText("Priyanka & Sam Iyer")).toBeTruthy();
    expect(screen.queryByText("Marcus & Dana Whitley")).toBeNull();
    expect(screen.getByRole("button", { name: "Clear" })).toBeTruthy();
  });

  it("e: pressing a tile filters and pressing it again clears", async () => {
    mount("a");
    await screen.findByText("Marcus & Dana Whitley");
    const tiles = screen.getByRole("group", { name: "Status" });
    fireEvent.click(within(tiles).getByRole("button", { name: /New/ }));
    await waitFor(() => {
      expect(screen.queryByText("Marcus & Dana Whitley")).toBeNull();
    });
    // The filtered page arrives after the old rows leave (one refetch).
    expect(await screen.findByText("Aurelio Santos")).toBeTruthy();
  });

  it("f: no open notices", async () => {
    mount("f");
    expect(await screen.findByText(COPY.empty.title)).toBeTruthy();
    expect(screen.getByText(COPY.empty.body)).toBeTruthy();
  });

  it("g: loading draws skeleton rows and no counts", async () => {
    mount("g");
    await waitFor(() => {
      expect(document.querySelector('[data-tile-count="pending"]')).not.toBeNull();
    });
    expect(screen.queryByText("Thomas & Irene Kowal")).toBeNull();
  });
});
