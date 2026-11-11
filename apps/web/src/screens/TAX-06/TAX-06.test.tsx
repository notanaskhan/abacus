// T-04-T26 (SPEC-649 §3; TAX-06 a–g in fixture mode).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { COPY, DETAILS, FRAMES, issuesCsv, OPEN, RESOLVED } from "./copy";
import { Issues } from "./Issues";

afterEach(cleanup);

describe("TAX-06 issues", () => {
  it.each(FRAMES)("%s renders its artboard", (frame) => {
    render(<Issues frame={frame} />);
    expect(document.querySelector(`[data-screen='TAX-06'][data-frame='${frame}']`)).not.toBeNull();
  });

  it("counts: 4 open = 2 Missing information + 1 Action required + 1 Review point; 3 resolved", () => {
    const kinds = OPEN.map((r) => r.kind).sort();
    expect(kinds).toEqual([
      "Action required",
      "Missing information",
      "Missing information",
      "Review point",
    ]);
    expect(RESOLVED).toHaveLength(3);
    expect(OPEN.length + RESOLVED.length).toBe(7);
  });

  it("a: the 18A issue selected lights the chip, the viewer region and the two ghost fields", () => {
    render(<Issues frame="a" />);
    expect(document.querySelector("[data-issue='box18a'][aria-selected='true']")).not.toBeNull();
    expect(document.querySelector("[data-region='18A'][data-lit='true']")).not.toBeNull();
    expect(document.querySelector("[data-chip][data-lit='true']")).not.toBeNull();
    expect(document.querySelectorAll("[data-field][data-lit='true']")).toHaveLength(2);
  });

  it("acceptance: Accept on the box 18A ghost value opens SHL-10 and Issues go 4 to 3 after approval", () => {
    const onAccept = vi.fn();
    const { rerender } = render(<Issues frame="a" onAccept={onAccept} />);
    expect(screen.getByText("4")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: COPY.accept })[0]!);
    expect(onAccept).toHaveBeenCalledWith("box18a");
    rerender(<Issues frame="a" openCount={3} />);
    expect(screen.getByText("3")).toBeTruthy();
  });

  it("Reject asks a reason", () => {
    const onReject = vi.fn();
    render(<Issues frame="a" onReject={onReject} />);
    fireEvent.click(screen.getAllByRole("button", { name: COPY.reject })[0]!);
    fireEvent.click(screen.getByRole("menuitem", { name: COPY.rejectReasons[1] }));
    expect(onReject).toHaveBeenCalledWith("box18a", COPY.rejectReasons[1]);
  });

  it("acceptance: Mark as Resolved is disabled with 'Resolves when the final K-1 is released' on the Draft K-1 issue", () => {
    render(<Issues frame="b" />);
    const resolve = screen.getByRole<HTMLButtonElement>("button", { name: `✓ ${COPY.resolve}` });
    expect(resolve.disabled).toBe(true);
    expect(screen.getByText(DETAILS.draftK1!.resolveDisabled!)).toBeTruthy();
    expect(screen.getByText(COPY.whatItBlocks)).toBeTruthy();
  });

  it("Mark as Resolved needs a note, then answers the host with it", () => {
    const onResolve = vi.fn();
    render(<Issues frame="d" onResolve={onResolve} />);
    const resolve = screen.getByRole<HTMLButtonElement>("button", { name: `✓ ${COPY.resolve}` });
    expect(resolve.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Resolution note"), {
      target: { value: "Brooklyn confirmed" },
    });
    fireEvent.click(resolve);
    expect(onResolve).toHaveBeenCalledWith("nycResidency", "Brooklyn confirmed");
  });

  it("Set Fix Instructions offers the suggested instruction", () => {
    const onSetFix = vi.fn();
    render(<Issues frame="a" onSetFix={onSetFix} />);
    fireEvent.click(screen.getByRole("button", { name: "Set Fix Instructions" }));
    expect(onSetFix).toHaveBeenCalledWith("box18a", COPY.fixInstruction);
  });

  it("c: waiting on client, already requested", () => {
    render(<Issues frame="c" />);
    expect(screen.getByText(DETAILS.estimates!.note!)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Ask the client…" })).toBeTruthy();
  });

  it("e: the agent fixing shows In progress and the run row", () => {
    render(<Issues frame="e" />);
    expect(screen.getByText(COPY.inProgress)).toBeTruthy();
    expect(screen.getByText(COPY.running)).toBeTruthy();
    expect(document.querySelector("[data-fixing='true']")).not.toBeNull();
  });

  it("f and g: resolved filter rows and the empty state", () => {
    render(<Issues frame="f" />);
    expect(screen.getAllByText(COPY.resolvedPill)).toHaveLength(3);
    cleanup();
    render(<Issues frame="g" />);
    expect(screen.getByText(COPY.emptyTitle)).toBeTruthy();
    expect(screen.getByText(COPY.emptyBody)).toBeTruthy();
  });

  it("the CSV quotes and never lets a spreadsheet evaluate a cell", () => {
    const csv = issuesCsv([{ ...OPEN[1]!, title: "=SUM(A1)" }]);
    expect(csv.split("\n")[0]).toBe(COPY.csvHeader);
    expect(csv).toContain("'=SUM(A1)");
  });

  it("the agent never resolves: no control names the agent resolving", () => {
    render(<Issues frame="a" />);
    expect(screen.queryByText(/Agent resolved/i)).toBeNull();
  });
});
