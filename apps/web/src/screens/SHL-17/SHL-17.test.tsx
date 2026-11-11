// P-05-T13 (SPEC-650; SHL-17 a–f from the collaboration seed).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { dueWords } from "../../domain/collaboration";
import { COPY } from "./copy";
import { STATES, TodoDrawer } from "./index";

afterEach(cleanup);

describe("SHL-17 to-do drawer", () => {
  it.each(STATES)("%s renders from data", (state) => {
    render(<TodoDrawer state={state} />);
    expect(document.querySelector(`[data-screen='SHL-17'][data-state='${state}']`)).not.toBeNull();
  });

  it("acceptance: Create to-do stays disabled until title and assignee are set", () => {
    const onCreate = vi.fn();
    render(<TodoDrawer state="b" onCreate={onCreate} />);
    const create = screen.getByRole<HTMLButtonElement>("button", { name: COPY.create });
    expect(create.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(COPY.titlePlaceholder), {
      target: { value: "Request opt-out elections" },
    });
    expect(create.disabled).toBe(true);
    fireEvent.click(screen.getByRole("option", { name: /Marcus Delaney/ }));
    expect(create.disabled).toBe(false);
    fireEvent.click(create);
    expect(onCreate).toHaveBeenCalledWith("Request opt-out elections", expect.any(String));
  });

  it("acceptance: the Undo toast calls only reopen", () => {
    const onComplete = vi.fn();
    const onReopen = vi.fn();
    const onCreate = vi.fn();
    render(
      <TodoDrawer state="c" onComplete={onComplete} onReopen={onReopen} onCreate={onCreate} />,
    );
    fireEvent.click(screen.getByRole("button", { name: COPY.markDone }));
    expect(onComplete).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: COPY.undo }));
    expect(onReopen).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("a: the title card, the due chip and the 0 of 4 checklist", () => {
    render(<TodoDrawer state="a" />);
    expect(screen.getByText("Wed Sep 16 · 2 days")).toBeTruthy();
    expect(screen.getByText("0 of 4")).toBeTruthy();
    expect(screen.getByText(COPY.activityA)).toBeTruthy();
  });

  it("c: assigned to you by Margaret Okonkwo", () => {
    render(<TodoDrawer state="c" />);
    expect(screen.getByText(COPY.assignedBanner("Margaret Okonkwo", "12:36 PM"))).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.reassign })).toBeTruthy();
  });

  it("d: overdue is derived from the date (red-tint)", () => {
    render(<TodoDrawer state="d" />);
    expect(document.querySelector("[data-due='overdue']")?.textContent).toContain(
      "Overdue · Sep 18",
    );
    expect(screen.getByText("1 of 2")).toBeTruthy();
  });

  it("e: done, with Reopen", () => {
    const onReopen = vi.fn();
    render(<TodoDrawer state="e" onReopen={onReopen} />);
    expect(screen.getByText(COPY.doneLine)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: COPY.reopen }));
    expect(onReopen).toHaveBeenCalled();
  });

  it("f: My to-dos foots 1 + 1 + 2 = 4 open", () => {
    render(<TodoDrawer state="f" />);
    expect(screen.getByText(COPY.segmentOpen(4))).toBeTruthy();
    expect(document.querySelectorAll("[data-todo]")).toHaveLength(4);
    expect(
      document.querySelector("[data-todo-group='Overdue'] [data-due='overdue']")?.textContent,
    ).toContain("Overdue · Sep 11");
    expect(
      document.querySelector("[data-todo-group='Today'] [data-due='today']")?.textContent,
    ).toContain("Today");
  });

  it("due words", () => {
    expect(dueWords("2026-09-16", "2026-09-14").text).toBe("Wed Sep 16 · 2 days");
    expect(dueWords("2026-09-16", "2026-09-14", false, true).text).toBe("Sep 16");
    expect(dueWords("2026-09-28", "2026-09-28", true).text).toBe("Due Sep 28");
  });
});
