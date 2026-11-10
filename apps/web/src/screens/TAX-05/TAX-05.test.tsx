// T-04-T21 (SPEC-649 AC-2.1 to AC-2.6; TAX-05 a–f in fixture mode).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIGURES } from "../../fixtures/seed/tax-workspace";
import { COPY, FRAMES, MATRIX } from "./copy";
import { ReviewPreset } from "./Review";

afterEach(cleanup);

const amount = (s: string): number => Number(s.replace(/[$,]/g, ""));

describe("TAX-05 review preset", () => {
  it.each(FRAMES)("%s renders its artboard", (frame) => {
    render(<ReviewPreset frame={frame} />);
    expect(document.querySelector(`[data-screen='TAX-05'][data-frame='${frame}']`)).not.toBeNull();
  });

  it("a: Review 37, the K-1 selected and flagged, box 5 lit with the Interest Income row", () => {
    render(<ReviewPreset frame="a" />);
    expect(screen.getByText("Review 37")).toBeTruthy();
    expect(document.querySelector("[data-row='k1'][aria-selected='true']")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Flag 1" })).toBeTruthy();
    expect(document.querySelector("[data-box='5'][data-lit='true']")).not.toBeNull();
    expect(
      document.querySelector("[data-matrix='Interest Income'][data-lit='true']"),
    ).not.toBeNull();
  });

  it("b: approving Statement A moves Review 37 to 36 with the toast", () => {
    render(<ReviewPreset frame="b" />);
    expect(screen.getByText("Review 36")).toBeTruthy();
    expect(screen.getByText(COPY.toast)).toBeTruthy();
    expect(document.querySelector("[data-row='stmtA'] [data-check='approved']")).not.toBeNull();
    expect(screen.getByRole("button", { name: COPY.unapprove })).toBeTruthy();
  });

  it("a: Approve calls the host and never moves the count itself", () => {
    const onApprove = vi.fn();
    render(<ReviewPreset frame="a" onApprove={onApprove} />);
    fireEvent.click(screen.getByRole("button", { name: COPY.approve }));
    expect(onApprove).toHaveBeenCalledWith("k1");
    expect(screen.getByText("Review 37")).toBeTruthy();
  });

  it("c: the flag opens TAX-06 with the box 18A issue", () => {
    const onFlag = vi.fn();
    render(<ReviewPreset frame="c" onFlag={onFlag} />);
    fireEvent.click(screen.getByRole("button", { name: "Flag 1" }));
    expect(onFlag).toHaveBeenCalledWith(COPY.flaggedIssue);
  });

  it("d: the Worksheets tab shows the Sch E p2 rows with their sign-off chips", () => {
    render(<ReviewPreset frame="d" />);
    expect(screen.getByText(COPY.worksheet)).toBeTruthy();
    expect(screen.getAllByText("✓ KO").length).toBeGreaterThan(0);
  });

  it("e: all approved, the banner, and Request final approval… blocked while the Draft K-1 exists", () => {
    render(<ReviewPreset frame="e" />);
    expect(screen.getByText(COPY.allApproved)).toBeTruthy();
    const request = screen.getByRole<HTMLButtonElement>("button", { name: COPY.requestFinal });
    expect(request.disabled).toBe(true);
    expect(screen.getAllByText(COPY.draftBlocks).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^Review \d+$/)).toBeNull();
  });

  it("the matrix foots to the K-1: 307,900 / 4,600 / 1,550 / 150,000 and Item L 1,912,500", () => {
    const cy = Object.fromEntries(MATRIX.map((m) => [m.label, amount(m.cy)]));
    expect(cy["Net Rental Real Estate Income"]).toBe(Number(FIGURES.ridgelineBox2Total));
    expect(FIGURES.ridgelineBox2Shares.map(Number).reduce((a, b) => a + b, 0)).toBe(307_900);
    expect(cy["Interest Income"]).toBe(4_600);
    expect(cy["Tax-Exempt Interest"]).toBe(1_550);
    expect(cy["Distributions — Cash"]).toBe(150_000);
    const itemL =
      (cy["Beginning Capital Account"] ?? 0) +
      (cy["Capital Contributed"] ?? 0) +
      312_500 -
      (cy["Distributions — Cash"] ?? 0);
    expect(itemL).toBe(cy["Ending Capital Account"]);
    expect(cy["Section 199A UBIA"]).toBe(0.25 * 15_752_000);
  });
});
