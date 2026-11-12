// F-07-T06 (TASK-7508; SPEC-652 AC-5; handoff T4 ASK CARD, TPL-04a). Acceptance: "T4c and TPL-04a
// pass Tier D, Next emits exactly one answer intent with the chosen key, Previous is disabled on
// step 1, and the card never renders a gate verb."
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatThread } from "./thread";
import { type QuestionPayload, QuestionCard } from "./question-card";

afterEach(cleanup);

// TPL-04a's ask, verbatim (spec.md ASK CARD): 79 open of 224, 145 done.
const ASK: QuestionPayload = {
  question_id: "q-ty2025-scope",
  n: 1,
  m: 2,
  steps: [
    {
      q: "Which returns should the report cover?",
      preselect: "open",
      options: [
        {
          key: "open",
          title: "Open returns only",
          detail:
            "79 returns still in gather, prepare, review or delivery. This is what office managers act on this week.",
        },
        {
          key: "all",
          title: "All TY2025 returns",
          detail: "All 224 returns, including the 145 already filed or accepted.",
        },
      ],
      other: true,
    },
    {
      q: "Where should I save the workbook?",
      preselect: "files",
      options: [{ key: "files", title: "Files › Firm reports › TY2025 season" }],
    },
  ],
  skipText: "Skip",
  skipDefault: "open",
};

function radios(): HTMLInputElement[] {
  return screen.getAllByRole("radio") as HTMLInputElement[];
}

describe("QuestionCard", () => {
  it("opens on step 1 of 2 with the default chosen and Previous disabled", () => {
    render(<QuestionCard question={ASK} onAnswer={vi.fn()} />);
    expect(screen.getByText("Which returns should the report cover?")).toBeTruthy();
    expect(screen.getByText("1 of 2")).toBeTruthy();
    expect(radios().map((r) => r.checked)).toEqual([true, false]);
    expect((screen.getByRole("button", { name: "Previous" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("Next emits exactly one answer with the chosen key, then moves to step 2", () => {
    const onAnswer = vi.fn();
    render(<QuestionCard question={ASK} onAnswer={onAnswer} />);
    fireEvent.click(radios()[1]!);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onAnswer).toHaveBeenCalledTimes(1);
    expect(onAnswer).toHaveBeenCalledWith({ question_id: "q-ty2025-scope", step: 1, key: "all" });
    expect(screen.getByText("2 of 2")).toBeTruthy();
    expect(screen.getByText("Where should I save the workbook?")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Previous" }) as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  it("answers the last step once, however often Next is pressed", () => {
    const onAnswer = vi.fn();
    render(
      <QuestionCard question={{ ...ASK, steps: [ASK.steps[1]!], n: 2 }} onAnswer={onAnswer} />,
    );
    const next = screen.getByRole("button", { name: "Next" });
    fireEvent.click(next);
    fireEvent.click(next);
    expect(onAnswer).toHaveBeenCalledTimes(1);
    expect(onAnswer).toHaveBeenCalledWith({
      question_id: "q-ty2025-scope",
      step: 2,
      key: "files",
    });
  });

  it("keys 1-9 choose, Enter is Next and Esc returns focus to the composer", () => {
    const onAnswer = vi.fn();
    const onEscape = vi.fn();
    render(<QuestionCard question={ASK} onAnswer={onAnswer} onEscape={onEscape} />);
    const card = screen.getByRole("group");
    fireEvent.keyDown(card, { key: "2" });
    expect(radios().map((r) => r.checked)).toEqual([false, true]);
    fireEvent.keyDown(card, { key: "9" });
    expect(radios().map((r) => r.checked)).toEqual([false, true]);
    fireEvent.keyDown(card, { key: "Escape" });
    expect(onEscape).toHaveBeenCalledTimes(1);
    expect(onAnswer).not.toHaveBeenCalled();
    fireEvent.keyDown(card, { key: "Enter" });
    expect(onAnswer).toHaveBeenCalledWith({ question_id: "q-ty2025-scope", step: 1, key: "all" });
  });

  it("skips only when Skip is pressed", () => {
    const onAnswer = vi.fn();
    render(<QuestionCard question={ASK} onAnswer={onAnswer} />);
    fireEvent.blur(screen.getByRole("group"));
    expect(onAnswer).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(onAnswer).toHaveBeenCalledWith({ question_id: "q-ty2025-scope", skipped: true });
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(onAnswer).toHaveBeenCalledTimes(1);
  });

  it("Something else… hands back to the composer without answering", () => {
    const onAnswer = vi.fn();
    const onSomethingElse = vi.fn();
    render(<QuestionCard question={ASK} onAnswer={onAnswer} onSomethingElse={onSomethingElse} />);
    fireEvent.click(screen.getByRole("button", { name: "Something else…" }));
    expect(onSomethingElse).toHaveBeenCalledWith("q-ty2025-scope", 1);
    expect(onAnswer).not.toHaveBeenCalled();
  });

  it("never renders a gate verb, and the agent's words go through AgentText", () => {
    const { container } = render(<QuestionCard question={ASK} onAnswer={vi.fn()} />);
    for (const verb of ["Approve", "Reject", "Decide", "Sign off", "Release", "Send"]) {
      expect(screen.queryByRole("button", { name: new RegExp(verb, "i") })).toBeNull();
    }
    expect(container.querySelectorAll('[data-actor="agent"]').length).toBeGreaterThanOrEqual(5);
  });

  it("sits above a composer that stays live", () => {
    const onSend = vi.fn();
    render(
      <ChatThread
        items={[]}
        onSend={onSend}
        above={<QuestionCard question={ASK} onAnswer={vi.fn()} />}
      />,
    );
    const composer = screen.getByRole("textbox");
    expect((composer as HTMLTextAreaElement).disabled).toBe(false);
    const order = Array.from(document.querySelectorAll("[data-kit], textarea")).map(
      (n) => n.getAttribute("data-kit") ?? n.tagName.toLowerCase(),
    );
    expect(order.indexOf("QuestionCard")).toBeLessThan(order.indexOf("textarea"));
  });
});
