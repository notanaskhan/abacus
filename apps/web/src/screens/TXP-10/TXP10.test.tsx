// T-05-T58 (TASK-7945; docs/screens/TXP-10.md; handoff TXP-10 A, A2, B, C, D, E, F): "The fix
// journey from A to D runs live on staging and the badge reads 10 afterwards." Here: each state
// from the fixtures (the server's shapes), the moves calling their host callbacks; the staging
// walk is the end pass's.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ASSIGNEES,
  ELECTION_754,
  TAX_EXEMPT,
  issueDetail,
  ridgelineIssues,
} from "../../fixtures/seed/tax-entity-issues";
import { COPY } from "./copy";
import { TXP10, type TXP10Props } from ".";

afterEach(cleanup);

function at(state: "a" | "b" | "c" | "d" | "f", over: Partial<TXP10Props> = {}) {
  const selectedId = state === "b" ? ELECTION_754 : state === "f" ? null : TAX_EXEMPT;
  return render(
    <TXP10
      queue={ridgelineIssues(state, over.showResolved ?? false)}
      selectedId={selectedId}
      detail={selectedId === null ? undefined : issueDetail(selectedId, state)}
      assignees={ASSIGNEES.items}
      showResolved={false}
      query=""
      {...over}
    />,
  );
}

describe("TXP-10 Return › Issues (1065)", () => {
  it("A: 5 waiting on the client + 6 review points = 11, the badge", () => {
    at("a");
    const counts = [...document.querySelectorAll("[data-section] h3")].map((h) => h.textContent);
    expect(counts).toEqual(["Waiting on the client5", "Review points6"]);
    expect(document.querySelector("[data-screen='TXP-10']")?.getAttribute("data-badge")).toBe("11");
    expect(screen.getByText(COPY.whatItBlocks)).toBeTruthy();
    expect(document.querySelectorAll("[data-cell]").length).toBe(7);
  });

  it("A2: the proposed fix opens SHL-10 (only a person approves)", () => {
    const review = vi.fn();
    at("a", { onReviewFix: review });
    fireEvent.click(screen.getByRole("button", { name: COPY.reviewFix }));
    expect(review).toHaveBeenCalledWith(expect.any(String));
  });

  it("a cell opens TXP-11 on it; the composer opens SHL-15", () => {
    const cell = vi.fn();
    const instruct = vi.fn();
    at("a", { onOpenCell: cell, onInstruct: instruct });
    fireEvent.click(document.querySelector("[data-cell='07 M-2!C9']") as Element);
    expect(cell).toHaveBeenCalledWith("07 M-2", "C9");
    fireEvent.click(screen.getByText(COPY.composer));
    expect(instruct).toHaveBeenCalledWith(TAX_EXEMPT);
  });

  it("the assignee picker lists the team, the Accrued Agent and the client contact", () => {
    const assign = vi.fn();
    at("a", { onAssign: assign });
    fireEvent.click(screen.getByRole("button", { name: /Accrued Agent/ }));
    fireEvent.click(screen.getByRole("option", { name: /Samuel Ito/ }));
    expect(assign).toHaveBeenCalledWith(expect.objectContaining({ id: TAX_EXEMPT }), ASSIGNEES.items[1]);
  });

  it("B: the waiting item shows its POR-04 preview and Send reminder", () => {
    const remind = vi.fn();
    at("b", { onRemind: remind });
    expect(document.querySelector("[data-por04-preview]")?.textContent).toContain("§754 decision");
    fireEvent.click(screen.getByRole("button", { name: COPY.sendReminder }));
    expect(remind).toHaveBeenCalled();
  });

  it("C: after Approve fix the agent fixing row runs, never amber", () => {
    at("c");
    expect(document.querySelector("[data-agent-fixing]")?.textContent).toContain(
      "Writing 05 Capital!H8:H12 and 07 M-2!C9",
    );
    expect(document.querySelector("[data-status]")?.getAttribute("data-status")).toBe("in_progress");
  });

  it("D: resolved by Samuel Ito; the badge reads 10", () => {
    at("d", { showResolved: true });
    expect(document.querySelector("[data-screen='TXP-10']")?.getAttribute("data-badge")).toBe("10");
    expect(screen.getAllByText(COPY.resolved).length).toBeGreaterThan(0);
  });

  it("Resolve asks for a note and calls the host", () => {
    const resolve = vi.fn();
    at("a", { onResolve: resolve });
    fireEvent.click(screen.getByRole("button", { name: COPY.resolve }));
    const note = within(screen.getByRole("dialog", { name: COPY.noteLabel }));
    fireEvent.change(note.getByRole("textbox"), { target: { value: "Settled by the fix." } });
    fireEvent.click(note.getByRole("button", { name: COPY.confirmResolve }));
    expect(resolve).toHaveBeenCalledWith(expect.objectContaining({ id: TAX_EXEMPT }), "Settled by the fix.");
  });

  it("E and F: no issue selected, and no open issues", () => {
    render(
      <TXP10 queue={ridgelineIssues("a")} selectedId={null} detail={undefined} showResolved={false} query="" />,
    );
    expect(screen.getByText(COPY.selectIssue)).toBeTruthy();
    cleanup();
    at("f");
    expect(screen.getAllByText(COPY.noOpen).length + screen.getAllByText(COPY.selectIssue).length).toBeGreaterThan(0);
  });
});
