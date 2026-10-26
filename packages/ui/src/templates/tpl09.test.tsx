import { act, cleanup, fireEvent, render, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "../components/popover";
import { COPPERLEAF_BANK_REC } from "../specimens/seed-figures";
import { TPL09A_MATCH, TPL09_K1_FILE, Tpl09Board } from "../specimens/tpl09";
import { CLOSE_COUNTS, FELD_COUNTS, RIDGELINE_COUNTS } from "../specimens/tpl09-data";
import { installDomShims } from "../test-dom";

// F-05-T57: "Counts tie (Feld 4 = 2/1/1, Copperleaf 7 = 2+5, Ridgeline 11 = 5+6) and the bank
// reconciliation shows tie, not Reconciled." The reconciliation's footing is the app's seed test
// (apps/web/src/fixtures/specimen-figures.test.ts, COPPERLEAF_BANK_REC). Plus TPL-09a to TPL-09g:
// the three presets, the agent fixing, the client ask, resolved with Reopen, the empty queue, the
// proposed value's Accept and Reject, and Resolve with a note.

beforeAll(installDomShims);
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function board(id: string): HTMLElement {
  const { container } = render(
    <TooltipProvider>
      <Tpl09Board id={id} />
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

const rows = (el: HTMLElement): HTMLElement[] => [
  ...el.querySelectorAll<HTMLElement>("[data-issue-row]"),
];

const AGENT_VERBS = /^(Approve|Sign off|Release|Send|Post|Decide)\b/;

describe("TPL-09 acceptance", () => {
  it("TPL-09 acceptance: counts tie (Feld 4 = 2/1/1, Copperleaf 7 = 2+5, Ridgeline 11 = 5+6)", () => {
    expect([FELD_COUNTS.missing, FELD_COUNTS.action, FELD_COUNTS.review]).toEqual([2, 1, 1]);
    expect([CLOSE_COUNTS.medium, CLOSE_COUNTS.low]).toEqual([2, 5]);
    expect([RIDGELINE_COUNTS.waiting, RIDGELINE_COUNTS.review]).toEqual([5, 6]);

    const a = board("tpl-09a");
    expect(rows(a)).toHaveLength(4);
    expect(within(a).getByRole("tab", { name: /Issues/ }).textContent).toContain("4");
    const subs = rows(a).map((r) => r.textContent);
    expect(subs.filter((t) => t.includes("Missing Information"))).toHaveLength(2);
    expect(subs.filter((t) => t.includes("Action Required"))).toHaveLength(1);
    expect(subs.filter((t) => t.includes("Review Point"))).toHaveLength(1);
    cleanup();

    const b = board("tpl-09b");
    expect(rows(b)).toHaveLength(7);
    expect(q(b, '[data-issue-group="med"]').textContent).toMatch(/Medium\s*2/);
    expect(q(b, '[data-issue-group="low"]').textContent).toMatch(/Low\s*5/);
    expect(within(b).getByRole("tab", { name: /Review/ }).textContent).toContain("7");
    expect(b.textContent).toContain(
      "Payroll up 12.5% on July — new hires, merit increases and overtime",
    );
    cleanup();

    const c = board("tpl-09c");
    expect(rows(c)).toHaveLength(11);
    expect(within(q(c, '[data-issue-group="wait"]')).getAllByRole("button")).toHaveLength(1 + 5);
    const review = q(c, '[data-issue-group="rev"]');
    expect(review.querySelectorAll("[data-issue-row]")).toHaveLength(6);
    expect(review.textContent).toContain(
      "Schedules K-2/K-3 required — domestic filing exception unavailable",
    );
    expect(within(c).getByRole("tab", { name: /Issues/ }).textContent).toContain("11");
  });

  it("TPL-09 acceptance: the bank reconciliation shows tie, not Reconciled", () => {
    const b = board("tpl-09b");
    const rec = q(b, "[data-bank-rec]");
    const diff = q(rec, '[data-rec-row="diff"]');
    expect(diff.textContent).toContain("$0.00");
    expect(q(diff, "[data-rec-tally]").textContent).toBe("tie");
    expect(rec.textContent).not.toMatch(/Reconciled/);
    expect(q(rec, '[data-rec-row="adjbank"]').textContent).toContain("$184,990.50");
    expect(q(rec, '[data-rec-row="adjbook"]').textContent).toContain("$184,990.50");
    expect(q(rec, '[data-rec-row="toc"]').textContent).toContain("($5,658.08)");
    expect(COPPERLEAF_BANK_REC.difference).toBe("0.00");
    // #2281 is the selected issue: its stale row is flagged and selected.
    const stale = q(rec, '[data-rec-row="ck2281"]');
    expect(stale.className).toContain("bg-sel-bg");
    expect(within(stale).getByLabelText("Flagged")).toBeTruthy();
  });
});

describe("TPL-09 artboards", () => {
  it("TPL-09a Issues · individual: the tree, the 18A detail, the lit chip and the ghost value", () => {
    const a = board("tpl-09a");
    expect(q(a, "[data-queue]").getAttribute("data-queue")).toBe("issues-individual");
    expect(q(a, '[data-queue-part="queue"]').style.width).toBe("262px");
    expect(a.querySelectorAll("[data-issue-sub]")).toHaveLength(3);
    expect(q(a, '[data-issue-group="general"]').textContent).toContain(
      "Payments, Penalties & Estimates",
    );
    const k18 = q(a, '[data-issue-row="k18"]');
    expect(k18.getAttribute("aria-current")).toBe("true");
    expect(within(k18).getByLabelText("The agent can fix this")).toBeTruthy();
    const detail = q(a, "[data-issue-detail]");
    expect(q(detail, "[data-issue-summary]").textContent).toContain(
      "18A Tax-exempt interest = 1,550",
    );
    expect(within(detail).getByText("18A Tax-exempt interest = 1,550").className).toContain(
      "font-medium",
    );
    expect(detail.textContent).toMatch(/Priority\s*High/);
    expect(detail.querySelector("[data-issue-why]")).toBeNull();
    expect(q(detail, `[data-issue-link="${TPL09_K1_FILE}"]`)).toBeTruthy();
    // The chip lights the K-1's box 18A region and worksheet line 2a with it (one match, INV-2).
    act(() => {
      fireEvent.click(q(detail, `[data-issue-link="${TPL09_K1_FILE}"]`));
    });
    const lit = [...a.querySelectorAll("[data-lit][data-match]")];
    expect(lit.length).toBeGreaterThanOrEqual(1);
    for (const el of lit) expect(el.getAttribute("data-match")).toBe(TPL09A_MATCH);
    expect(q(detail, `[data-issue-link="${TPL09_K1_FILE}"]`).className).toContain("bg-match-bg");
    const ghost = q(a, '[data-field="line2a"]');
    expect(q(ghost, "[data-field-proposed]")).toBeTruthy();
    expect(q(ghost, "[data-field-value]").className).toContain("border-dashed");
    expect(q(ghost, "[data-field-value]").textContent).toBe("1,550");
    // The footer: Set Fix Instructions, Explain…, Mark as Resolved.
    const names = within(a)
      .getAllByRole("button")
      .map((b) => b.textContent.trim());
    expect(names).toEqual(expect.arrayContaining(["Set Fix Instructions", "Explain…"]));
    expect(names.some((n) => AGENT_VERBS.test(n))).toBe(false);
  });

  it("TPL-09a: Accept the proposed value creates a checkpoint; Reject leaves line 2a blank", () => {
    const a = board("tpl-09a");
    fireEvent.click(within(q(a, '[data-field="line2a"]')).getByRole("button", { name: "Accept" }));
    expect(a.querySelector("[data-field-proposed]")).toBeNull();
    expect(q(a, '[data-field="line2a"] [data-field-value]').textContent).toBe("1,550");
    expect(a.textContent).toContain("Checkpoint created · 1,550 added to Form 1040 line 2a");
    cleanup();
    const b = board("tpl-09a");
    fireEvent.click(within(q(b, '[data-field="line2a"]')).getByRole("button", { name: "Reject" }));
    expect(q(b, '[data-field="line2a"] [data-field-value]').textContent).toBe("");
    expect(b.textContent).toContain("Proposed value rejected");
  });

  it("TPL-09a: Mark as Resolved needs a note before Resolve", () => {
    const a = board("tpl-09a");
    fireEvent.click(within(a).getByRole("button", { name: "Mark as Resolved" }));
    const form = q(a, "[data-issue-note]");
    const resolve = within(form).getByRole("button", { name: "Resolve" });
    expect(resolve.hasAttribute("disabled")).toBe(true);
    fireEvent.change(within(form).getByPlaceholderText("Add a resolution note"), {
      target: { value: "Added 18A to line 2a" },
    });
    fireEvent.click(within(form).getByRole("button", { name: "Resolve" }));
    expect(q(a, "[data-issue-detail]").getAttribute("data-state")).toBe("resolved");
    expect(q(a, '[data-issue-row="k18"]').textContent).toContain("Resolved");
    fireEvent.click(within(a).getByRole("button", { name: "Reopen" }));
    expect(q(a, "[data-issue-detail]").getAttribute("data-state")).toBe("open");
  });

  it("TPL-09b Close review: the 790 split, Why This Was Surfaced on the olive disc, the account", () => {
    const b = board("tpl-09b");
    expect(q(b, "[data-queue]").getAttribute("data-queue")).toBe("close-review");
    expect(q(b, '[data-queue-part="queue"]').style.width).toBe("310px");
    const detail = q(b, "[data-issue-detail]");
    expect(detail.textContent).toContain("Outstanding check #2281 dated Feb 2026 has not cleared");
    expect(detail.textContent).toMatch(/Severity\s*Low/);
    expect(detail.textContent).toMatch(/Account\s*Operating Checking \(Front Range Bank\) ••4410/);
    const why = within(detail).getByRole("heading", { name: /Why This Was Surfaced/ });
    expect(why.querySelector('[role="img"]')?.getAttribute("aria-label")).toBe("Done");
    expect(why.innerHTML).not.toMatch(/sparkles/i);
    expect(q(detail, "[data-issue-why]").textContent).toContain("Confirm with Ben Ashby");
    const entity = q(detail, "[data-issue-entity]");
    expect(entity.textContent).toContain("1 reconciling item");
    const names = within(b)
      .getAllByRole("button")
      .map((x) => x.textContent.trim());
    expect(names).toEqual(expect.arrayContaining(["Resolve", "Mark Not Applicable"]));
  });

  it("TPL-09b: Mark Not Applicable drops the issue unless Show resolved is on", () => {
    const b = board("tpl-09b");
    fireEvent.click(within(b).getByRole("button", { name: "Mark Not Applicable" }));
    expect(b.querySelector('[data-issue-row="ck"]')).toBeNull();
    expect(q(b, '[data-issue-group="low"]').textContent).toMatch(/Low\s*4/);
    fireEvent.click(within(b).getByRole("button", { name: "Show resolved" }));
    expect(q(b, '[data-issue-row="ck"]').textContent).toContain("Resolved ·");
  });

  it("TPL-09c Issues · entity: radio bands, What it blocks, the seven workbook cells, Resolve", () => {
    const c = board("tpl-09c");
    expect(q(c, "[data-queue]").getAttribute("data-queue")).toBe("issues-entity");
    const detail = q(c, "[data-issue-detail]");
    expect(q(detail, "[data-issue-blocks]").textContent).toContain("6,866,200");
    expect(detail.querySelectorAll("[data-issue-cell]")).toHaveLength(7);
    expect(q(detail, '[data-issue-cell="07 M-2!C9"]')).toBeTruthy();
    expect(detail.textContent).toMatch(/Severity\s*Review point/);
    expect(within(c).getByPlaceholderText("Tell the agent how to fix this…")).toBeTruthy();
    expect(within(c).getByRole("button", { name: "Resolve" })).toBeTruthy();
    expect(c.querySelector("[data-issue-footer]")).toBeNull();
  });

  it("TPL-09d Agent fixing: Agent working… and the run row Adding 1,550 to Form 1040 line 2a", () => {
    const d = board("tpl-09d");
    const detail = q(d, "[data-issue-detail]");
    expect(detail.getAttribute("data-state")).toBe("working");
    expect(q(detail, "[data-issue-working]").textContent).toContain("Agent working…");
    expect(q(detail, "[data-issue-run]").textContent).toContain(
      "Adding 1,550 to Form 1040 line 2a",
    );
    expect(within(d).getByRole("button", { name: "Waiting on the agent" })).toBeTruthy();
    expect(within(d).queryByRole("button", { name: "Set Fix Instructions" })).toBeNull();
  });

  it("TPL-09a: Set Fix Instructions runs the agent, then the issue resolves and 2a is filled", () => {
    vi.useFakeTimers();
    const a = board("tpl-09a");
    fireEvent.click(within(a).getByRole("button", { name: "Set Fix Instructions" }));
    expect(q(a, "[data-issue-detail]").getAttribute("data-state")).toBe("working");
    act(() => {
      vi.advanceTimersByTime(2400);
    });
    expect(q(a, "[data-issue-detail]").getAttribute("data-state")).toBe("resolved");
    expect(a.querySelector("[data-field-proposed]")).toBeNull();
  });

  it("TPL-09e Waiting on client: Ask the client… creates the portal request", () => {
    const e = board("tpl-09e");
    const detail = q(e, "[data-issue-detail]");
    expect(detail.textContent).toContain("Form 1040 line 26");
    expect(detail.textContent).toMatch(/Priority\s*Medium/);
    fireEvent.click(within(e).getByRole("button", { name: "Ask the client…" }));
    expect(within(e).getByRole("button", { name: "Request sent" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(e.textContent).toContain(
      "Request sent to the Feld portal · estimated payment confirmations",
    );
  });

  it("TPL-09f Resolved: the title in ink-2, the Resolved pill, the olive disc row, Reopen", () => {
    const f = board("tpl-09f");
    const detail = q(f, "[data-issue-detail]");
    expect(detail.getAttribute("data-state")).toBe("resolved");
    expect(q(detail, "h3").className).toContain("text-ink-2");
    expect(detail.textContent).toMatch(/Status\s*Resolved/);
    expect(q(f, '[data-issue-row="tei"]').getAttribute("data-state")).toBe("resolved");
    expect(within(f).queryByPlaceholderText("Tell the agent how to fix this…")).toBeNull();
    fireEvent.click(within(f).getByRole("button", { name: "Reopen" }));
    expect(q(f, "[data-issue-detail]").getAttribute("data-state")).toBe("open");
  });

  it("TPL-09g Empty queue: No open issues., a blank detail and the Review tab without a count", () => {
    const g = board("tpl-09g");
    expect(g.textContent).toContain("No open issues.");
    expect(g.textContent).toContain("Issues raised by the agent or reviewers appear here.");
    expect(rows(g)).toHaveLength(0);
    expect(q(g, '[data-issue-detail="blank"]').className).toContain("bg-shell");
    expect(within(g).getByRole("tab", { name: /Review/ }).textContent).toBe("Review");
    // The reconciliation still stands beside it.
    expect(q(g, '[data-rec-row="diff"] [data-rec-tally]').textContent).toBe("tie");
  });
});
