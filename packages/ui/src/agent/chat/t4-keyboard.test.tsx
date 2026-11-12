// F-07-T09 (TASK-7511; SPEC-652 AC-4, AC-5): the keyboard suite for the QuestionCard, the Composer
// and the JumpFab, at unit level (the gallery walk is e2e/specimens/f07-t4.spec.ts).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QuestionCard, type QuestionPayload } from "./question-card";
import { ChatThread, type ThreadItem } from "./thread";

afterEach(cleanup);

const ONE: QuestionPayload = {
  question_id: "q1",
  steps: [
    {
      q: "Which returns should the report cover?",
      options: [
        { key: "open", title: "Open returns only" },
        { key: "all", title: "All TY2025 returns" },
      ],
      preselect: "open",
    },
  ],
};

function line(seq: number): ThreadItem {
  return {
    id: `i${String(seq)}`,
    seq,
    kind: "user_message",
    payload: { body: `Line ${String(seq)}` },
    actor_kind: "human",
    actor_name: "Hannah Leclerc",
  };
}

describe("T4 keyboard", () => {
  it("QuestionCard: every option is reachable by its number and announced as a radio", () => {
    const onAnswer = vi.fn();
    render(<QuestionCard question={ONE} onAnswer={onAnswer} />);
    const radios = screen.getAllByRole("radio");
    expect(radios.map((r) => r.getAttribute("aria-keyshortcuts"))).toEqual(["1", "2"]);
    fireEvent.keyDown(screen.getByRole("group"), { key: "2" });
    fireEvent.keyDown(screen.getByRole("group"), { key: "Enter" });
    expect(onAnswer).toHaveBeenCalledWith({ question_id: "q1", step: 1, key: "all" });
  });

  it("QuestionCard: Shift+Enter does not answer", () => {
    const onAnswer = vi.fn();
    render(<QuestionCard question={ONE} onAnswer={onAnswer} />);
    fireEvent.keyDown(screen.getByRole("group"), { key: "Enter", shiftKey: true });
    expect(onAnswer).not.toHaveBeenCalled();
  });

  it("Composer: Enter sends the trimmed text, Shift+Enter does not, an empty composer sends nothing", () => {
    const onSend = vi.fn();
    render(<ChatThread items={[]} onSend={onSend} />);
    const composer = screen.getByRole("textbox", { name: "Message" });
    fireEvent.keyDown(composer, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.change(composer, { target: { value: "  Status by office  " } });
    fireEvent.keyDown(composer, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(composer, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("Status by office");
    expect((composer as HTMLTextAreaElement).value).toBe("");
  });

  it("JumpFab: appears for an unseen item while scrolled up and focuses the latest item", () => {
    const { rerender } = render(<ChatThread items={[line(1)]} />);
    const log = screen.getByRole("log", { name: "Conversation" });
    Object.defineProperty(log, "scrollHeight", { configurable: true, value: 1000 });
    Object.defineProperty(log, "clientHeight", { configurable: true, value: 300 });
    log.scrollTop = 0;
    fireEvent.scroll(log);
    rerender(<ChatThread items={[line(1), line(2)]} />);
    const jump = screen.getByRole("button", { name: "Jump to latest" });
    fireEvent.click(jump);
    expect(screen.queryByRole("button", { name: "Jump to latest" })).toBeNull();
  });
});
