// C-02-T17 (TASK-8637, DEC-5637): CLS-07 in fixture mode. Row acceptance: "CLS-07a, a2, b and c
// render from fixtures at Tier C and the batch modal reads 'Approve 4 under BH AJE thresholds v2'
// with $20,020.00."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { CLOSE_WORK_ITEM_ID, closeEntries, lineCount } from "../../fixtures/seed/cls07";
import exported from "../../fixtures/seed/scenario.cls07-entries.json";
import { newQueryClient } from "../../testing/support";
import { CLS07, type CLS07Props } from "./index";
import { type Cls07State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Cls07State, props: Partial<CLS07Props> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CLS07
        workItemId={CLOSE_WORK_ITEM_ID}
        periodLabel="August 2026"
        lineCount={lineCount}
        approver={{ userId: "u-priya", name: "Priya Raman" }}
        {...props}
      />
    </QueryClientProvider>,
  );
}

async function rows(): Promise<HTMLElement[]> {
  await waitFor(() => {
    expect(document.querySelector("[data-entry='AJE-01']")).not.toBeNull();
  });
  return [...document.querySelectorAll<HTMLElement>("[data-entry]")];
}

describe("CLS-07 Adjustments & thresholds", () => {
  it("the fixture is the Python scenario's: 11,860 + 700 + 2,140 + 5,320 = 20,020; + 14,900 = 34,920", () => {
    const a = closeEntries("a");
    expect(a.tallies.within_threshold).toEqual({ count: 4, amount: "20020.00" });
    expect(a.tallies.review_required).toEqual({ count: 1, amount: "14900.00" });
    expect(a.tallies.proposed).toEqual({ count: 5, amount: "34920.00" });
    expect(closeEntries("c").tallies.proposed.amount).toBe("35300.00");
    expect(a.items.map((r) => r.ref)).toEqual(exported.entries.slice(0, 5).map((e) => e.ref));
  });

  it("a: four within threshold, AJE-05 held, Approve 4 within threshold under Raj", async () => {
    show("a");
    const list = await rows();
    expect(list).toHaveLength(5);
    expect(list.filter((r) => r.dataset.status === "within_threshold")).toHaveLength(4);
    expect(screen.getByText("> $10,000 other accruals")).toBeTruthy();
    expect(screen.getByText("≤ $15,000 payroll accruals")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Approve 4 within threshold" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Approve — Manager or Partner" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(screen.getByRole("button", { name: "Request approval from Priya Raman" })).toBeTruthy();
    expect(screen.queryByText(/Send to client/)).toBeNull();
  });

  it("a2: the batch modal reads 'Approve 4 under BH AJE thresholds v2' with $20,020.00", async () => {
    show("a2", { initial: { batchOpen: true } });
    await rows();
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getAllByText("Approve 4 under BH AJE thresholds v2").length).toBeGreaterThan(0);
    expect(within(dialog).getByText("$20,020.00")).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Approve adjustments" })).toBeTruthy();
  });

  it("b: four approved in Raj's name, 4 of 5, Post 4 approved… while AJE-05 waits", async () => {
    show("b");
    await rows();
    expect(screen.getAllByText("Approved by RM under BH AJE thresholds v2 · 9:31 AM")).toHaveLength(4);
    expect(screen.getByText("4 of 5")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Post 4 approved…" })).toBeTruthy();
  });

  it("c: Priya approves the held entry; AJE-06 from the reconciliation joins", async () => {
    show("c", { initial: { selected: "AJE-05" } });
    const list = await rows();
    expect(list.map((r) => r.dataset.entry)).toContain("AJE-06");
    expect(screen.getByRole("button", { name: "Approve" })).toBeTruthy();
    expect(screen.getByText("Inventory — Green Coffee")).toBeTruthy();
  });

  it("g: the attest client shows no Post control, only Send to client for approval…", async () => {
    show("g");
    await rows();
    expect(screen.queryByRole("button", { name: /^Post/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Send to client for approval…" })).toBeTruthy();
  });
});
