// I-02-T17 (TASK-7943; docs/screens/SHL-23.md, HOME-05.md; SPEC-654 §3.5–§3.8): "Daniel creates the
// to-do 'Approve the M-2 fix — Ridgeline Capital Accounts' for Samuel Ito due Sep 15 by pressing
// Create, Basis reads 'Reserved to you — not assignable', and the 9:26 answer shows its three
// citation chips." The words and figures are the fixtures' (the server's); nothing is composed.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HISTORY, TODAY_SESSION, danielToday, ridgelineDrill } from "../../fixtures/seed/today";
import { COPY } from "./copy";
import { AskThread, AssignSheet, TodayDrill, TodayHistory } from "./drill";
import { TodayPanel } from ".";

afterEach(cleanup);

describe("SHL-23 drill-in, assign, history and ask", () => {
  it("2: the drill-in reads its narrative, blockers, downstream and Open return", () => {
    const open = vi.fn();
    const back = vi.fn();
    render(<TodayDrill drill={ridgelineDrill()} onBack={back} onOpen={open} />);
    expect(screen.getByText("Ridgeline Property Partners, LP · 2025 Form 1065")).toBeTruthy();
    expect(document.querySelectorAll("[data-blocker]").length).toBe(2);
    expect(screen.getByText(COPY.waitingDownstream)).toBeTruthy();
    expect(screen.getByText("Feld 2025 Form 1040")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Open return/ }));
    expect(open).toHaveBeenCalledWith(ridgelineDrill().open_href);
    fireEvent.click(screen.getByRole("button", { name: /Today/ }));
    expect(back).toHaveBeenCalled();
  });

  it("Basis reads 'Reserved to you — not assignable'; Capital Accounts does not", () => {
    render(<TodayDrill drill={ridgelineDrill()} onBack={() => undefined} />);
    const reserved = [...document.querySelectorAll("[data-reserved]")];
    expect(reserved.map((r) => r.textContent)).toEqual(["Reserved to you — not assignable"]);
    expect(reserved[0]?.closest("[data-blocker]")?.textContent).toContain("Basis");
  });

  it("Assign: the prefill is SHL-17's new to-do; the person presses Create", () => {
    const [prefill] = ridgelineDrill().prefills ?? [];
    if (prefill === undefined) throw new Error("the drill has a prefill");
    const create = vi.fn();
    render(
      <AssignSheet
        prefill={prefill}
        position={0}
        of={1}
        onCreate={create}
        onSkip={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(screen.getByText("Approve the M-2 fix — Ridgeline Capital Accounts")).toBeTruthy();
    expect(screen.getByText("Samuel Ito")).toBeTruthy();
    expect(screen.getByText("2026-09-15")).toBeTruthy();
    expect(create).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: COPY.create }));
    expect(create).toHaveBeenCalledWith(prefill);
  });

  it("3: the 9:26 answer shows the bubble and its three citation chips", () => {
    render(<AskThread items={TODAY_SESSION.items} pending={null} />);
    expect(
      screen.getByText("What happens if Samuel doesn't approve the M-2 fix today?"),
    ).toBeTruthy();
    const answer = document.querySelector("[data-answer]");
    expect(answer?.textContent).toContain("Capital Accounts stays blocked");
    expect(answer?.querySelectorAll("[data-cite], button").length).toBeGreaterThanOrEqual(3);
  });

  it("a request to act shows the read-only notice pointing to sign-off", () => {
    const open = vi.fn();
    render(
      <AskThread
        items={[
          {
            id: "n1",
            seq: 4,
            kind: "notice",
            actor_kind: "system",
            created_at: "2026-09-14T14:27:00Z",
            payload: { v: 1, code: "today_read_only" },
          },
        ]}
        pending={null}
        onOpen={open}
      />,
    );
    expect(screen.getByText(COPY.readOnly)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: COPY.openSignOff }));
    expect(open).toHaveBeenCalled();
  });

  it("History lists earlier briefs; a past brief reads only (no composer, no rebuild)", () => {
    const pick = vi.fn();
    render(<TodayHistory page={HISTORY} onBack={() => undefined} onPick={pick} />);
    fireEvent.click(screen.getByText("2026-09-11"));
    expect(pick).toHaveBeenCalledWith(HISTORY.items[0]?.brief_id);
    cleanup();
    const vm = { ...danielToday(), availability: { narrative: true, ask: true } };
    render(<TodayPanel vm={vm} readOnlyLine={COPY.pastBrief("2026-09-11")} />);
    expect(screen.getByText(COPY.pastBrief("2026-09-11"))).toBeTruthy();
    expect(screen.queryByPlaceholderText(COPY.ask)).toBeNull();
    expect(screen.queryByRole("button", { name: COPY.more })).toBeNull();
  });

  it("a High risk card drills in, and Assign goes straight to the prefill", () => {
    const drill = vi.fn();
    render(<TodayPanel vm={danielToday()} onDrill={drill} />);
    fireEvent.click(screen.getByText("Ridgeline K-1 release — Sep 15"));
    expect(drill).toHaveBeenLastCalledWith(expect.any(String), false);
    fireEvent.click(screen.getByRole("button", { name: COPY.assign }));
    expect(drill).toHaveBeenLastCalledWith(expect.any(String), true);
  });
});
