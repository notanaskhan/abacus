// KNW-04 · Firm standards & thresholds (K-02-T13; SPEC-500 AC-13, AC-14). One test per read
// artboard a–h on its fixture scenario, with the handoff's footings (20,020 within threshold and
// 14,900 held; 224 TY2025 returns; Northwind decided, Granite Peak blocked), the staff view
// without the draft (US-3.4), the designed empty examples state (US-3.1) and the flag-off frame.
// Axe, parity and the journeys are K-02-T19's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { KNW04 } from ".";
import { type Knw04State, OPENS, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Knw04State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <KNW04 initial={OPENS[state]} />
    </QueryClientProvider>,
  );
}

async function table(name: string): Promise<HTMLElement> {
  return screen.findByRole("table", { name });
}

function rowsOf(t: HTMLElement): string[][] {
  return within(t)
    .getAllByRole("row")
    .slice(1)
    .map((r) =>
      within(r)
        .queryAllByRole("cell")
        .map((c) => c.textContent),
    );
}

describe("KNW-04 a (Priya Raman, AJE thresholds)", () => {
  it("shows BH AJE thresholds v2 with its seven rows, published Jan 20, 2026 by Priya Raman", async () => {
    show("a");
    const t = await table("BH AJE thresholds v2");
    expect(rowsOf(t)).toEqual([
      ["Payroll accruals", "$15,000", "Senior or above, as one batch"],
      ["Other accrued expenses", "$10,000", "Senior or above, as one batch"],
      ["Prepaid expenses", "$10,000", "Senior or above, as one batch"],
      ["Depreciation", "$10,000", "Senior or above, as one batch"],
      ["Deferred revenue", "$10,000", "Senior or above, as one batch"],
      ["All other classes", "Review required", "Manager or partner"],
      ["Attest clients", "Always held", "Partner"],
    ]);
    expect(screen.getByText("Published Jan 20, 2026 · Priya Raman")).toBeTruthy();
    expect(document.querySelector("[data-version-chip]")?.textContent).toBe("v2");
  });

  it("foots Copperleaf's August entries: 4 within (20,020) by Raj Malhotra, 1 held (14,900)", async () => {
    show("a");
    await table("How v2 sorted the August 2026 closes");
    await waitFor(() => {
      expect(document.querySelector("[data-total='within']")?.textContent).toBe(
        "4 within threshold · 20,020 · approved as one batch by Raj Malhotra",
      );
    });
    expect(document.querySelector("[data-total='held']")?.textContent).toBe(
      "1 held · 14,900 · approved by Priya Raman",
    );
  });

  it("keeps the policy toggle off and display-only; New version… is the owner's (K-02-T14)", async () => {
    show("a");
    await table("BH AJE thresholds v2");
    const toggle = screen.getByRole("switch", {
      name: "Let the policy accept within-threshold entries without a person (logged as ‘Policy: BH AJE thresholds v2’)",
    });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect((toggle as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "New version…" }).disabled).toBe(
      false,
    );
  });

  it("shows the Versions timeline: v2 current, v1 superseded", async () => {
    show("a");
    const versions = await screen.findByRole("list", { name: "Versions" });
    expect(versions.textContent).toContain("Published (current)");
    expect(versions.textContent).toContain("Superseded");
  });
});

describe("KNW-04 b (Review checklists)", () => {
  it("lists six TY2025 checklists applied to 224 returns, the 1065 run card and the draft", async () => {
    show("b");
    const t = await table("Review checklists");
    const rows = rowsOf(t);
    expect(rows.slice(0, 6).map((r) => r[0])).toEqual([
      "1040 Review Checklist",
      "1065 Review Checklist",
      "1120-S Review Checklist",
      "1120 Review Checklist",
      "1041 Review Checklist",
      "990 Review Checklist",
    ]);
    expect(rows[1]).toEqual(["1065 Review Checklist", "42", "v4", "38 returns", "Daniel Reyes"]);
    expect(rows[6]?.[3]).toBe("224 TY2025 returns");
    expect(rows[7]?.[0]).toBe("1040 Review Checklist v7 (TY2026)");
    const card = await screen.findByRole("region", { name: "Firm standards" });
    expect(card.textContent).toContain(
      "1065 Review Checklist v4 · last run started 9:18 AM · Samuel Ito",
    );
    expect(card.textContent).toContain("2 exceptions");
    expect(card.textContent).toContain("3 exceptions");
    expect(card.textContent).toContain("Running… 31 of 42");
    expect(screen.getByText("Published · owner Daniel Reyes")).toBeTruthy();
  });

  it("hides the draft from Cole Hart (staff, US-3.4)", async () => {
    show("draft_hidden");
    const t = await table("Review checklists");
    expect(rowsOf(t).some((r) => r[0]?.includes("v7"))).toBe(false);
  });
});

describe("KNW-04 c–h", () => {
  it("c: three tiers of sign-off", async () => {
    show("c");
    const rows = rowsOf(await table("BH review levels v2"));
    expect(rows.map((r) => r[1])).toEqual([
      "Preparer (L1) → Reviewer (L2)",
      "+ Manager (L3)",
      "+ Partner (L4) + second-partner review",
    ]);
  });

  it("d: BH-TAX-02 applies to four clients → Daniel Reyes", async () => {
    show("d");
    await waitFor(() => {
      expect(
        screen.getByText(
          "Jonah & Claire Feld · Ridgeline Property Partners, LP · Calloway Family Trust · Marcus & Dana Whitley → Daniel Reyes",
        ),
      ).toBeTruthy();
    });
    expect(document.querySelector("[data-version-chip]")?.textContent).toBe("BH-TAX-02");
  });

  it("e: variance v3, both legs exceeded, with the Copperleaf R&M example", async () => {
    show("e");
    const rows = rowsOf(await table("BH variance thresholds v3"));
    expect(rows[0]).toEqual(["Close flux", "10%", "$2,500", "Both must be exceeded"]);
    expect(await screen.findByText(/Copperleaf repairs & maintenance 3,200 vs 640/u)).toBeTruthy();
  });

  it("f: materiality v2 foots; Northwind decided, Granite Peak blocked on Margaret Okonkwo", async () => {
    show("f");
    const rows = rowsOf(await table("Engagements"));
    expect(rows[0]?.slice(1, 4)).toEqual(["$252,200", "75% · $189,150", "5% · $12,610"]);
    expect(rows[1]?.slice(1, 4)).toEqual(["$155,000", "75% · $116,250", "5% · $7,750"]);
    expect(rows[0]?.[4]).toContain("Decided");
    expect(rows[1]?.[4]).toContain("Blocked on a partner decision");
    expect(rows[1]?.[4]).toContain("Waiting on Margaret Okonkwo");
  });

  it("g: hold below 90%; auto-accept above 98% stays off", async () => {
    show("g");
    expect(await screen.findByText("Below 90% confidence")).toBeTruthy();
    expect(screen.getByText("Above 98% confidence · off")).toBeTruthy();
  });

  it("h: SSARS 27 not adopted; Copperleaf August is an AR-C 70 preparation", async () => {
    show("h");
    expect(await screen.findByText("AR-C 70 preparation")).toBeTruthy();
    const toggle = screen.getByRole("switch", {
      name: "Early-adopt SSARS 27 for CAS monthly statements",
    });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
  });
});

describe("KNW-04 conditions", () => {
  it("shows the designed empty state, never invented rows, when no provider is registered", async () => {
    show("no_examples");
    await table("BH AJE thresholds v2");
    expect(await screen.findByText("No examples yet")).toBeTruthy();
    expect(document.querySelector("[data-total]")).toBeNull();
  });

  it("draws the T12 frame with the not-turned-on state when the flag is off (AC-14)", async () => {
    show("flag_off");
    await waitFor(() => {
      expect(document.querySelector("[data-flag-off='knowledge.firm_standards']")).not.toBeNull();
    });
    expect(screen.getByRole("navigation", { name: "Sections" })).toBeTruthy();
  });
});
