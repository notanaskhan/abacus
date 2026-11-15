// W-02-T27 (TASK-8066; W-02 §10; T4, TPL-04): the Workbench keyboard suite beyond F-07-T09's
// `t4-keyboard.test.tsx`. QuestionCard: Next walks "1 of 2" to "2 of 2", Previous returns with the
// first answer still chosen, Skip emits exactly one `{skipped: true}` and nothing after it, Esc
// hands focus back without answering. ContextPicker: every record is a native button announced as
// a menuitemcheckbox, so Space and Enter activate it, and aria-checked follows the attachment.
// Undo toast: the window is UNDO_MS (DEC-24), Undo is a real button reachable by Tab, pressing it
// calls only the caller's compensating command, and the deferred commit never runs after it.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastHost } from "../../components/toast";
import { UNDO_MS, createToast, createToastStore } from "../../components/toast-store";
import { ContextPicker } from "./context-picker";
import type { ContextItem } from "./empty-session";
import { QuestionCard, type QuestionPayload } from "./question-card";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const TWO: QuestionPayload = {
  question_id: "q-season",
  steps: [
    {
      q: "Which returns should the report cover?",
      options: [
        { key: "open", title: "Open returns only" },
        { key: "all", title: "All TY2025 returns" },
      ],
      preselect: "open",
    },
    {
      q: "How should offices be grouped?",
      options: [
        { key: "office", title: "By office" },
        { key: "preparer", title: "By preparer" },
      ],
    },
  ],
};

describe("W-02 keyboard: QuestionCard", () => {
  it("Next walks 1 of 2 to 2 of 2 and Previous returns to step 1", () => {
    const onAnswer = vi.fn();
    render(<QuestionCard question={TWO} onAnswer={onAnswer} />);
    expect(screen.getByText("1 of 2")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Previous" })).toHaveProperty("disabled", true);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onAnswer).toHaveBeenCalledWith({ question_id: "q-season", step: 1, key: "open" });
    expect(screen.getByText("2 of 2")).toBeTruthy();
    const previous = screen.getByRole("button", { name: "Previous" });
    expect(previous).toHaveProperty("disabled", false);
    fireEvent.click(previous);
    expect(screen.getByText("1 of 2")).toBeTruthy();
    expect(screen.getByRole("radio", { name: /Open returns only/ })).toHaveProperty(
      "checked",
      true,
    );
  });

  it("Skip emits one skipped answer and nothing after it", () => {
    const onAnswer = vi.fn();
    render(<QuestionCard question={TWO} onAnswer={onAnswer} />);
    const skip = screen.getByRole("button", { name: "Skip" });
    fireEvent.click(skip);
    fireEvent.click(skip);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onAnswer).toHaveBeenCalledTimes(1);
    expect(onAnswer).toHaveBeenCalledWith({ question_id: "q-season", skipped: true });
  });

  it("Esc returns focus to the composer without answering", () => {
    const onAnswer = vi.fn();
    const onEscape = vi.fn();
    render(<QuestionCard question={TWO} onAnswer={onAnswer} onEscape={onEscape} />);
    fireEvent.keyDown(screen.getAllByRole("radio")[0] as HTMLElement, { key: "Escape" });
    expect(onEscape).toHaveBeenCalledTimes(1);
    expect(onAnswer).not.toHaveBeenCalled();
  });

  it("Skip, Previous and Next are native buttons in that tab order", () => {
    render(<QuestionCard question={TWO} onAnswer={vi.fn()} />);
    const names = screen
      .getAllByRole("button")
      .map((b) => b.textContent.trim())
      .filter((t) => t === "Skip" || t === "Previous" || t === "Next");
    expect(names).toEqual(["Skip", "Previous", "Next"]);
    for (const b of screen.getAllByRole("button")) expect(b.tagName).toBe("BUTTON");
  });
});

const NORTHWIND: ContextItem = {
  id: "cr-northwind",
  kind: "client_record",
  label: "Northwind Dental Group",
  detail: "Client record",
};
const PBC: ContextItem = {
  id: "doc-pbc",
  kind: "documents",
  label: "PBC 12 of 24",
  detail: "Request list",
};

describe("W-02 keyboard: ContextPicker", () => {
  it("every record is a native button announced as a menuitemcheckbox with aria-checked", () => {
    render(
      <ContextPicker
        trigger={<span />}
        forceState="open"
        items={{ client_record: [NORTHWIND], documents: [PBC] }}
        attached={new Set([NORTHWIND.id])}
        onAttach={vi.fn()}
        onDetach={vi.fn()}
      />,
    );
    const rows = screen.getAllByRole("menuitemcheckbox");
    expect(rows).toHaveLength(2);
    for (const row of rows) expect(row.tagName).toBe("BUTTON");
    expect(rows.map((r) => r.getAttribute("aria-checked"))).toEqual(["true", "false"]);
  });

  it("activating a row attaches or detaches it", () => {
    const onAttach = vi.fn();
    const onDetach = vi.fn();
    render(
      <ContextPicker
        trigger={<span />}
        forceState="open"
        items={{ client_record: [NORTHWIND], documents: [PBC] }}
        attached={new Set([NORTHWIND.id])}
        onAttach={onAttach}
        onDetach={onDetach}
      />,
    );
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: /PBC 12 of 24/ }));
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: /Northwind/ }));
    expect(onAttach).toHaveBeenCalledWith(PBC);
    expect(onDetach).toHaveBeenCalledWith(NORTHWIND);
  });
});

describe("W-02 keyboard: Undo toast", () => {
  it("Undo is a button; pressing it inside the window calls only the undo command", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
    const store = createToastStore();
    const toast = createToast(store);
    const commit = vi.fn();
    const undo = vi.fn();
    render(<ToastHost store={store} contained />);
    act(() => {
      toast.undoable({ text: "Saved to Files", commit, undo });
    });
    const button = screen.getByRole("button", { name: "Undo" });
    expect(button.tagName).toBe("BUTTON");
    act(() => {
      vi.advanceTimersByTime(UNDO_MS - 1);
    });
    fireEvent.click(button);
    act(() => {
      vi.advanceTimersByTime(UNDO_MS);
    });
    expect(undo).toHaveBeenCalledTimes(1);
    expect(commit).not.toHaveBeenCalled();
  });

  it("with no Undo the deferred commit runs once at UNDO_MS (10 seconds)", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
    expect(UNDO_MS).toBe(10_000);
    const store = createToastStore();
    const toast = createToast(store);
    const commit = vi.fn();
    render(<ToastHost store={store} contained />);
    act(() => {
      toast.undoable({ text: "Saved to Files", commit, undo: vi.fn() });
    });
    act(() => {
      vi.advanceTimersByTime(UNDO_MS - 1);
    });
    expect(commit).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(commit).toHaveBeenCalledTimes(1);
  });
});
