// F-07-T05 (ADR-078; TASK-7420): independent acceptance tests for the T4 chat kit, written from
// SPEC-652 (AC-1 to AC-5) and F-07 §3 A–C against the package's public exports, not the files.
// Acceptance: "Tests fail if an agent-owned element exposes Approve, Sign off, Release or Send, if
// agent text bypasses AgentText, if a locked thread shows figures, or if a default answer is applied
// without an explicit Skip."
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatHeader, ChatThread, SessionList, type ThreadItem, WorkbenchLayout } from "../../index";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const VERBS = ["Approve", "Sign off", "Release", "Send"] as const;
const SENTINEL = "Sentinel agent sentence 4729";

let n = 0;
function item(kind: string, payload: Record<string, unknown>, actor: ThreadItem["actor_kind"] = "agent"): ThreadItem {
  n += 1;
  return { id: `ac${String(n)}`, seq: n, kind, payload: { v: 1, ...payload }, actor_kind: actor, run_id: "r" };
}
const para = (text: string) => ({ blocks: { version: 1, parts: [{ kind: "p", segments: [{ kind: "text", text }] }] } });

function everything(extra: ThreadItem[] = []): ThreadItem[] {
  return [
    item("user_message", { body: "Send me the report" }, "human"),
    item("agent_blocks", para(`${SENTINEL}. Approve, sign off, release or send nothing.`)),
    item("agent_blocks", {
      blocks: {
        version: 1,
        parts: [
          { kind: "p", segments: [{ kind: "text", text: `${SENTINEL} in a block` }] },
          { kind: "table", head: ["Item", "Result"], rows: [[{ kind: "text", text: "Tax returns" }, { kind: "text", text: `${SENTINEL} 224` }]] },
        ],
      },
      badge: "Report prepared",
    }),
    item("tool_card", { label: "Read 79 open returns", state: "succeeded" }),
    item("tool_card", { label: "Read binder status", state: "failed", error: { title: "Stopped at Read binder status", body: "CCH Axcess token expired on Sep 12." } }),
    item("artifact", { artifact_id: "a", name: "TY2025 Season Progress — by office.xlsx", meta: "Excel · 5 tabs" }),
    item("notice", { text: "§7216 consent required" }, "system"),
    item("question", { steps: [{ q: "Which returns should the report cover?", preselect: "open" }], skipDefault: "open" }),
    item("approval", { decision: "approve" }),
    item("decision_ref", { decision: "decide" }),
    item("run_card", { run: "r" }),
    ...extra,
  ];
}

describe("T4 chat kit: independent acceptance (ADR-078)", () => {
  it("no element the kit draws exposes Approve, Sign off, Release or Send (INV-1)", () => {
    render(
      <WorkbenchLayout
        tab="sessions"
        list={
          <SessionList
            still
            rows={[{ id: "s", title: "Season progress", owner: { kind: "agent_assisted", person: "Hannah Leclerc" }, last_at: "2026-09-14T14:00:00Z", state: "awaiting_answer", needs_answer: true, running: false, locked: false }]}
          />
        }
        chat={
          <>
            <ChatHeader title="TY2025 season progress by office" owner={{ kind: "human", name: "Hannah Leclerc" }} live still />
            <ChatThread still items={everything()} />
          </>
        }
      />,
    );
    const controls = [...screen.getAllByRole("button"), ...screen.queryAllByRole("link"), ...screen.queryAllByRole("menuitem")];
    for (const c of controls) {
      const name = (c.getAttribute("aria-label") ?? c.textContent ?? "").trim();
      for (const verb of VERBS) {
        // "Send message" is the person's own composer, not a decision on agent output.
        if (name === "Send message") continue;
        expect(name.startsWith(verb), `${name} exposes ${verb}`).toBe(false);
      }
    }
    for (const agentEl of document.querySelectorAll("[data-actor='agent'], [data-agent-blocks]")) {
      expect(agentEl.querySelectorAll("button, a, [role='button']")).toHaveLength(0);
    }
  });

  it("every agent string is inside AgentText or AgentBlocks", () => {
    render(<ChatThread still items={everything()} />);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let found = 0;
    for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
      if (!(node.textContent ?? "").includes(SENTINEL)) continue;
      found += 1;
      const owner = node.parentElement?.closest("[data-actor='agent'], [data-agent-blocks]");
      expect(owner, `"${node.textContent ?? ""}" bypasses AgentText`).not.toBeNull();
    }
    expect(found).toBeGreaterThanOrEqual(3);
  });

  it("a person's message is never drawn as agent text", () => {
    render(<ChatThread still items={[item("user_message", { body: "Person words 818" }, "human")]} />);
    const el = screen.getByText("Person words 818");
    expect(el.closest("[data-actor='agent']")).toBeNull();
  });

  it("a locked thread shows no figure anywhere: frame, list row, header or thread (INV-3)", () => {
    render(
      <WorkbenchLayout
        tab="sessions"
        viewState="restricted"
        list={<SessionList rows={[]} />}
        chat={<ChatThread locked items={everything([item("agent_blocks", para("Copperleaf payroll 2,625,000"))])} />}
      />,
    );
    expect(document.body.textContent ?? "").not.toMatch(/\d{2,}/);
    cleanup();
    render(<ChatThread locked items={everything([item("agent_blocks", para("Copperleaf payroll 2,625,000"))])} />);
    expect(document.body.textContent ?? "").not.toMatch(/2,625,000|224|79/);
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("an open question's default is never applied by time, blur or navigation (only Skip)", () => {
    vi.useFakeTimers();
    const onSend = vi.fn();
    const answers: unknown[] = [];
    const question = item("question", {
      question_id: "q1",
      steps: [{ q: "Which returns should the report cover?", preselect: "open", options: [{ key: "open", title: "Open returns only" }, { key: "all", title: "All TY2025 returns" }] }],
      skipText: "Skip",
      skipDefault: "open",
    });
    render(
      <ChatThread
        items={[question]}
        onSend={onSend}
        slots={{ question: () => <p data-question-slot>question</p> }}
        onArtifact={(...a) => answers.push(a)}
        onRetryStep={(...a) => answers.push(a)}
      />,
    );
    act(() => {
      vi.advanceTimersByTime(10 * 60 * 1000);
    });
    fireEvent.blur(screen.getByRole("textbox", { name: "Message" }));
    window.dispatchEvent(new Event("pagehide"));
    expect(onSend).not.toHaveBeenCalled();
    expect(answers).toEqual([]);
    expect(document.querySelector("[data-item='answer']")).toBeNull();
  });

  it("the session list's meta lines name people, never the agent as an owner (INV-5)", () => {
    render(
      <SessionList
        still
        rows={[
          { id: "1", title: "a", owner: { kind: "human", name: "Marcus Delaney" }, last_at: "2026-09-13T15:00:00Z", state: "live", needs_answer: false, running: false, locked: false },
          { id: "2", title: "b", owner: { kind: "agent_assisted", person: "Grace Holloway" }, last_at: "2026-09-13T13:00:00Z", state: "complete", needs_answer: false, running: false, locked: false },
        ]}
      />,
    );
    const metas = [...document.querySelectorAll("[data-meta]")].map((m) => m.textContent ?? "");
    expect(metas.some((m) => m.endsWith("Grace Holloway via Agent"))).toBe(true);
    expect(metas.every((m) => !m.endsWith("Accrued Agent"))).toBe(true);
  });
});
