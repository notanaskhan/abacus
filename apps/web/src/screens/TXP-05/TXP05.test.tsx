// T-05-T43 (TASK-7704; docs/screens/TXP-05.md; handoff TXP-05 A–D): every artboard renders from the
// server's figures (the fixture stands in for it); each line ties K = Σ K-1s, Item L is off 6,200
// until the fix, Line 2 opens Form 8825 and Item L opens its two routes.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { partners } from "../../fixtures/seed/tax-entity";
import {
  allocationSummary,
  breakdown,
  capitalAccounts,
  scheduleK,
} from "../../fixtures/seed/tax-entity-schedule-k";
import { COPY } from "./copy";
import { TXP05, tableRows, tallyItems } from ".";

afterEach(cleanup);

function draw(props: Partial<Parameters<typeof TXP05>[0]> = {}) {
  return render(
    <TXP05
      k={scheduleK("federal")}
      partners={partners("run2")}
      capital={capitalAccounts("run2")}
      allocation={allocationSummary()}
      view="federal"
      {...props}
    />,
  );
}

describe("TXP-05 Schedule K", () => {
  it("A: the matrix's groups and line 2 crossfoot to 1,231,600 with Pell Street II second-half only", () => {
    const rows = tableRows(scheduleK("federal"), partners("run2"), capitalAccounts("run2"));
    expect(rows.filter((r) => r.kind === "group").map((r) => r.label)).toEqual([
      COPY.groups.income,
      COPY.groups.other,
      COPY.groups.analysis,
      COPY.groups.items,
    ]);
    const line2 = rows.find((r) => r.id === "line:2");
    expect(line2?.cells.total?.value).toBe("1231600");
    expect(line2?.cells.sum?.value).toBe("1231600");
    expect(line2?.cells.p2?.value).toBe("400270"); // 35% × 615,800 + 30% × 615,800
    expect(line2?.cells.p3?.value).toBe("30790");
    expect(rows.find((r) => r.id === "line:20c")?.cells.total?.text).toBe(COPY.stmt);
    expect(rows.find((r) => r.id === "line:1")?.cells.total?.text).toBe("—");
  });

  it("A: Analysis of Net Income is 1,250,000 and Item J reads beginning → ending", () => {
    const rows = tableRows(scheduleK("federal"), partners("run2"), capitalAccounts("run2"));
    expect(rows.find((r) => r.id === "line:analysis_1")?.cells.total?.value).toBe("1250000");
    const j = rows.find((r) => r.id === "item:J");
    expect(j?.cells.p2?.text).toBe("35% → 30%");
    expect(j?.cells.p3?.text).toBe("0% → 5%");
  });

  it("A: Item L as drafted sums to 6,860,000, off 6,200 against 6,866,200", () => {
    const l = tableRows(scheduleK("federal"), partners("run2"), capitalAccounts("run2")).find(
      (r) => r.id === "item:L",
    );
    expect(l?.label).toBe(COPY.rows.itemL);
    expect(l?.cells.sum?.value).toBe("6860000");
    expect(l?.cells.tie?.value).toBe("off 6,200");
    expect(l?.cells.total?.text).toBe(`6,866,200 ${COPY.rows.schL}`);
    const items = tallyItems(
      scheduleK("federal"),
      partners("run2"),
      capitalAccounts("run2"),
      allocationSummary(),
      false,
    );
    expect(items.map((i) => i.label)).toEqual(Object.values(COPY.cards));
    expect(items[4]).toMatchObject({ tally: "off", vars: { amount: "6,200" } });
    expect(items[2]).toMatchObject({ value: "1,250,000" });
    expect(items[5]).toMatchObject({ pill: { text: "Straight percentage · Approved" } });
  });

  it("A: the screen draws the title, the controls, the footnote and no $", () => {
    draw();
    expect(screen.getByText(COPY.title, { selector: "span" })).toBeTruthy();
    expect(screen.getByText(COPY.allocation)).toBeTruthy();
    expect(screen.getByText(COPY.footnote)).toBeTruthy();
    expect(screen.getAllByText("1,231,600").length).toBeGreaterThan(0);
    expect(screen.queryByText(/\$/)).toBeNull();
  });

  it("A2: line 2 opens the Form 8825 popover with its three properties", () => {
    draw({ breakdown: breakdown("2") });
    expect(screen.getByText("Elm Street")).toBeTruthy();
    expect(screen.getByText("566,536")).toBeTruthy();
    expect(screen.getByText("Bergen Street")).toBeTruthy();
  });

  it("A4: Item L's popover routes to Capital Accounts and Issues", () => {
    const onOpenCapital = vi.fn();
    const onOpenIssues = vi.fn();
    draw({ itemLOpen: true, onOpenCapital, onOpenIssues });
    fireEvent.click(screen.getByText(COPY.openCapital));
    fireEvent.click(screen.getByText(COPY.openIssues));
    expect(onOpenCapital).toHaveBeenCalledOnce();
    expect(onOpenIssues).toHaveBeenCalledOnce();
  });

  it("B: the state view lists each state's PTET credit with its partner splits", () => {
    const rows = tableRows(scheduleK("state"), partners("run2"), capitalAccounts("run2"));
    const il = rows.find((r) => r.id === "line:ptet_il");
    expect(il?.cells.total?.value).toBe("28044");
    expect(il?.cells.p1?.value).toBe("10657");
    expect(rows.find((r) => r.id === "line:IL")?.cells.total?.text).toBe("—");
  });

  it("C: after the fix Item L ties at 6,866,200", () => {
    const l = tableRows(scheduleK("federal"), partners("run2"), capitalAccounts("afterFix")).find(
      (r) => r.id === "item:L",
    );
    expect(l?.cells.sum?.value).toBe("6866200");
    expect(l?.cells.tie?.value).toBe("tie");
    expect(l?.cells.p0?.value).toBe("93124");
  });

  it("D: Building shows skeleton rows and Pending cards", () => {
    draw({ building: true });
    expect(screen.getAllByText(COPY.building).length).toBeGreaterThan(0);
    const items = tallyItems(undefined, undefined, undefined, undefined, true);
    expect(items.every((i) => "pill" in i && i.pill.text === COPY.pending)).toBe(true);
  });

  it("the Allocation Structure trigger opens TXP-06", () => {
    const onAllocation = vi.fn();
    draw({ onAllocation });
    fireEvent.click(screen.getByText(COPY.allocation));
    expect(onAllocation).toHaveBeenCalledOnce();
  });
});
