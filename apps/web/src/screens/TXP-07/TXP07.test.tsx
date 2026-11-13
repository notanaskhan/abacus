// T-05-T55 (TASK-7907; docs/screens/TXP-07.md; handoff TXP-07 a–e): "All eight artboards render and
// the blocked sign-off explains the open tie-out in words." Figures are the server's (the fixture
// stands in for it); every pane crossfoots and the screen sums nothing.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { partners } from "../../fixtures/seed/tax-entity";
import { capitalAccounts } from "../../fixtures/seed/tax-entity-schedule-k";
import { STATES } from "./scenarios";
import { COPY } from "./copy";
import { TXP07, movementRows, paneLines, tallyItems } from ".";

afterEach(cleanup);

function must<T>(v: T | null | undefined): T {
  if (v === null || v === undefined) throw new Error("expected an element");
  return v;
}

describe("TXP-07 Capital Accounts", () => {
  it("covers the eight artboards", () => {
    expect(STATES).toEqual(["a", "a2", "a3", "b", "b2", "c", "d", "e"]);
  });

  it("a: two panes of five, Meera Shah's tax ending 2,527,000 and 704(b) 2,529,356", () => {
    render(
      <TXP07 capital={capitalAccounts("run2")} partners={partners("run2")} view="by_partner" />,
    );
    expect(screen.getByText(COPY.pager(1, 2, 5))).toBeTruthy();
    expect(screen.getByText("2,527,000")).toBeTruthy();
    expect(screen.getAllByText("2,529,356").length).toBe(2);
    expect(screen.queryByText(/\$/)).toBeNull();
  });

  it("a: M-2 ties is off 6,200 and the off link opens the issue", () => {
    const onOpenIssue = vi.fn();
    const items = tallyItems(capitalAccounts("run2"), false, onOpenIssue);
    const m2 = items[1];
    expect(m2).toMatchObject({ label: COPY.cards.m2, tally: "off", vars: { amount: "6,200" } });
    expect(items.map((i) => i.label)).not.toContain(COPY.cards.other);
    expect(items.find((i) => i.label === COPY.cards.end)).toMatchObject({ value: "6,860,000" });
  });

  it("a2: Meera Shah's blank tax cell is amber and opens its provenance", () => {
    const onOpenCell = vi.fn();
    render(
      <TXP07
        capital={capitalAccounts("run2")}
        view="by_partner"
        page={0}
        onOpenCell={onOpenCell}
      />,
    );
    fireEvent.click(screen.getByLabelText(COPY.amberCell("05 Capital!G3")));
    expect(onOpenCell).toHaveBeenCalledWith("05 Capital!G3");
  });

  it("a3: Pell Street's transfers net to 0 and open the Allocation Structure", () => {
    const rows = capitalAccounts("run2").rows;
    const psv = paneLines(must(rows[2])).find((l) => l.id === "transfers");
    const ps2 = paneLines(must(rows[3])).find((l) => l.id === "transfers");
    expect(psv?.tax).toBe("(331,405)");
    expect(ps2?.tax).toBe("331,405");
    const onTransfers = vi.fn();
    render(
      <TXP07
        capital={capitalAccounts("run2")}
        view="by_partner"
        page={2}
        onTransfers={onTransfers}
      />,
    );
    fireEvent.click(must(screen.getAllByLabelText(COPY.transfersCell)[0]));
    expect(onTransfers).toHaveBeenCalled();
  });

  it("b: the movement totals and the tie-out to Schedule L, difference (6,200)", () => {
    const rows = movementRows(capitalAccounts("run2"), partners("run2"));
    const total = rows.find((r) => r.id === "total");
    expect(total?.cells.beginning?.value).toBe("5960000");
    expect(total?.cells.ending?.value).toBe("6860000");
    expect(total?.cells.transfers?.value).toBe("0");
    const onOpenIssue = vi.fn();
    render(
      <TXP07 capital={capitalAccounts("run2")} view="by_movement" onOpenIssue={onOpenIssue} />,
    );
    fireEvent.click(screen.getByLabelText(COPY.tieOut.openIssue));
    expect(onOpenIssue).toHaveBeenCalled();
  });

  it("b2: Sign off… while a tie-out is off explains it in words and needs a note", () => {
    const onSignOffOpen = vi.fn();
    const { rerender } = render(
      <TXP07 capital={capitalAccounts("run2")} view="by_partner" onSignOffOpen={onSignOffOpen} />,
    );
    fireEvent.click(screen.getByText(COPY.signOff));
    expect(onSignOffOpen).toHaveBeenCalledWith(true);
    const onSignOff = vi.fn();
    rerender(
      <TXP07
        capital={capitalAccounts("run2")}
        view="by_partner"
        signOffOpen
        onSignOff={onSignOff}
      />,
    );
    expect(screen.getByText(COPY.blocked(1))).toBeTruthy();
    const sign = screen.getByText(COPY.signWithNote);
    expect((sign.closest("button") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(COPY.noteLabel), { target: { value: "Fix pending" } });
    fireEvent.click(screen.getByText(COPY.signWithNote));
    expect(onSignOff).toHaveBeenCalledWith("Fix pending");
  });

  it("c: after the fix the tax-exempt cells are ink, M-2 ties and OTHER INCREASES is 6,200", () => {
    const items = tallyItems(capitalAccounts("afterFix"), false);
    expect(items[1]).toMatchObject({ tally: "tie" });
    expect(items.find((i) => i.label === COPY.cards.other)).toMatchObject({ value: "6,200" });
    expect(items.find((i) => i.label === COPY.cards.end)).toMatchObject({ value: "6,866,200" });
    render(<TXP07 capital={capitalAccounts("afterFix")} view="by_partner" />);
    expect(screen.queryByLabelText(COPY.amberCell("05 Capital!G2"))).toBeNull();
  });

  it("d: computing shows every check pending", () => {
    render(<TXP07 capital={capitalAccounts("run2")} view="by_partner" computing />);
    expect(screen.getByText(COPY.computing)).toBeTruthy();
    expect(tallyItems(capitalAccounts("run2"), true).every((i) => "pill" in i)).toBe(true);
  });

  it("e: signed off shows the initials chip and Reviewed · SI, no Sign off…", () => {
    render(<TXP07 capital={capitalAccounts("afterFix")} view="by_partner" signedBy="SI" />);
    expect(screen.getByText(COPY.signedChip("SI"))).toBeTruthy();
    expect(screen.getByText(COPY.reviewed("SI"))).toBeTruthy();
    expect(screen.queryByText(COPY.signOff)).toBeNull();
  });
});
