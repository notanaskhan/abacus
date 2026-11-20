// T-06-T32 (TASK-8835; docs/screens/TXP-09.md; T-06 §3 F4): "Pills are distinguishable without
// colour and the NYC row never creates an election." One test per artboard; figures are the
// server's and the screen adds nothing.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TXP09_OPENS, scenarios } from "../../fixtures/scenarios/TXP-09";
import { states } from "../../fixtures/seed/tax-depth-states";
import { COPY } from "./copy";
import { TXP09, tallyItems } from ".";

afterEach(cleanup);

describe("TXP-09 States & PTET", () => {
  it("covers the five artboards", () => {
    expect(Object.keys(scenarios)).toEqual(["a", "b", "c", "d", "e"]);
    expect(TXP09_OPENS).toEqual({ d: "?view=nexus" });
  });

  it("a: IL 46.0 + CO 31.5 + NY 22.5, PTET 64,096 paid, sourcing in review", () => {
    render(<TXP09 states={states()} view="apportionment" />);
    expect(document.querySelectorAll("[data-state]")).toHaveLength(3);
    expect(screen.getByText("566,536")).toBeTruthy();
    expect(screen.getAllByText("64,096").length).toBeGreaterThan(0);
    expect(screen.getByText(COPY.reviewPointOpen)).toBeTruthy();
    const items = tallyItems(states());
    expect(items[0]).toMatchObject({ tally: "tie" });
    expect(items[2]).toMatchObject({ value: "3 of 3" });
  });

  it("b: Colorado shows Map… and the sum reads Check with the banner", () => {
    const onMap = vi.fn();
    render(<TXP09 states={states("missingFactor")} view="apportionment" onMap={onMap} />);
    fireEvent.click(screen.getByRole("button", { name: COPY.map }));
    expect(onMap).toHaveBeenCalledWith("CO");
    expect(screen.getByText(COPY.missingBanner)).toBeTruthy();
    expect(tallyItems(states("missingFactor"))[0]).toMatchObject({ pill: { text: "Check" } });
  });

  it("c: New York Not paid, Paid 2 of 3", () => {
    render(<TXP09 states={states("paymentGap")} view="apportionment" />);
    expect(screen.getByText(COPY.notPaid)).toBeTruthy();
    expect(tallyItems(states("paymentGap"))[4]).toMatchObject({ pill: { text: "2 of 3" } });
  });

  it("d: nexus facts with evidence and conclusions", () => {
    render(<TXP09 states={states()} view="nexus" />);
    expect(document.querySelectorAll("[data-nexus]")).toHaveLength(4);
    expect(screen.getByText("Elm_Street_Deed_2018.pdf")).toBeTruthy();
    expect(screen.getByText("No UBT return")).toBeTruthy();
  });

  it("e: approved by SI on Sep 14, no Approve sourcing", () => {
    render(<TXP09 states={states("approved")} view="apportionment" />);
    expect(screen.getAllByText("Approved · SI · Sep 14")).toHaveLength(3);
    expect(screen.queryByRole("button", { name: COPY.approveSourcing })).toBeNull();
  });

  it("credits: Jonah Feld reads 16,025", () => {
    render(<TXP09 states={states()} view="credits" />);
    expect(screen.getByText("16,025")).toBeTruthy();
  });

  it("pills carry their words and the NYC row never elects", () => {
    const onRecommend = vi.fn();
    render(<TXP09 states={states()} view="apportionment" onRecommend={onRecommend} />);
    for (const word of [COPY.ptet.elected, COPY.ptet.recommend, COPY.ptet.not_elected]) {
      expect(screen.getAllByText(word).length).toBeGreaterThan(0);
    }
    fireEvent.click(screen.getByRole("button", { name: /Recommend: New York City/u }));
    expect(onRecommend).toHaveBeenCalledTimes(1);
    expect(document.querySelectorAll('[data-opportunity] [data-ptet="elected"]')).toHaveLength(0);
  });
});
