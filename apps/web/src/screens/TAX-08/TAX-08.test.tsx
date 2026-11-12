// T-04-T34 (SPEC-649 §3; TAX-08 a, a2, b, c, d, e, f, loading, not allowed in fixture mode).
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Assistant, UNDO_MS } from "./Assistant";
import { COPY, DIFF, FRAMES, TIES } from "./copy";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("TAX-08 assistant", () => {
  it.each(FRAMES)("%s renders its artboard", (frame) => {
    render(<Assistant frame={frame} />);
    expect(document.querySelector(`[data-screen='TAX-08'][data-frame='${frame}']`)).not.toBeNull();
  });

  it("the ties hold: NY AGI 614,055 → 615,605, QBI 61,580 under 98,450, total tax +12,397", () => {
    const sum = (xs: readonly number[]) => xs.reduce((a, b) => a + b, 0);
    expect(sum(TIES.nyAgiBefore.parts)).toBe(TIES.nyAgiBefore.total);
    expect(sum(TIES.nyAgiAfter.parts)).toBe(TIES.nyAgiAfter.total);
    expect((TIES.qbi.box2 * TIES.qbi.rate) / 100).toBe(TIES.qbi.deduction);
    expect((TIES.qbi.ubia * TIES.qbi.ubiaRate) / 100).toBe(TIES.qbi.limit);
    expect(TIES.qbi.deduction).toBeLessThan(TIES.qbi.limit);
    expect(TIES.totalTax.y2025 - TIES.totalTax.y2024).toBe(TIES.totalTax.rise);
    expect(DIFF.map((d) => d.after)).toEqual(["1,550", "1,550", "615,605"]);
  });

  it("a: the tax-exempt row is lit and hovering a row lights its box in the viewer", () => {
    const light = vi.fn();
    render(<Assistant frame="a" onLightRegion={light} />);
    expect(document.querySelector("[data-k1-row='taxExempt'][data-lit='true']")).not.toBeNull();
    const rental = document.querySelector("[data-k1-row='rental']");
    if (rental === null) throw new Error("expected the rental row");
    fireEvent.mouseEnter(rental);
    expect(light).toHaveBeenCalledWith("2");
    fireEvent.mouseLeave(rental);
    expect(light).toHaveBeenLastCalledWith(null);
    expect(document.querySelectorAll("[data-chip]")).toHaveLength(6);
  });

  it("a: approving sends the person's approval; the agent's own text never reads approve or sign", () => {
    const approve = vi.fn();
    render(<Assistant frame="a" onApprove={approve} />);
    fireEvent.click(screen.getByRole("button", { name: "Approve adjustments" }));
    expect(approve).toHaveBeenCalledWith({});
    for (const block of document.querySelectorAll("[data-actor='agent']")) {
      expect(block.querySelector("button")).toBeNull();
    }
  });

  it("a: Reject… asks a reason before it rejects", () => {
    const reject = vi.fn();
    render(<Assistant frame="a" onReject={reject} />);
    fireEvent.click(screen.getByRole("button", { name: COPY.reject }));
    fireEvent.change(screen.getByLabelText(COPY.rejectReason), {
      target: { value: "wait for the final K-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(reject).toHaveBeenCalledWith("wait for the final K-1");
  });

  it("d: the checkpoint line shows Undo for 10 seconds, then not", () => {
    vi.useFakeTimers();
    render(<Assistant frame="d" />);
    expect(screen.getByText(COPY.applied)).not.toBeNull();
    expect(screen.queryByRole("button", { name: COPY.undo })).not.toBeNull();
    act(() => {
      vi.advanceTimersByTime(UNDO_MS);
    });
    expect(screen.queryByRole("button", { name: COPY.undo })).toBeNull();
  });

  it("b offers the three idle prompts and asks the one chosen", () => {
    const ask = vi.fn();
    render(<Assistant frame="b" onAsk={ask} />);
    const prompts = document.querySelectorAll("[data-suggestion]");
    expect(prompts).toHaveLength(3);
    fireEvent.click(screen.getByText("What's left before partner review?"));
    expect(ask).toHaveBeenCalledWith("What's left before partner review?");
  });

  it("e and f: the rejection line and the 2024 / 2025 table", () => {
    render(<Assistant frame="e" />);
    expect(screen.getByText(COPY.rejected)).not.toBeNull();
    cleanup();
    render(<Assistant frame="f" />);
    expect(screen.getByRole("table", { name: "2024 and 2025" })).not.toBeNull();
    expect(screen.getByText("123,223")).not.toBeNull();
  });
});
