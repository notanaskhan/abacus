// T-04-T22 (SPEC-649 AC-3.1 to AC-3.8; TXI-01 a–g in fixture mode).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { COPY, FRAMES, IT201 } from "./copy";
import { WorksheetEditor } from "./Editor";

afterEach(cleanup);

const n = (s: string): number => Number(s.replace(/,/g, ""));
const value = (key: string): number =>
  n(IT201.flatMap((s) => s.fields).find((f) => f.key === key)?.value ?? "NaN");

describe("TXI-01 worksheet editor", () => {
  it.each(FRAMES)("%s renders its artboard", (frame) => {
    render(<WorksheetEditor frame={frame} />);
    expect(document.querySelector(`[data-screen='TXI-01'][data-frame='${frame}']`)).not.toBeNull();
  });

  it("a: line 20 lights Box 18A on page 3, with its struck prior value", () => {
    render(<WorksheetEditor frame="a" />);
    expect(document.querySelector("[data-field='20'][data-lit='true']")).not.toBeNull();
    expect(
      document.querySelector("[data-region='18A'][data-page='3'][data-lit='true']"),
    ).not.toBeNull();
    expect(document.querySelector("[data-field='20'] s")?.textContent).toBe("0");
    expect(screen.getByText(COPY.footer)).toBeTruthy();
  });

  it("the IT-201 figures tie to 615,605, 52,805, 51,536 and 1,269", () => {
    expect(value("19") + value("20") + value("22")).toBe(615_605);
    expect(value("33")).toBe(615_605);
    expect(value("33") - value("34")).toBe(value("37"));
    const tax = value("39") - value("112r") + value("47a");
    expect(tax).toBe(52_805);
    const paid = value("72") + value("73") + value("75") + value("653");
    expect(paid).toBe(51_536);
    expect(tax - paid).toBe(value("owed"));
  });

  it("b: the provenance popover names the approved proposal", () => {
    render(<WorksheetEditor frame="b" />);
    expect(screen.getByRole("dialog", { name: "Field provenance" }).textContent).toBe(
      COPY.provenance,
    );
  });

  it("c: the W-2 worksheet with boxes signed by both", () => {
    render(<WorksheetEditor frame="c" />);
    expect(document.querySelector("[data-sheet='w2']")).not.toBeNull();
    expect(screen.getByText("268,400")).toBeTruthy();
  });

  it("d: the flag on New York City resident opens TAX-06", () => {
    const onFlag = vi.fn();
    render(<WorksheetEditor frame="d" onFlag={onFlag} />);
    fireEvent.click(
      screen.getByRole("button", { name: "⚑ SI on New York City resident (line D2)" }),
    );
    expect(onFlag).toHaveBeenCalledWith("nyc");
  });

  it("e: IT-653 is new this year; f: Payments and credits signed off", () => {
    render(<WorksheetEditor frame="e" />);
    expect(screen.getByLabelText("New this year")).toBeTruthy();
    cleanup();
    render(<WorksheetEditor frame="f" />);
    expect(screen.getByText(COPY.signedOff)).toBeTruthy();
  });

  it("g: the NYC rows read recomputed by the engine and IT-360.1 appears", () => {
    render(<WorksheetEditor frame="g" />);
    expect(document.querySelectorAll("[data-recomputed='true']").length).toBe(2);
    expect(screen.getByText(COPY.it3601)).toBeTruthy();
  });

  it("no edit saves without a reason", () => {
    const onSave = vi.fn();
    render(<WorksheetEditor frame="a" onSave={onSave} />);
    fireEvent.click(screen.getByRole("button", { name: COPY.edit }));
    fireEvent.change(screen.getByLabelText("Value"), { target: { value: "1,600" } });
    fireEvent.click(screen.getByRole("button", { name: COPY.save }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toBe(COPY.reasonRequired);
    fireEvent.change(screen.getByLabelText(COPY.reason), { target: { value: "K-1 corrected" } });
    fireEvent.click(screen.getByRole("button", { name: COPY.save }));
    expect(onSave).toHaveBeenCalledWith("20", "1,600", "K-1 corrected");
  });
});
