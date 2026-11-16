// WB-10 · Workbench › Connect (W-01-T12). One test per artboard a–i on its fixture scenario
// (fixtures/scenarios/connect.ts, W-01-T03): the counts (53 = 9 + 38 + 6 at E0, 55 at E2), the
// category totals that never move with search or status, Hannah's disabled Enable that states its
// reason from the keyboard (aria-disabled, focusable, aria-describedby), Connecting in a status
// region, Reconnect on Needs reauth. Axe runs in e2e/screens.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { WB10, isStepUp } from ".";
import { OPENS, STATES, type Wb10State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Wb10State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <WB10 initial={OPENS[state]} />
    </QueryClientProvider>,
  );
}

function tiles(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("[data-connect-tile]")];
}

function names(): string[] {
  return tiles().map(
    (t) => t.parentElement?.querySelector("p[title]")?.getAttribute("title") ?? "",
  );
}

function tile(key: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-key="${key}"]`)?.closest("li");
  if (!found) throw new Error(`no tile ${key}`);
  return found;
}

/** The CategoryList as label → count. */
function categoryCounts(): Record<string, number | undefined> {
  const out: Record<string, number | undefined> = {};
  const list = screen.getByRole("listbox", { name: "Categories" });
  for (const option of within(list).getAllByRole("option")) {
    const count = option.querySelector("[data-count]")?.textContent;
    const label = option.querySelector("span span")?.textContent ?? "";
    out[label] = count == null ? undefined : Number(count);
  }
  return out;
}

async function loaded(): Promise<void> {
  await waitFor(() => {
    expect(document.querySelector("[data-catalog-grid][aria-busy='true']")).toBeNull();
    expect(tiles().length).toBeGreaterThan(0);
  });
}

const E0_TOTALS = {
  All: 53,
  "Tax Software": 8,
  "Practice Management": 5,
  "ERP & Accounting": 8,
  "Document Management": 13,
  Communications: 8,
  Productivity: 12,
  CRM: 3,
  "HRIS & Payroll": 3,
  "Spend & Payments": 5,
};

describe("WB-10 Workbench › Connect", () => {
  it("has a scenario and an opening for every artboard", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g", "h", "i"]);
  });

  it("a: 53 tiles at E0, the canvas's category totals", async () => {
    show("a");
    await loaded();
    expect(tiles()).toHaveLength(53);
    const counts = categoryCounts();
    for (const [label, n] of Object.entries(E0_TOTALS)) {
      if (label in counts) expect(counts[label]).toBe(n);
    }
    expect(counts.All).toBe(53);
  });

  it("b: ERP lists its 8", async () => {
    show("b");
    await loaded();
    expect(tiles()).toHaveLength(8);
    expect(names()).toEqual(
      expect.arrayContaining(["QuickBooks Online", "NetSuite", "Sage Intacct", "Xero"]),
    );
  });

  it("c: Connected lists the 9; the category totals stay the catalogue's", async () => {
    show("c");
    await loaded();
    expect(tiles()).toHaveLength(9);
    expect(categoryCounts().All).toBe(53);
  });

  it("d: Hannah's firm Enable is aria-disabled, focusable, and says who manages it", async () => {
    show("d");
    await loaded();
    const ultratax = tile("ultratax");
    const enable = within(ultratax).getByRole("button", { name: "Enable" });
    expect(enable.getAttribute("aria-disabled")).toBe("true");
    expect((enable as HTMLButtonElement).disabled).toBe(false);
    const reason = document.getElementById(enable.getAttribute("aria-describedby") ?? "");
    expect(reason?.textContent).toBe("Felix Andersen manages firm connections.");
  });

  it("e: Google Workspace reads Connecting… in a status region", async () => {
    show("e");
    await loaded();
    expect(within(tile("gws")).getByRole("status").textContent).toContain("Connecting…");
  });

  it("f: on Aug 17 CCH Axcess Tax needs reauth, with Reconnect", async () => {
    show("f");
    await loaded();
    const cch = tile("cch");
    expect(cch.textContent).toContain("Needs reauth");
    expect(within(cch).getByRole("button", { name: "Reconnect" })).toBeTruthy();
  });

  it('g: "Karbon" finds one Practice Management tile; the counts do not move', async () => {
    show("g");
    await loaded();
    expect(names()).toEqual(["Karbon"]);
    expect(categoryCounts()["Practice Management"]).toBe(5);
  });

  it("h: E2 lists 55 with GRC & Compliance", async () => {
    show("h");
    await loaded();
    expect(tiles()).toHaveLength(55);
    expect(categoryCounts()["GRC & Compliance"]).toBe(2);
  });

  it("i: GRC & Compliance lists Drata and Vanta", async () => {
    show("i");
    await loaded();
    expect(names()).toEqual(["Drata", "Vanta"]);
  });

  it("a coming-soon tile offers Notify me", async () => {
    show("a");
    await loaded();
    expect(within(tile("adp")).getByRole("button", { name: "Notify me" })).toBeTruthy();
  });

  it("AC-7: only a stale second factor's refusal steps up", () => {
    expect(isStepUp({ detail: "forbidden", facts: { reason: "mfa_required" } })).toBe(true);
    expect(isStepUp({ detail: "forbidden" })).toBe(false);
    expect(isStepUp({ detail: "invalid_state" })).toBe(false);
    expect(isStepUp(null)).toBe(false);
  });
});
