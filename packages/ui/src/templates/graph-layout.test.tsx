// F-07-T16 (TASK-7918; handoff T14, TPL-14 a–c): "T14a to T14c render, the TIN slot accepts only a
// last-4 mask, a revealed value re-masks after 10 s, and Reveal is absent when the capability is
// absent."
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GraphCanvasLayout, MaskedTin, REMASK_MS, isTinMask } from "./graph-layout";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("T14 GraphCanvasLayout", () => {
  it("the TIN slot accepts only a last-four mask", () => {
    expect(isTinMask("•••-••-4417")).toBe(true);
    expect(isTinMask("••-•••0287")).toBe(true);
    expect(isTinMask("900-45-4417")).toBe(false);
    render(<MaskedTin value="900-45-4417" canReveal />);
    expect(screen.getByText("—")).toBeTruthy();
    expect(screen.queryByText("900-45-4417")).toBeNull();
  });

  it("Reveal is absent without the capability", () => {
    render(
      <MaskedTin value="•••-••-4417" canReveal={false} onReveal={() => Promise.resolve("x")} />,
    );
    expect(screen.queryByText("Reveal (logged)")).toBeNull();
  });

  it("a revealed value re-masks after 10 s", async () => {
    vi.useFakeTimers();
    render(
      <MaskedTin value="•••-••-4417" canReveal onReveal={() => Promise.resolve("900-45-4417")} />,
    );
    await act(async () => {
      fireEvent.click(screen.getByText("Reveal (logged)"));
      await Promise.resolve();
    });
    expect(screen.getByText("900-45-4417")).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(REMASK_MS);
    });
    expect(screen.getByText("•••-••-4417")).toBeTruthy();
  });

  it("a: graph with banner and inspector; b: list; e: single entity", () => {
    const { rerender } = render(
      <GraphCanvasLayout
        view="graph"
        canvas={<div data-testid="canvas" />}
        banner={{ tone: "at_risk", text: "Ridgeline 1065 → 2 K-1s at risk" }}
        inspector={{
          title: "Jonah Feld",
          sub: "Person · Brooklyn, NY",
          tin: "•••-••-4417",
          kv: [],
        }}
      />,
    );
    expect(screen.getByTestId("canvas")).toBeTruthy();
    expect(document.querySelector('[data-banner="at_risk"]')).toBeTruthy();
    rerender(
      <GraphCanvasLayout
        view="list"
        canvas={null}
        rows={[
          {
            id: "1",
            from: "A",
            relationship: "Sold",
            to: "B",
            since: "6/30/2025",
            source: "Agreement",
          },
        ]}
      />,
    );
    expect(screen.getByText("Sold")).toBeTruthy();
    rerender(<GraphCanvasLayout view="graph" canvas={null} single />);
    expect(screen.getByText("No relationships yet.")).toBeTruthy();
  });
});
