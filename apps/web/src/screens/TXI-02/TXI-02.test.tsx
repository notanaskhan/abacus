// T-04-T40 (SPEC-649 §3.7; TXI-02 a–e in fixture mode). Acceptance: "TXI-02a-e render from
// scenarios, figures tie to 307,900, 16,025, 61,580 and 4,674,575, approval collapses to the 10:24
// AM checkpoint line, and the Draft chip stays until the released state."
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { COPY, FRAMES, STATEMENT, TREATMENTS } from "./copy";
import { K1Resolver } from "./Resolver";

afterEach(cleanup);

const n = (s: string): number => Number(s.replace(/[^0-9]/g, ""));
const parts = (resolved: string): number[] =>
  [...resolved.matchAll(/([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)/g)].map((m) => n(m[1] ?? ""));
const row = (key: string) => TREATMENTS.find((t) => t.key === key);

describe("TXI-02 K-1 treatment resolver", () => {
  it.each(FRAMES)("%s renders its artboard", (frame) => {
    render(<K1Resolver frame={frame} />);
    expect(document.querySelector(`[data-screen='TXI-02'][data-frame='${frame}']`)).not.toBeNull();
  });

  it("TXI-02 acceptance: every figure ties", () => {
    const state = parts(row("state")?.resolved ?? "");
    expect(state[0]! + state[1]! + state[2]!).toBe(307_900);
    const ptet = STATEMENT.filter((r) => r.key !== "total").map((r) => n(r.figure));
    expect(ptet.reduce((a, b) => a + b, 0)).toBe(16_025);
    expect(n(STATEMENT.find((r) => r.key === "total")?.figure ?? "")).toBe(16_025);
    const qbi = parts(row("qbi")?.resolved ?? "");
    expect(qbi).toEqual([307_900, 61_580]);
    expect(Math.round(307_900 * 0.2)).toBe(61_580);
    expect(61_580).toBeLessThan(98_450);
    expect(1_912_500 + 2_762_075).toBe(n(row("basis")?.resolved.split("basis ")[1] ?? ""));
  });

  it("a: seven proposed, treatment 8 approved at 9:31, only PTET amber with its reason", () => {
    render(<K1Resolver frame="a" />);
    expect(document.querySelectorAll("[data-status='proposed']")).toHaveLength(6);
    expect(document.querySelectorAll("[data-status='changed']")).toHaveLength(1);
    expect(document.querySelector("[data-treatment='7'][data-changed='true']")).not.toBeNull();
    expect(screen.getByText("Approved · SI 9:31")).toBeTruthy();
    expect(screen.getByText(row("ptet")?.rationale ?? "")).toBeTruthy();
    expect(document.querySelectorAll("[data-chip-changed='true']")).toHaveLength(1);
  });

  it("a: approve opens SHL-10 through the host; the agent decides nothing here", () => {
    const onApprove = vi.fn();
    render(<K1Resolver frame="a" onApprove={onApprove} />);
    fireEvent.click(screen.getByRole("button", { name: COPY.approve }));
    expect(onApprove).toHaveBeenCalledOnce();
  });

  it("b: every row Approved · SI and the card collapses to the 10:24 AM checkpoint line", () => {
    render(<K1Resolver frame="b" />);
    expect(document.querySelectorAll("[data-status='approved']")).toHaveLength(8);
    expect(document.querySelector("[data-approval='collapsed']")?.textContent).toBe(
      COPY.approvedLine,
    );
    expect(screen.queryByRole("button", { name: COPY.approve })).toBeNull();
  });

  it("c: treatment 7 lights the PTET statement and carries the Colorado note", () => {
    render(<K1Resolver frame="c" />);
    expect(document.querySelector("[data-treatment='7'][data-selected='true']")).not.toBeNull();
    expect(document.querySelectorAll("[data-statement][data-lit='true']")).toHaveLength(4);
    expect(screen.getByText(COPY.changedNote)).toBeTruthy();
  });

  it("d: an override needs a reason, then reads Overridden · SI with the reason", () => {
    const onOverride = vi.fn();
    render(<K1Resolver frame="d" onOverride={onOverride} />);
    fireEvent.click(screen.getByRole("button", { name: COPY.save }));
    expect(screen.getByRole("alert").textContent).toBe(COPY.reasonRequired);
    expect(onOverride).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole("textbox", { name: COPY.reasonLabel }), {
      target: { value: "Material participation documented" },
    });
    fireEvent.click(screen.getByRole("button", { name: COPY.save }));
    expect(onOverride).toHaveBeenCalledWith(
      "passive",
      "Nonpassive",
      "Material participation documented",
    );
    expect(screen.getByText(COPY.overridden)).toBeTruthy();
    expect(screen.getByText("Material participation documented")).toBeTruthy();
  });

  it("the Draft chip stays until the released state", () => {
    for (const frame of FRAMES.filter((f) => f !== "e")) {
      render(<K1Resolver frame={frame} />);
      expect(document.querySelector("[data-chip-state='draft']")?.textContent).toBe(COPY.draftChip);
      cleanup();
    }
    render(<K1Resolver frame="e" />);
    expect(document.querySelector("[data-chip-state='draft']")).toBeNull();
    expect(document.querySelector("[data-chip-state='released']")?.textContent).toBe(
      COPY.releasedChip,
    );
  });

  it("e: the released banner and treatment 5's basis after the M-2 fix", () => {
    render(<K1Resolver frame="e" />);
    expect(screen.getByRole("status").textContent).toBe(COPY.released);
    expect(document.querySelector("[data-resolved='5']")?.textContent).toContain("4,676,125");
  });
});
