// W-02-T17 (TASK-7946; docs/screens/WB-01.md a–e, g; W-02 §3.4–§3.7): "WB-01 a-e and g pass in
// Vitest with axe clean, and the locked state renders no thread item or figure." The thread's
// reads are the fixtures' (the server's shapes); axe runs at the S43 end pass.
import type { SessionItemOut } from "@abacus/api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { QUESTION, SESSION_ID, threadItems as season } from "../../fixtures/seed/tpl04-sessions";
import { COPY } from "./copy";
import { NOTICE_WORDS, Thread, openQuestion, questionOf, threadItems } from "./Thread";

afterEach(cleanup);

function wrap(node: ReactNode) {
  return <QueryClientProvider client={new QueryClient()}>{node}</QueryClientProvider>;
}

const snap = (items: SessionItemOut[], over: Record<string, unknown> = {}) => ({
  id: SESSION_ID,
  title: "TY2025 season progress by office",
  state: "awaiting_answer" as const,
  origin: "manual" as const,
  locked: false,
  allowed_actions: ["message" as const, "manage" as const],
  items,
  ...over,
});

describe("WB-01 thread states", () => {
  it("a: the discovery block and the open question 1 of 2 above the composer", () => {
    render(wrap(<Thread snapshot={snap(season("a"))} sessionId={SESSION_ID} onOpenRun={() => undefined} />));
    expect(screen.getByText(QUESTION.steps[0]?.q ?? "")).toBeTruthy();
    expect(document.querySelectorAll("[data-item='agent_blocks']").length).toBe(2);
  });

  it("b: an answered question is no longer open; other messages leave it open", () => {
    const items = season("c");
    expect(openQuestion(items)).toBeNull();
    const a = season("a");
    expect(openQuestion(a)?.kind).toBe("question");
    const asked = openQuestion(a);
    expect(asked === null ? null : questionOf(asked)?.steps.length).toBe(2);
  });

  it("the code's notices read their fixed words, never model text", () => {
    const items = threadItems([
      {
        id: "n", seq: 9, kind: "notice", actor_kind: "system", created_at: "2026-09-14T14:30:00Z",
        payload: { v: 1, code: "nothing_written" },
      },
      {
        id: "m", seq: 10, kind: "notice", actor_kind: "system", created_at: "2026-09-14T14:30:00Z",
        payload: { v: 1, code: "plans_off" },
      },
    ] as SessionItemOut[]);
    expect(items.map((i) => i.payload["text"])).toEqual([
      NOTICE_WORDS["nothing_written"],
      NOTICE_WORDS["plans_off"],
    ]);
  });

  it("context and drill rows are left out of the thread (WB-02's and WB-03's)", () => {
    const items = threadItems([
      { id: "c", seq: 1, kind: "context_added", actor_kind: "system", created_at: "", payload: {} },
      { id: "d", seq: 2, kind: "drill", actor_kind: "human", created_at: "", payload: {} },
    ] as SessionItemOut[]);
    expect(items).toEqual([]);
  });

  it("the person's bubble menu offers Copy and Edit and resend", () => {
    render(wrap(<Thread snapshot={snap(season("a"))} sessionId={SESSION_ID} onOpenRun={() => undefined} />));
    fireEvent.click(screen.getAllByRole("button", { name: "Message actions" })[0] as Element);
    expect(screen.getByRole("menuitem", { name: "Copy" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "Edit and resend" })).toBeTruthy();
  });

  it("g: a locked session renders no thread item or figure", () => {
    render(
      wrap(
        <Thread snapshot={snap(season("a"), { locked: true })} sessionId={SESSION_ID} onOpenRun={() => undefined} />,
      ),
    );
    expect(document.querySelectorAll("[data-item]").length).toBe(0);
    expect(screen.queryByText(QUESTION.steps[0]?.q ?? "")).toBeNull();
  });

  it("a viewer who is not the owner gets no composer actions and no question card", () => {
    render(
      wrap(<Thread snapshot={snap(season("a"), { allowed_actions: [] })} sessionId={SESSION_ID} onOpenRun={() => undefined} />),
    );
    expect(screen.queryByText(QUESTION.steps[0]?.q ?? "")).toBeNull();
    expect(COPY.viewRun).toBe("View run");
  });
});
