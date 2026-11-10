// T-04-T13 (TAX-04 Prepare preset in fixture mode): a–e render; box 1a 14,820 lights line 3b;
// approving moves Review 36 to 35 with the ink check; a mismatch disables approval.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { COPY } from "./copy";
import { TAX04 } from ".";
import { STATES } from "./scenarios";

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("TAX-04 Prepare preset", () => {
  it.each(STATES)("%s renders its frame", (frame) => {
    render(<TAX04 frame={frame} />);
    expect(document.querySelector(`[data-screen='TAX-04'][data-frame='${frame}']`)).not.toBeNull();
    expect(screen.getByText(COPY.record.title)).toBeTruthy();
  });

  it("a: box 1a 14,820 lights line 3b in the demo's order", () => {
    render(<TAX04 frame="a" />);
    const line = (id: string): Element | null => document.querySelector(`[data-lead-row='${id}']`);
    const litBoxes = (): number =>
      document.querySelectorAll("[data-match-kind='region'][data-lit]").length;
    expect(line("3b")?.getAttribute("data-lit")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(700);
    });
    expect(litBoxes()).toBe(1); // box 1a
    expect(line("3b")?.getAttribute("data-lit")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(litBoxes()).toBe(2); // and box 1b at 1000 ms
    act(() => {
      vi.advanceTimersByTime(950);
    });
    expect(line("3b")?.getAttribute("data-lit")).toBe("true"); // 1950 ms
    expect(line("3b")?.textContent).toContain("$14,820");
    expect(line("3a")?.getAttribute("data-lit")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(300);
    });
    // The poster (3600 ms) holds all four: both boxes and both lines.
    act(() => {
      vi.advanceTimersByTime(1350);
    });
    expect(litBoxes()).toBe(2);
    expect(line("3a")?.getAttribute("data-lit")).toBe("true");
    expect(line("3b")?.getAttribute("data-lit")).toBe("true");
  });

  it("approving moves Review 36 to 35 and swaps the footer to Unapprove", () => {
    render(<TAX04 frame="a" />);
    expect(screen.getByText("36")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Approve Document/ }));
    expect(screen.getByText("35")).toBeTruthy();
    expect(screen.getByText(COPY.approvedToast)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Unapprove Document/ })).toBeTruthy();
  });

  it("b: approved shows Unapprove Document and Review 35", () => {
    render(<TAX04 frame="b" />);
    expect(screen.getByText("35")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Unapprove Document/ })).toBeTruthy();
  });

  it("c: the mismatch disables approval with its helper", () => {
    render(<TAX04 frame="c" />);
    expect(screen.getByText(COPY.mismatchHelper)).toBeTruthy();
    const approve = screen.getByRole<HTMLButtonElement>("button", { name: /Approve Document/ });
    expect(approve.disabled).toBe(true);
    expect(document.querySelector("[data-lead-row='3b']")?.textContent).toContain("$14,280");
  });

  it("d: the draft K-1 with box 5 lit beside its row; 2a keeps its flag", () => {
    render(<TAX04 frame="d" />);
    expect(screen.getByText(COPY.k1File)).toBeTruthy();
    expect(document.querySelector("[data-lead-row='int-k1']")?.getAttribute("data-lit")).toBe(
      "true",
    );
    expect(
      document.querySelector("[data-lead-row='texempt-all'] [aria-label='Flagged']"),
    ).not.toBeNull();
  });

  it("2b foots: 2,310 + 4,600 = 6,910", () => {
    render(<TAX04 frame="a" />);
    expect(document.querySelector("[data-lead-row='2b']")?.textContent).toContain("$6,910");
  });
});
