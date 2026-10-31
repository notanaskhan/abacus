import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CAPITAL_ROWS, CAPITAL_TOTAL } from "../../../fixtures/seed/tax";
import { Tpl06Board, movementRows, partnerRows, tpl06Workbook } from ".";

// F-06-T20 (docs/screens/TPL-06.md): "Every row crossfoots and every column foots with transfers
// netting to 0, TPL-06b ties at 6,866,200, and a SignOffSlots click only calls onOpenSignOff."
// The arithmetic here checks the seed's carried figures; the specimen itself never adds.

afterEach(cleanup);

const n = (v: string | null | undefined): bigint => BigInt(v ?? "0");
const KEYS = ["beginning", "contributions", "income", "transfers", "distributions"] as const;

function wrap(node: ReactNode): JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

describe("TPL-06: the rollforward foots", () => {
  it("every row crossfoots, as drafted and fixed", () => {
    for (const r of CAPITAL_ROWS) {
      const drafted = KEYS.reduce((sum, k) => sum + n(r[k]), 0n);
      expect(drafted).toBe(n(r.endingDrafted));
      expect(drafted + n(r.taxExempt)).toBe(n(r.endingFixed));
    }
  });

  it("every column foots to the Total row and transfers net to 0", () => {
    for (const k of [...KEYS, "taxExempt", "endingDrafted", "endingFixed"] as const) {
      expect(CAPITAL_ROWS.reduce((sum, r) => sum + n(r[k]), 0n)).toBe(n(CAPITAL_TOTAL[k]));
    }
    expect(n(CAPITAL_TOTAL.transfers)).toBe(0n);
  });

  it("b ties at 6,866,200 with the tax-exempt column summing to 6,200 and no difference", () => {
    const rows = movementRows("b");
    const total = rows.find((r) => r.id === "total");
    expect(total?.cells.ending?.value).toBe("6866200");
    expect(total?.cells.taxExempt?.value).toBe("6200");
    expect(rows.find((r) => r.id === "tie-diff")?.cells.ending?.value).toBe("0");
    const m2 = tpl06Workbook("b").tally.find((t) => t.label === "M-2 ties");
    expect(m2 && "tally" in m2 ? m2.tally : null).toBe("tie");
  });

  it("a is off 6,200 on M-2 alone, explained by the tie-out", () => {
    const offs = tpl06Workbook("a").tally.filter((t) => "tally" in t && t.tally === "off");
    expect(offs).toHaveLength(1);
    expect(movementRows("a").find((r) => r.id === "tie-diff")?.cells.ending?.value).toBe("-6200");
  });

  it("c draws five 452 panes with Tax beside Book", () => {
    const wb = tpl06Workbook("c");
    expect(wb.panes.map((p) => p.width)).toEqual([452, 452, 452, 452, 452]);
    const first = CAPITAL_ROWS[0];
    if (first === undefined) throw new Error("no partner");
    const ending = partnerRows(first).find((r) => r.id === "end");
    expect(ending?.cells.tax?.value).toBe(first.endingFixed);
    expect(ending?.cells.book?.value).toBe(first.endingFixed);
  });
});

describe("TPL-06: sign-off", () => {
  it("e shows ✓ SI and Reviewed · SI, and a chip only opens SHL-12", () => {
    const open = vi.fn();
    render(wrap(<Tpl06Board state="e" onOpenSignOff={open} />));
    expect(screen.getByText("Reviewed · SI")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Samuel Ito, L2: open sign-off" }));
    expect(open).toHaveBeenCalledWith("workpaper:ridgeline-2025-capital-accounts", "L2");
  });

  it("d is building: no chips and no live sign-off", () => {
    expect(tpl06Workbook("d").building?.label).toBe("Workbook agent is running");
    expect(tpl06Workbook("d").signOffs).toBeUndefined();
  });
});
