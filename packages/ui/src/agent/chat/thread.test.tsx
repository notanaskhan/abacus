// F-07-T03 (SPEC-652 AC-4; handoff T4 thread). Acceptance: "Every agent string renders through
// AgentText or AgentBlocks, an unknown item kind renders a neutral row and never raw payload, and
// reduced motion or ?static=1 shows verified text at once."
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatThread, type ThreadItem } from "./thread";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

let n = 0;
function item(kind: string, payload: Record<string, unknown>, actor: ThreadItem["actor_kind"] = "agent"): ThreadItem {
  n += 1;
  return { id: `i${String(n)}`, seq: n, kind, payload: { v: 1, ...payload }, actor_kind: actor, run_id: "run-1" };
}
const p = (text: string) => ({ blocks: { version: 1, parts: [{ kind: "p", segments: [{ kind: "text", text }] }] } });
const LINE = "I'll start with read-only discovery of returns, engagements, binders and offices.";

describe("ChatThread", () => {
  it("agent strings render through AgentText or AgentBlocks; a person's through the me bubble", () => {
    render(
      <ChatThread
        still
        items={[
          item("user_message", { body: "Build an Excel report" }, "human"),
          item("agent_blocks", p(LINE)),
          item("agent_blocks", {
            blocks: {
              version: 1,
              parts: [
                { kind: "p", segments: [{ kind: "text", text: "What I found in Accrued:" }] },
                { kind: "table", head: ["Item", "Result"], rows: [[{ kind: "text", text: "Tax returns" }, { kind: "text", text: "224" }]] },
              ],
            },
          }),
        ]}
      />,
    );
    expect(document.querySelector("[data-bubble='me']")?.textContent).toBe("Build an Excel report");
    expect(document.querySelector("[data-bubble='line'] [data-actor='agent']")?.textContent).toBe(LINE);
    expect(document.querySelector("[data-bubble='block'] [data-agent-blocks='v1']")).not.toBeNull();
  });

  it("an unknown kind or a slot kind with no slot renders a neutral row, never the payload", () => {
    render(
      <ChatThread
        still
        items={[
          item("hologram", { secret: "RAW-PAYLOAD-123" }),
          item("approval", { secret: "RAW-APPROVAL" }),
          item("plan", { steps: ["RAW-PLAN"] }),
          item("agent_blocks", { blocks: "not blocks" }),
        ]}
      />,
    );
    expect(document.querySelectorAll("[data-row='neutral']")).toHaveLength(4);
    expect(document.body.textContent).not.toMatch(/RAW-/);
  });

  it("a registered slot renders its item", () => {
    render(<ChatThread still items={[item("plan", { n: 2 })]} slots={{ plan: () => <p>PLAN SLOT</p> }} />);
    expect(screen.getByText("PLAN SLOT")).toBeTruthy();
  });

  it("?static=1 (still) shows a new line whole at once", () => {
    const first = [item("user_message", { body: "hi" }, "human")];
    const { rerender } = render(<ChatThread still items={first} />);
    rerender(<ChatThread still items={[...first, item("agent_blocks", p(LINE))]} />);
    expect(document.querySelector("[data-bubble='line']")?.textContent).toBe(LINE);
  });

  it("without still, a new line reveals 20 ms a word; history shows whole", () => {
    vi.useFakeTimers();
    const history = [item("agent_blocks", p("Earlier answer in full."))];
    const { rerender } = render(<ChatThread items={history} />);
    expect(document.querySelector("[data-bubble='line']")?.textContent).toBe("Earlier answer in full.");
    rerender(<ChatThread items={[...history, item("agent_blocks", p(LINE))]} />);
    const lines = () => [...document.querySelectorAll("[data-bubble='line']")].map((e) => e.textContent ?? "");
    expect(lines()[1]).toBe("");
    const tick = () => {
      act(() => {
        vi.advanceTimersByTime(20);
      });
    };
    for (let i = 0; i < 3; i += 1) tick();
    expect(lines()[1]).toBe("I'll start with ");
    for (let i = 0; i < 20; i += 1) tick();
    expect(lines()[1]).toBe(LINE);
  });

  it("a failed tool card says what stopped and Retry emits its step once", () => {
    const onRetryStep = vi.fn();
    const onOpenRun = vi.fn();
    const failed = { ...item("tool_card", { label: "Read binder status", state: "failed", error: { title: "Stopped at Read binder status", body: "CCH Axcess token expired on Sep 12." } }), step_id: "step-7" };
    render(<ChatThread still items={[failed]} onRetryStep={onRetryStep} onOpenRun={onOpenRun} />);
    expect(screen.getByRole("alert").textContent).toContain("CCH Axcess token expired on Sep 12.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetryStep).toHaveBeenCalledExactlyOnceWith("step-7");
    fireEvent.click(screen.getByRole("button", { name: "View run" }));
    expect(onOpenRun).toHaveBeenCalledWith("run-1");
  });

  it("the artifact row's intents and the server's badge", () => {
    const onArtifact = vi.fn();
    render(
      <ChatThread
        still
        onArtifact={onArtifact}
        items={[
          item("agent_blocks", { ...p("Season progress, open returns: Gather 10"), badge: "Report prepared" }),
          item("artifact", { artifact_id: "a1", name: "TY2025 Season Progress — by office.xlsx", meta: "Excel · 5 tabs" }),
        ]}
      />,
    );
    expect(document.querySelector("[data-badge]")?.textContent).toBe("✓ Report prepared");
    for (const [name, intent] of [["Open", "open"], ["Download", "download"], ["Save to Files", "save"]] as const) {
      fireEvent.click(screen.getByRole("button", { name }));
      expect(onArtifact).toHaveBeenLastCalledWith("a1", intent);
    }
  });

  it("Enter sends, Shift+Enter does not, an empty composer cannot send", () => {
    const onSend = vi.fn();
    render(<ChatThread still items={[]} onSend={onSend} />);
    const box = screen.getByRole("textbox", { name: "Message" });
    expect((screen.getByRole("button", { name: "Send message" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(box, { target: { value: "How many are open?" } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSend).toHaveBeenCalledExactlyOnceWith("How many are open?");
  });

  it("a locked thread renders no item and no composer (INV-3)", () => {
    render(<ChatThread locked items={[item("agent_blocks", p("224 returns SECRET"))]} />);
    expect(document.body.textContent).not.toContain("SECRET");
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("the kit never renders a decision verb (INV-1)", () => {
    render(
      <ChatThread
        still
        items={[
          item("tool_card", { label: "x", state: "failed" }),
          item("artifact", { artifact_id: "a", name: "f.xlsx" }),
          item("agent_blocks", p("Approve the plan?")),
        ]}
      />,
    );
    const names = screen.getAllByRole("button").map((b) => b.textContent ?? "");
    for (const verb of ["Approve", "Reject", "Decide", "Sign off", "Release", "Send"]) {
      expect(names.some((t) => t.trim().startsWith(verb)), verb).toBe(false);
    }
  });
});
