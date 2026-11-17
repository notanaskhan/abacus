import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { AnalyticsWorkspace } from ".";
import { AUD13_SCENARIOS } from "./scenarios";

// A-08-T28 (AUD-13 a to e plus Substantive): every artboard renders in fixture mode; tallies foot
// 14 = 8 + 6 and 8 = 6 + 2; unexplained rows are amber; no dollar sign appears in the table.

afterEach(cleanup);

function wrap(node: ReactNode): JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

describe("AUD-13 analytics", () => {
  it.each(AUD13_SCENARIOS)("renders artboard %s", (st) => {
    const { container } = render(wrap(<AnalyticsWorkspace st={st} />));
    const root = container.querySelector("[data-screen='AUD-13']");
    expect(root?.getAttribute("data-scenario")).toBe(st);
  });

  it("foots the tallies: 14 = 8 + 6 within, and 8 over = 6 explained + 2 unexplained", () => {
    const { container } = render(wrap(<AnalyticsWorkspace st="a" />));
    const lines = container.querySelectorAll("[data-line]");
    const over = container.querySelectorAll("[data-line][data-over]");
    const within = [...lines].filter((l) => !l.hasAttribute("data-over"));
    expect([lines.length, over.length, within.length]).toEqual([14, 8, 6]);
    const status = (s: string): number =>
      [...over].filter(
        (l) =>
          ["explained", "accepted"].includes(l.getAttribute("data-status") ?? "") ===
          (s === "explained"),
      ).length;
    expect([status("explained"), status("unexplained")]).toEqual([6, 2]);
    const tallies = container.querySelector("[data-aud13='tallies']")?.textContent ?? "";
    for (const n of ["14", "8", "6", "2"]) expect(tallies).toContain(n);
  });

  it("shades unexplained rows amber, never red", () => {
    const { container } = render(wrap(<AnalyticsWorkspace st="a" />));
    const amber = [...container.querySelectorAll("[data-line].bg-amber-tint")].map((r) =>
      r.getAttribute("data-line"),
    );
    expect(amber.sort()).toEqual(["cost_of_goods_sold", "inventory_net"]);
    expect(container.querySelector("[data-line][class*='red']")).toBeNull();
  });

  it.each(["a", "d", "e", "s"])("shows no dollar sign in the statement table (%s)", (st) => {
    const { container } = render(wrap(<AnalyticsWorkspace st={st} />));
    const table = container.querySelector("[data-aud13='statement']");
    expect(table?.textContent).not.toContain("$");
  });

  it("names the provisional materiality and the deciding partner in the threshold tooltip", async () => {
    const { AUD13_COPY } = await import("./copy");
    expect(AUD13_COPY.tally.thresholdTip).toContain("$155,000");
    expect(AUD13_COPY.tally.thresholdTip).toContain("Margaret Okonkwo");
  });

  it("final analytics carries the three adjustments: pre-tax income 3,100,000 less 114,480", () => {
    const { container } = render(wrap(<AnalyticsWorkspace st="e" />));
    const pti = container.querySelector("[data-subtotal='Pre-tax income']")?.textContent ?? "";
    expect(pti).toContain("2,985,520");
    for (const total of ["Total assets", "Total liabilities & equity"]) {
      const row = container.querySelector(`[data-subtotal='${total}']`)?.textContent ?? "";
      expect(row).toContain("26,295,520");
    }
  });
});
