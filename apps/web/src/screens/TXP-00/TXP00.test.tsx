// T-05-T29 (TASK-7521; docs/screens/TXP-00.md; handoff TXP-00 A–E): "All five artboards render
// from fixtures with ink-2 spinners, and running versus waiting is distinguishable without colour."
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { COPY, GROUPS } from "./copy";
import { TXP00, type Txp00Frame, frameOf, openItems, rowState } from ".";

afterEach(cleanup);

const FRAMES: Txp00Frame[] = ["a", "b", "c", "d", "e"];

describe("TXP-00 Agent tab", () => {
  it("renders all five artboards with six groups and ten rows", () => {
    for (const frame of FRAMES) {
      const { container, unmount } = render(<TXP00 frame={frame} />);
      expect(
        container.querySelector(`[data-screen="TXP-00"][data-frame="${frame}"]`),
      ).not.toBeNull();
      expect(container.querySelectorAll("[data-group]")).toHaveLength(6);
      expect(container.querySelectorAll("[data-task]")).toHaveLength(10);
      unmount();
    }
  });

  it("A: open items sum to 11, the Issues badge", () => {
    expect(openItems()).toBe(11);
    expect(GROUPS.map((g) => g.tasks.reduce((n, t) => n + t.open, 0))).toEqual([1, 1, 2, 4, 1, 2]);
    render(<TXP00 frame="a" />);
    expect(screen.getByText(COPY.completeTitle)).toBeTruthy();
  });

  it("B: three rows run with ink-2 spinners and the word Running, never amber", () => {
    const { container } = render(<TXP00 frame="b" />);
    const running = container.querySelectorAll('[data-state="run"]');
    expect(running).toHaveLength(3);
    for (const row of running) {
      expect(row.textContent).toMatch(/Running…/u);
      expect(row.querySelector("[data-spinner]")).not.toBeNull();
      expect(row.innerHTML).not.toMatch(/amber/u);
    }
    expect(screen.getByText(COPY.runningPill)).toBeTruthy();
    expect(container.querySelector("[data-live]")).not.toBeNull();
  });

  it("D: waiting reads in words and a warn disc, with the §706(d) question above the composer", () => {
    const { container } = render(<TXP00 frame="d" />);
    const waiting = container.querySelector('[data-task="interim_closing_706d"]') as HTMLElement;
    expect(waiting.dataset.state).toBe("warn");
    expect(within(waiting).getByText(COPY.waiting)).toBeTruthy();
    expect(waiting.querySelector("[data-spinner]")).toBeNull();
    expect(screen.getByText(/Pell Street transfer\?/u)).toBeTruthy();
    expect((screen.getAllByRole("radio")[0] as HTMLInputElement).checked).toBe(true);
  });

  it("C: idle rows are Not started and ▶ Run starts the run", () => {
    const onRun = vi.fn();
    render(<TXP00 frame="c" onRun={onRun} />);
    expect(screen.getAllByText(COPY.notStarted)).toHaveLength(10);
    fireEvent.click(screen.getByRole("button", { name: COPY.runPrimary }));
    expect(onRun).toHaveBeenCalledOnce();
  });

  it("E: the failed import offers Retry, Reconnect and View run", () => {
    const onRetry = vi.fn();
    render(<TXP00 frame="e" onRetry={onRetry} />);
    expect(screen.getAllByText(COPY.failedTitle).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: COPY.retry }));
    expect(onRetry).toHaveBeenCalledWith("import_trial_balance");
    expect(screen.getByRole("button", { name: COPY.reconnect })).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.viewRun })).toBeTruthy();
  });

  it("never renders a human-only verb", () => {
    for (const frame of FRAMES) {
      const { unmount } = render(<TXP00 frame={frame} />);
      for (const verb of ["Approve", "Sign off", "Release", "Send", "Post", "Decide"]) {
        expect(screen.queryByRole("button", { name: new RegExp(`^${verb}`, "u") })).toBeNull();
      }
      unmount();
    }
  });

  it("maps a return's runs to its frame", () => {
    expect(frameOf([])).toBe("c");
    expect(frameOf([{ state: "running" }])).toBe("b");
    expect(frameOf([{ state: "waiting_on_inputs" }])).toBe("d");
    expect(frameOf([{ state: "failed" }])).toBe("e");
    expect(frameOf([{ state: "succeeded" }, { state: "failed" }])).toBe("a");
    expect(rowState("c", GROUPS[0]!.tasks[0]!)).toBe("todo");
  });
});
