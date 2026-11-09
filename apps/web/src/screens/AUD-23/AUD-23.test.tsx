// A-07-T34 (AUD-23 in fixture mode): the ten artboards, structured choices only, the partner's
// approval, the decision card for a modification, and the .docx states (revision R2).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { type Frame, ReportBuilder } from "./ReportBuilder";

afterEach(cleanup);

const FRAMES: Frame[] = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"];

describe("AUD-23 report builder", () => {
  it.each(FRAMES)("%s renders its artboard from the fixture", (frame) => {
    render(<ReportBuilder frame={frame} canApprove />);
    expect(document.querySelector(`[data-screen='AUD-23'][data-frame='${frame}']`)).not.toBeNull();
    expect(document.querySelector("[data-signature='placeholder']")).not.toBeNull();
    expect(screen.queryByRole("button", { name: /^Release/ })).toBeNull();
  });

  it("no paragraph text is editable as free text", () => {
    render(<ReportBuilder frame="a" canApprove />);
    expect(document.querySelector("[contenteditable='true']")).toBeNull();
    expect(document.querySelector("section[aria-label='Paper'] textarea")).toBeNull();
    expect(document.querySelector("section[aria-label='Paper'] input")).toBeNull();
    expect(screen.getByRole("button", { name: "Edit" }).getAttribute("title")).toBe(
      "Report text comes from the structured choices",
    );
  });

  it("a: draft v2 awaiting the partner, the two-part opinion and the ERISA schedules section", () => {
    const onApprove = vi.fn();
    render(<ReportBuilder frame="a" canApprove onApprove={onApprove} />);
    expect(screen.getByText("Independent auditor’s report · v2")).toBeTruthy();
    expect(document.querySelector("[data-watermark='draft']")).not.toBeNull();
    expect(screen.getByText("Supplemental Schedules Required by ERISA")).toBeTruthy();
    expect(screen.getByText("Engagement partner approval")).toBeTruthy();
    expect(screen.getByText("October 9, 2026", { selector: "dd *, span, p" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Approve report/ }));
    expect(onApprove).toHaveBeenCalledTimes(1);
  });

  it("Approve report is the partner's: a viewer without the action sees none", () => {
    render(<ReportBuilder frame="a" />);
    expect(screen.queryByRole("button", { name: /Approve report/ })).toBeNull();
  });

  it("b: approved and locked; the primary goes to issuance & release", () => {
    render(<ReportBuilder frame="b" />);
    expect(
      screen.getByText(
        "Approved by Margaret Okonkwo · Oct 7, 4:20 PM · locked · the firm signature is applied at release (AUD-24)",
      ),
    ).toBeTruthy();
    expect(document.querySelector("[data-watermark='draft']")).toBeNull();
    expect(screen.getByRole("button", { name: /Go to issuance & release/ })).toBeTruthy();
  });

  it("c: a qualified opinion waits on the partner's decision card and blocks approval", () => {
    const onRequestDecision = vi.fn();
    render(<ReportBuilder frame="c" canApprove onRequestDecision={onRequestDecision} />);
    expect(screen.getByText("Qualified Opinion")).toBeTruthy();
    expect(screen.getByText("Basis for Qualified Opinion")).toBeTruthy();
    expect(screen.getByText("Decision required")).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: /Approve report/ }) as HTMLButtonElement).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Request partner decision…" }));
    expect(onRequestDecision).toHaveBeenCalledWith("qual");
  });

  it("picking a modification records a version and re-renders the paper", () => {
    render(<ReportBuilder frame="a" canApprove />);
    fireEvent.click(screen.getByRole("button", { name: /None — unmodified/ }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: /Adverse/ }));
    expect(screen.getByText("Adverse Opinion")).toBeTruthy();
    expect(screen.getByText("Independent auditor’s report · v3")).toBeTruthy();
  });

  it("d: the going-concern section shows for illustration; its toggle is never a choice", () => {
    render(<ReportBuilder frame="d" canApprove />);
    expect(
      screen.getByText("Substantial Doubt About the Plan’s Ability to Continue as a Going Concern"),
    ).toBeTruthy();
    const toggle = screen.getByRole("switch", { name: "Going concern section" });
    expect((toggle as HTMLButtonElement).disabled).toBe(true);
  });

  it("e and f: review and compilation titles", () => {
    render(<ReportBuilder frame="e" />);
    expect(screen.getByText("Independent Accountant’s Review Report")).toBeTruthy();
    expect(screen.getByText("Conclusion")).toBeTruthy();
    cleanup();
    render(<ReportBuilder frame="f" />);
    expect(screen.getByText("Accountant’s Compilation Report")).toBeTruthy();
  });

  it("g: the reissue is dual-dated and waits on the partner's reissue approval", () => {
    render(<ReportBuilder frame="g" canApprove />);
    expect(screen.getByText("Reissued report")).toBeTruthy();
    expect(
      screen.getByText("October 9, 2026, except for Note 12, as to which the date is January 15, 2027"),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /Approve reissue/ })).toBeTruthy();
  });

  it("an emphasis-of-matter paragraph needs its reason code before approval", () => {
    render(<ReportBuilder frame="a" canApprove />);
    fireEvent.click(screen.getByRole("switch", { name: "Emphasis of matter" }));
    expect(screen.getByText("Pick a reason code for each paragraph you turned on")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /EOM-CHG · Emphasis of matter · change/ }));
    expect(screen.getByText(/Drafted from EOM-CHG/)).toBeTruthy();
  });

  it("h, i and j: generating, generated with Open in Word, and out of date", () => {
    render(<ReportBuilder frame="h" />);
    expect(screen.getByText("Generating…")).toBeTruthy();
    cleanup();
    render(<ReportBuilder frame="i" />);
    expect(screen.getByRole("status").textContent).toBe(
      "Northwind PY2025 auditor's report v2.docx generated · DRAFT",
    );
    expect(screen.getByRole("button", { name: "Open in Word" })).toBeTruthy();
    cleanup();
    render(<ReportBuilder frame="j" />);
    expect(screen.getByText("Out of date · Update from data")).toBeTruthy();
  });

  it("Generate .docx… opens the template sheet with the locked DRAFT watermark", () => {
    render(<ReportBuilder frame="a" />);
    fireEvent.click(screen.getByRole("button", { name: /Generate \.docx/ }));
    const sheet = screen.getByRole("dialog", { name: "Generate from template" });
    expect(sheet.textContent).toContain("BH Report · EBP 103(a)(3)(C) v3");
    expect(sheet.textContent).toContain("Placeholder — applied at release (AUD-24)");
    expect(
      (screen.getByRole("switch", { name: "Watermark" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("hovering a citation lights its structure row", () => {
    render(<ReportBuilder frame="a" />);
    fireEvent.mouseEnter(document.querySelector("[data-marker='3']") as Element);
    expect(document.querySelector("[data-lit='true']")?.textContent).toContain("ERISA-SUPP");
  });
});
