import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "../components/popover";
import { AGENT_ASSIGNEE, IssueDetail, IssueFooter, type IssueState } from "../issues/issue-kit";
import { T9Board, T9A_CELL_MATCH } from "../specimens/t9";
import { FELD_ISSUES, T9_PEOPLE } from "../specimens/t9-data";
import { installDomShims } from "../test-dom";

// F-05-T55: "T9a to T9e render all three presets with Why This Was Surfaced on an olive disc, and
// the agent can be assigned but is never offered Resolve." Plus each preset's panes, the queue
// variants, the empty detail, the agent working, the instruction composer and the cross-highlight.

beforeAll(installDomShims);
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function board(id: string): HTMLElement {
  const { container } = render(
    <TooltipProvider>
      <T9Board id={id} />
    </TooltipProvider>,
  );
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no board ${id}`);
  return el;
}

const q = (el: HTMLElement, sel: string): HTMLElement => {
  const found = el.querySelector<HTMLElement>(sel);
  if (found === null) throw new Error(`no ${sel}`);
  return found;
};

const HUMAN_VERBS = /^(Resolve|Mark as Resolved|Mark Not Applicable)$/;

describe("T9 QueueDetailLayout", () => {
  it("T9a to T9e render the three presets, each with Why This Was Surfaced on the olive disc", () => {
    const presets: Record<string, string> = {
      t9a: "issues-individual",
      t9b: "close-review",
      t9c: "issues-entity",
      t9d: "issues-individual",
      t9e: "issues-entity",
    };
    for (const [id, preset] of Object.entries(presets)) {
      const el = board(id);
      expect(q(el, "[data-queue]").getAttribute("data-queue"), id).toBe(preset);
      expect(q(el, "[data-split]").getAttribute("data-split"), id).toBe(preset);
      if (id !== "t9d") {
        const why = within(el).getByRole("heading", { name: /Why This Was Surfaced/ });
        const disc = why.querySelector('[role="img"]');
        expect(disc?.getAttribute("aria-label"), id).toBe("Done");
        expect(disc?.className, id).toContain("bg-green");
        expect(why.innerHTML, id).not.toMatch(/sparkles/i);
      }
      cleanup();
    }
  });

  it("T9a individual: the 262 queue card and the detail card sit in the shell well; tree rows", () => {
    const a = board("t9a");
    expect(q(a, '[data-queue-part="well"]').className).toContain("bg-shell");
    expect(q(a, '[data-queue-part="queue"]').style.width).toBe("262px");
    expect(a.querySelectorAll('[data-queue-part="evidence"]')).toHaveLength(2);
    const row = q(a, '[data-issue-row="div3b"]');
    expect(row.getAttribute("aria-current")).toBe("true");
    expect(row.textContent).toContain("Action required");
    expect(within(row).getByLabelText("The agent can fix this")).toBeTruthy();
    expect(q(a, '[data-issue-group="scha"]').textContent).toContain("2 open");
    const detail = q(a, "[data-issue-detail]");
    expect(detail.textContent).toContain("Line 3b is 630 short of the 1099");
    expect(within(detail).getByText("630").className).toContain("font-medium");
    expect(q(a, '[data-issue-cell="Leadsheet!C14"]').textContent).toContain("4,182");
  });

  it("T9a: the workbook cell lights box 1a on the page and worksheet line 3b together", () => {
    const a = board("t9a");
    act(() => {
      fireEvent.click(q(a, '[data-issue-cell="Leadsheet!C14"]'));
    });
    const lit = [...a.querySelectorAll("[data-lit][data-match]")];
    expect(lit.length).toBeGreaterThanOrEqual(2);
    for (const el of lit) expect(el.getAttribute("data-match")).toBe(T9A_CELL_MATCH);
    expect(q(a, '[data-field="ws-3b"]').hasAttribute("data-matched")).toBe(true);
  });

  it("T9b close review: 790 split 310 | 480 beside the register; High 2 · Medium 2 · Low 3", () => {
    const b = board("t9b");
    expect(q(b, '[data-queue-part="split"]')).toBeTruthy();
    expect(q(b, '[data-queue-part="queue"]').style.width).toBe("310px");
    const bands = [...b.querySelectorAll("[data-issue-group] > button")].map((x) => x.textContent);
    expect(bands).toEqual(["High2", "Medium2", "Low3"]);
    expect(q(b, "[data-issue-detail]").getAttribute("data-issue-detail")).toBe("dup");
    expect(q(b, "[data-issue-detail] header").className).toContain("bg-shell");
    expect(b.textContent).toContain("Operating ••4410 · August Register");
    expect(b.querySelector('[data-issue-row="old"]')).toBeNull();
    act(() => {
      fireEvent.click(within(b).getByRole("button", { name: "Show resolved" }));
    });
    expect(q(b, '[data-issue-row="old"]').getAttribute("data-state")).toBe("resolved");
  });

  it("T9c entity: Waiting on the client 7 · Review points 2 · Resolved 1, the composer, Ask the client…", () => {
    const c = board("t9c");
    const bands = [...c.querySelectorAll("[data-issue-group] > button")].map((x) => x.textContent);
    expect(bands).toEqual(["Waiting on the client7", "Review points2", "Resolved1"]);
    expect(c.querySelector('[data-issue-row="ded"]')).toBeNull();
    expect(q(c, '[data-issue-row="rp"]').getAttribute("aria-current")).toBe("true");
    expect(c.querySelector("[data-issue-composer]")).not.toBeNull();
    expect(within(c).getByPlaceholderText("Tell the agent how to fix this…")).toBeTruthy();
    const footer = q(c, "[data-issue-footer]");
    expect(within(footer).getByRole("button", { name: "Ask the client…" })).toBeTruthy();
    expect(within(footer).getByRole("button", { name: "Mark as Resolved" })).toBeTruthy();
  });

  it("T9d empty detail: Nothing selected on the shell colour", () => {
    const d = board("t9d");
    const empty = q(d, '[data-issue-detail="empty"]');
    expect(empty.className).toContain("bg-shell");
    expect(empty.textContent).toContain("Nothing selected");
    expect(empty.textContent).toContain("Pick an issue to see what it blocks.");
    expect(d.querySelector("[data-issue-footer]")).toBeNull();
  });

  it("T9e agent working: the amber pill, its run in AgentText, and no Resolve anywhere", () => {
    const e = board("t9e");
    const detail = q(e, "[data-issue-detail]");
    expect(detail.getAttribute("data-state")).toBe("working");
    expect(q(detail, "[data-issue-working]").className).toContain("amber");
    expect(q(detail, "[data-issue-status]").textContent).toBe("Agent working");
    expect(q(detail, "[data-issue-run]").querySelector('[data-actor="agent"]')).not.toBeNull();
    expect(detail.textContent).toContain("Accrued Agent is fixing this");
    expect(detail.textContent).toContain("The agent can fix this");
    const footer = q(e, "[data-issue-footer]");
    const wait = within(footer).getByRole("button", { name: "Waiting on the agent" });
    expect((wait as HTMLButtonElement).disabled).toBe(true);
    expect(within(e).queryByRole("button", { name: HUMAN_VERBS })).toBeNull();
    expect(e.querySelector("[data-issue-composer]")).toBeNull();
  });

  it("the agent can be assigned: it is the assignee and the first choice in the menu", async () => {
    expect(T9_PEOPLE[0]).toBe(AGENT_ASSIGNEE);
    const onAssign = vi.fn();
    const view = FELD_ISSUES.div3b?.view;
    if (view === undefined) throw new Error("no div3b");
    render(
      <IssueDetail
        issue={{ ...view, assignee: "Samuel Ito" }}
        people={T9_PEOPLE}
        onAssign={onAssign}
      />,
    );
    const trigger = screen.getByRole("button", { name: "Assigned to Samuel Ito. Change" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const item = await screen.findByRole("menuitemradio", { name: AGENT_ASSIGNEE });
    fireEvent.click(item);
    await waitFor(() => {
      expect(onAssign).toHaveBeenCalledWith(AGENT_ASSIGNEE);
    });
  });

  it("the agent is never offered Resolve, Mark as Resolved or Mark Not Applicable (INV-1)", () => {
    for (const kind of ["agent", "review", "client"] as const) {
      for (const state of ["open", "working", "resolved"] as IssueState[]) {
        const { container } = render(
          <IssueFooter actor={{ kind: "agent" }} kind={kind} state={state} onResolve={vi.fn()} />,
        );
        expect(container.innerHTML, `${kind} ${state}`).toBe("");
        cleanup();
      }
    }
    // A person is: a review point offers Resolve and Mark Not Applicable.
    render(
      <IssueFooter actor={{ kind: "human", name: "Samuel Ito" }} kind="review" state="open" />,
    );
    expect(screen.getByRole("button", { name: "Resolve" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Mark Not Applicable" })).toBeTruthy();
  });

  it("T9c: sending fix instructions turns the issue Agent working…, then the agent fixes it", () => {
    vi.useFakeTimers();
    const c = board("t9c");
    act(() => {
      fireEvent.click(q(c, '[data-issue-row="state"]'));
    });
    const input = within(c).getByPlaceholderText("Tell the agent how to fix this…");
    act(() => {
      fireEvent.change(input, { target: { value: "Use the 2025 composite elections" } });
      fireEvent.keyDown(input, { key: "Enter" });
    });
    expect(q(c, "[data-issue-detail]").getAttribute("data-state")).toBe("working");
    expect(q(c, "[data-issue-run]").textContent).toContain("Use the 2025 composite elections");
    act(() => {
      vi.advanceTimersByTime(2800);
    });
    expect(q(c, "[data-issue-detail]").getAttribute("data-state")).toBe("resolved");
    expect(c.textContent).toContain("Fixed by Accrued Agent · State filing decisions");
  });

  it("↓ moves to the next issue and selects it", () => {
    const a = board("t9a");
    const first = q(a, '[data-issue-row="div3b"]');
    first.focus();
    act(() => {
      fireEvent.keyDown(first, { key: "ArrowDown" });
    });
    expect(q(a, '[data-issue-row="basis"]').getAttribute("aria-current")).toBe("true");
    expect(document.activeElement?.getAttribute("data-issue-row")).toBe("basis");
  });
});
