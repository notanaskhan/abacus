// T-06-T30 (TASK-8752; docs/screens/TXP-04.md; T-06 §3 F2): "M-1 never renders as filed, and Accept
// opens SHL-10 rather than applying the value inline." One test per artboard; figures are the
// server's (the fixture stands in for it) and the screen sums nothing.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TXP04_OPENS, TXP04_REVIEW, scenarios } from "../../fixtures/scenarios/TXP-04";
import { M1, M3, m2 } from "../../fixtures/seed/tax-depth-booktax";
import { COPY } from "./copy";
import { TXP04, m2Rows, m2Tally, m3Rows } from ".";

afterEach(cleanup);

describe("TXP-04 M-1/M-3 and Schedule M-2", () => {
  it("covers the five artboards on two frames", () => {
    expect(Object.keys(scenarios)).toEqual(["a", "ap", "b", "c", "d"]);
    expect(TXP04_REVIEW).toEqual({
      a: "m1-m3",
      ap: "m1-m3",
      b: "schedule-m2",
      c: "schedule-m2",
      d: "schedule-m2",
    });
    expect(TXP04_OPENS).toEqual({ ap: "?m1=1", c: "?variant=with_fix" });
  });

  it("a: M-3 is filed, Part I reads 17,914,500 and 1,256,200, one permanent row 6,200", () => {
    render(<TXP04 frame="m1-m3" m3={M3} />);
    expect(screen.getByText(COPY.filed)).toBeTruthy();
    expect(screen.getByText("17,914,500")).toBeTruthy();
    expect(screen.getAllByText("1,256,200").length).toBeGreaterThan(0);
    const rows = m3Rows(M3);
    const permanent = rows.filter((r) => r.cells.c?.value !== "0");
    expect(permanent.map((r) => r.cells.line?.value)).toEqual(["13", "29"]);
    expect(rows[0]?.label).toContain("Form 8916-A attached");
    expect(screen.queryByText(COPY.m1Banner)).toBeNull();
    // No "$" in cells (statement grammar); the Item J caption is prose.
    for (const grid of screen.getAllByRole("grid")) expect(grid.textContent).not.toMatch(/\$/);
  });

  it("a′: the M-1 reference has its banner and is never filed", () => {
    render(<TXP04 frame="m1-m3" m3={M3} m1={M1} showM1 />);
    expect(screen.getByRole("note").textContent).toBe(COPY.m1Banner);
    const ref = document.querySelector<HTMLElement>("[data-m1-reference]");
    if (ref === null) throw new Error("no M-1 reference");
    expect(within(ref).getByText(COPY.notFiled)).toBeTruthy();
    expect(within(ref).queryByText(COPY.filed)).toBeNull();
    // Exactly one schedule reads Filed on the frame: the M-3.
    expect(screen.getAllByText(COPY.filed)).toHaveLength(1);
    expect(M1.filed).toBe(false);
  });

  it("b: as drafted ends 6,860,000 against 6,866,200, off 6,200, with the ghost on line 4", () => {
    const tally = m2Tally(m2("as_drafted"));
    expect(tally[0]).toMatchObject({ tally: "off", vars: { amount: "6,200" } });
    expect(tally[1]).toMatchObject({ value: "6,860,000" });
    expect(tally[2]).toMatchObject({ value: "6,866,200" });
    const rows = m2Rows(m2("as_drafted"), "6,200");
    expect(rows.find((r) => r.id === "m2:4")?.cells.ghost?.value).toBe(COPY.proposed("6,200"));
  });

  it("b: Accept… opens SHL-10 and applies nothing inline; Reject… needs a reason", () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();
    render(
      <TXP04
        frame="schedule-m2"
        m2={m2("as_drafted")}
        proposedLine4="6200"
        variant="as_drafted"
        canDecide
        onAccept={onAccept}
        onReject={onReject}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: COPY.accept }));
    expect(onAccept).toHaveBeenCalledTimes(1);
    // Still as drafted: line 9 is 6,860,000 and the ghost is still a ghost.
    expect(screen.getAllByText("6,860,000").length).toBeGreaterThan(0);
    expect(document.querySelector("[data-accepted]")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: COPY.reject }));
    const dialog = screen.getByRole("dialog", { name: COPY.rejectTitle });
    const confirm = within(dialog).getByRole<HTMLButtonElement>("button", {
      name: COPY.rejectConfirm,
    });
    expect(confirm.disabled).toBe(true);
    expect(onReject).not.toHaveBeenCalled();
  });

  it("c: with the proposed fix line 4 is 6,200, line 5 7,466,200 and line 9 ties at 6,866,200", () => {
    render(
      <TXP04 frame="schedule-m2" m2={m2("with_fix")} variant="with_fix" proposedLine4="6200" />,
    );
    expect(m2Tally(m2("with_fix"))[0]).toMatchObject({ tally: "tie" });
    for (const t of ["6,200", "7,466,200", "6,866,200"]) {
      expect(screen.getAllByText(t).length).toBeGreaterThan(0);
    }
    expect(screen.queryByRole("button", { name: COPY.accept })).toBeNull();
  });

  it("d: accepted shows the checkpoint and no ghost, Accept or variant switch", () => {
    const onOpenCheckpoint = vi.fn();
    render(
      <TXP04
        frame="schedule-m2"
        m2={m2("as_drafted", "accepted")}
        variant="as_drafted"
        accepted
        onOpenCheckpoint={onOpenCheckpoint}
      />,
    );
    expect(screen.getByText(COPY.accepted)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: COPY.openCheckpoint }));
    expect(onOpenCheckpoint).toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: COPY.accept })).toBeNull();
    expect(screen.queryByText(COPY.withFix)).toBeNull();
  });
});
