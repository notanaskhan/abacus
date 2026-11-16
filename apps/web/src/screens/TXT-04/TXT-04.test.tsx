import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { APPRAISAL_HREF, EstateWorkpapers, TXT04_SCENARIOS } from ".";
import { TALLY, adjustedTaxableGifts, grossEstate, totalDeductions } from "./data";

// T-07-T26 (TXT-04 A to E): every section's totals foot to the tally; the Illinois card never
// shows a number; Request appraisal opens SHL-14 prefilled for Paul Thornbury.

afterEach(cleanup);

describe("TXT-04 estate workpapers", () => {
  it.each(TXT04_SCENARIOS)("renders section %s", (st) => {
    const { container } = render(<EstateWorkpapers st={st} />);
    expect(container.querySelector("[data-screen='TXT-04']")?.getAttribute("data-scenario")).toBe(
      st,
    );
  });

  it("foots every section to the tally", () => {
    expect(grossEstate()).toBe(TALLY.gross);
    expect(totalDeductions()).toBe(TALLY.deductions);
    expect(TALLY.gross - TALLY.deductions).toBe(TALLY.taxable);
    expect(adjustedTaxableGifts()).toBe(TALLY.adjustedGifts);
  });

  it("never shows a figure on the Illinois card", () => {
    const { container } = render(<EstateWorkpapers st="c" />);
    const card = container.querySelector("[data-illinois]");
    expect(card?.textContent).not.toMatch(/\d/);
  });

  it("opens SHL-14 prefilled for Paul Thornbury", () => {
    render(<EstateWorkpapers st="a" />);
    const link = screen.getByRole("link", { name: "Request appraisal…" });
    expect(link.getAttribute("href")).toBe(APPRAISAL_HREF);
    expect(link.getAttribute("data-prefill")).toBe("Paul Thornbury");
  });
});
