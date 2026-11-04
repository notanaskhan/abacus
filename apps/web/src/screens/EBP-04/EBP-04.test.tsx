// A-05-T31 (TASK-3277): EBP-04 a, b, d, e, f in fixture mode. Row acceptance: "Every amount foots on
// screen, the Dec 26 row shows 9 business days, and state f reads 'Corrected Sep 30' only after a
// person records the correction." Figures are the handoff's (seed/ebp04.ts).
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { newQueryClient } from "../../testing/support";
import { AuditCockpitPage } from "../AUD-02";
import { type Ebp04State, TAB_OF, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Ebp04State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AuditCockpitPage
        auditId={NORTHWIND_AUDIT}
        initial={{ section: "ebp_04", contributions: { tab: TAB_OF[state] } }}
      />
    </QueryClientProvider>,
  );
}

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

describe("EBP-04", () => {
  it("a: the waterfall foots from the server to $1,366,900.00", async () => {
    show("a");
    const a = await drawn("[data-ebp04='card-a']");
    await waitFor(() => {
      expect(a.querySelector("[data-figure='total']")?.textContent).toContain("$1,366,900.00");
    });
    expect(a.querySelector("[data-figure='total_payroll']")?.textContent).toContain(
      "$1,270,500.00",
    );
    expect(a.querySelector("[data-figure='less_late']")?.textContent).toContain("($48,600.00)");
    expect(a.querySelector("[data-figure='total_trust']")?.textContent).toContain("$1,318,300.00");
    expect(
      a.querySelector("[data-figure='receivable_aje1'] [data-entry-status]")?.textContent,
    ).toBe("Proposed to client");
    const tally = await drawn("[data-ebp04='tally']");
    expect(tally.textContent).toContain("1 late");
    expect(tally.textContent).toContain("64.38");
    expect(tally.textContent).toContain("48,600.00");
    expect(tally.querySelectorAll("[data-tally^='tie.']").length).toBe(3);
  });

  it("a: the Dec 26 row shows 9 business days; 25 of 26 on practice", async () => {
    show("a");
    const b = await drawn("[data-ebp04='card-b']");
    await waitFor(() => {
      expect(b.querySelectorAll("[data-dot]").length).toBe(26);
    });
    expect(b.querySelectorAll("[data-dot][data-late='true']").length).toBe(1);
    const late = b.querySelector("[data-payroll='2025-12-26']");
    expect(late?.textContent).toContain("9");
    expect(late?.textContent).toContain("Late");
    expect(b.querySelector("[data-ebp04='practice']")?.textContent).toContain(
      "Established practice: 2 business days (25 of 26).",
    );
    const c = await drawn("[data-ebp04='card-c'][data-status='found']");
    expect(c.querySelector("[data-ebp04='days']")?.textContent).toBe("10 · 9 business days");
    expect(c.textContent).toContain("$64.38");
    expect(c.textContent).toContain("Pending — VFCP Self-Correction Component");
  });

  it("b: Timeliness lists all 26 payrolls", async () => {
    show("b");
    const table = await drawn("[data-ebp04='payrolls']");
    await waitFor(() => {
      expect(table.querySelectorAll("[data-payroll]").length).toBe(26);
    });
  });

  it("d: agent running: tallies Pending and Card A a skeleton", async () => {
    show("d");
    const tally = await drawn("[data-ebp04='tally']");
    await waitFor(() => {
      expect(tally.textContent).toContain("Pending");
    });
    expect(document.querySelector("[data-ebp04='card-a'] [data-figure]")).toBeNull();
  });

  it("e: AJE-1 reads Client approved", async () => {
    show("e");
    const pill = await drawn("[data-figure='receivable_aje1'] [data-entry-status]");
    expect(pill.textContent).toBe("Client approved");
  });

  it("f: Corrected comes from the recorded correction, with Form 5330 not required", async () => {
    show("f");
    const c = await drawn("[data-ebp04='card-c'][data-status='corrected']");
    expect(c.querySelector("[data-correction='corrected']")?.textContent).toContain("Corrected");
    expect(c.textContent).toContain("Not required — excise tax relieved under PTE 2002-51");
    expect(c.querySelector("[data-line='fully_corrected']")?.textContent).toContain("33,540");
    expect(c.querySelector("[data-line='pending_vfcp']")?.textContent).toContain("—");
  });

  it("a: the default clock never reads Corrected", async () => {
    show("a");
    const c = await drawn("[data-ebp04='card-c']");
    expect(c.textContent).not.toContain("Corrected");
  });
});

// A-05-T32 (TASK-3278). Row acceptance: "Rows 8 and 15 open their EBP-03 rows, and no recalculated
// match exceeds 3.5% of compensation."
describe("EBP-04 c · Testing (A-05-T32)", () => {
  it("rows 8 and 15 link to EBP-03; no recalculated match exceeds 3.5% of compensation", async () => {
    show("c");
    const grid = await drawn("[data-ebp04='testing']");
    await waitFor(() => {
      expect(grid.querySelectorAll("[data-test-row]").length).toBe(25);
    });
    const linked = [...grid.querySelectorAll<HTMLElement>("[data-test-row]")]
      .filter((r) => r.querySelector("[data-link='EBP-03']") !== null)
      .map((r) => r.dataset.testRow);
    expect(linked).toEqual(["8", "15"]);
    const { ebp04Test } = await import("../../fixtures/seed/ebp04");
    for (const row of ebp04Test().rows) {
      const comp = Number(row.cells.find((c) => c.attribute_key === "compensation")?.expected);
      const match = Number(row.cells.find((c) => c.attribute_key === "match")?.expected);
      expect(match).toBeLessThanOrEqual(comp * 0.035 + 0.005);
    }
  });
});
