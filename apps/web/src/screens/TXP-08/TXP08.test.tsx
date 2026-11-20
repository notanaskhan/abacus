// T-06-T31 (TASK-8753; docs/screens/TXP-08.md; T-06 §3 F3): "Send to client shows the existing
// waiting-on-client issue, and Request more analysis is shown as fixture-only until T-09." One test
// per artboard; figures are the server's and the screen adds nothing.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TXP08_OPENS, scenarios } from "../../fixtures/scenarios/TXP-08";
import { BASIS_PARTNERS, FELD_ID, PELL_II_ID, basis } from "../../fixtures/seed/tax-depth-basis";
import { COPY } from "./copy";
import { TXP08, s752Rows, tallyItems } from ".";

afterEach(cleanup);

const PARTNERS = BASIS_PARTNERS.map((p) => ({ id: p.partner_id, name: p.name }));
const WAITING = {
  title:
    "§754 election: partners' decision and support for Pell Street II's $360,000 purchase price",
  step: "§706(d) interim closing · sent to Owen Calder Sep 11",
};

describe("TXP-08 Basis", () => {
  it("covers the five artboards with their opens", () => {
    expect(Object.keys(scenarios)).toEqual(["a", "b", "c", "d", "e"]);
    expect(TXP08_OPENS).toEqual({
      b: "?partner=_feldId_",
      c: "?partner=_pellIIId_",
      d: "?card=754",
      e: "?view=s752",
    });
  });

  it("a: 4 of 5 reconcile, inside 17,914,500 against outside 17,943,095, Pell Street II off", () => {
    render(<TXP08 basis={basis("basis")} partners={PARTNERS} view="basis" partnerId={null} />);
    const items = tallyItems(basis("basis"), 5);
    expect(items[0]).toMatchObject({ pill: { text: "4 of 5" } });
    expect(items[1]).toMatchObject({ value: "17,914,500" });
    expect(items[2]).toMatchObject({ value: "17,943,095" });
    const off = document.querySelectorAll('[data-tally="off"]');
    expect(off).toHaveLength(1);
    expect(off[0]?.getAttribute("data-basis-card")).toBe(PELL_II_ID);
    expect(document.querySelectorAll('[data-tally="tie"]')).toHaveLength(4);
  });

  it("b: Jonah Feld reconciles at 4,676,125", () => {
    render(
      <TXP08
        basis={basis("basis", FELD_ID)}
        partners={PARTNERS}
        view="basis"
        partnerId={FELD_ID}
      />,
    );
    const card = screen.getByRole("region", { name: "Jonah Feld" });
    expect(within(card).getAllByText("4,676,125")).toHaveLength(2);
    expect(within(card).getByText(COPY.reconciles)).toBeTruthy();
  });

  it("c: Pell Street II LLC reads 885,225 vs 913,820 with the §743(b) placeholder", () => {
    render(
      <TXP08
        basis={basis("basis", PELL_II_ID)}
        partners={PARTNERS}
        view="basis"
        partnerId={PELL_II_ID}
      />,
    );
    const card = screen.getByRole("region", { name: "Pell Street II LLC" });
    expect(card.textContent).toContain("885,225 vs 913,820");
    expect(card.textContent).toContain(COPY.placeholder);
  });

  it("d: the §754 card recommends Elect; the partners decide and Send to client… shows the waiting issue", () => {
    const onOpenIssue = vi.fn();
    render(
      <TXP08
        basis={basis("basis")}
        partners={PARTNERS}
        view="basis"
        partnerId={null}
        cardOpen
        waitingIssue={WAITING}
        requestMore="fixture"
        onOpenIssue={onOpenIssue}
      />,
    );
    const card = screen.getByRole("region", { name: COPY.card.title });
    expect(within(card).getByText("Agent recommendation")).toBeTruthy();
    // No Decide on the firm's screen: the partners decide (INV-1, T-06 F3).
    expect(within(card).queryByRole("button", { name: "Decide" })).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
    fireEvent.click(within(card).getByRole("button", { name: COPY.card.send }));
    const status = screen.getByRole("status");
    expect(status.textContent).toContain(WAITING.title);
    expect(status.textContent).toContain(WAITING.step);
    fireEvent.click(within(status).getByRole("button", { name: COPY.openIssue }));
    expect(onOpenIssue).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: COPY.card.requestMore })).toBeTruthy();
    expect(screen.getByText(COPY.card.fixtureOnly)).toBeTruthy();
  });

  it("d live: Request more analysis is absent outside fixture builds", () => {
    render(
      <TXP08
        basis={basis("basis")}
        partners={PARTNERS}
        view="basis"
        partnerId={null}
        cardOpen
        requestMore="hidden"
      />,
    );
    expect(screen.queryByRole("button", { name: COPY.card.requestMore })).toBeNull();
  });

  it("e: §752 shares by partner, qualified and other nonrecourse", () => {
    render(<TXP08 basis={basis("s752")} partners={PARTNERS} view="s752" partnerId={null} />);
    const rows = s752Rows(basis("s752"));
    expect(rows.find((r) => r.label === "Meera Shah")?.cells.qnr?.value).toBe("4070750");
    expect(screen.getByText("4,070,750")).toBeTruthy();
    expect(screen.getByText(COPY.s752Note)).toBeTruthy();
  });
});
