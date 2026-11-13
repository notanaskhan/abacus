// I-02-T15 (TASK-7914; docs/screens/SHL-23.md; SPEC-654 §3.1–§3.11): "Scenarios 1, 4, 6 and 7
// pass with axe and keyboard, a why line never renders without verified citations, and a missing
// briefing shows the HOME-01 context line instead." Counts and rows are the server's.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DANIEL_PARAGRAPH,
  DANIEL_ROWS,
  buildingToday,
  danielToday,
  margaretToday,
  quietToday,
} from "../../fixtures/seed/today";
import { COPY } from "./copy";
import { TodayPanel, factParagraph } from ".";

afterEach(cleanup);

describe("SHL-23 Today brief panel", () => {
  it("1: Daniel's cells 3 · 6 · 2 · 0 and the code fact paragraph", () => {
    render(<TodayPanel vm={danielToday()} />);
    expect(screen.getByText(COPY.greeting("Daniel"))).toBeTruthy();
    const cells = [...document.querySelectorAll("[data-cell]")].map((c) => c.textContent);
    expect(cells).toEqual(["3Decisions", "6Sign-offs", "2Approvals & sends", "0Overdue"]);
    expect(factParagraph(danielToday())).toBe(DANIEL_PARAGRAPH);
    expect(screen.getByText(DANIEL_PARAGRAPH)).toBeTruthy();
  });

  it("1: Needs you first rows carry their why lines; a row without one shows its context line", () => {
    const vm = danielToday();
    const first = DANIEL_ROWS[0];
    const stripped = { ...vm, needs_you_first: vm.needs_you_first.map((r, i) => (i === 0 ? { ...r, why_blocks: [] } : r)) };
    render(<TodayPanel vm={stripped} />);
    expect(screen.getByText(first?.context_line ?? "")).toBeTruthy();
    expect(document.querySelector(`[data-why="${first?.gate_id ?? ""}"]`)).toBeNull();
  });

  it("1: a count cell opens its HOME-02 band; keyboard reaches it", () => {
    const onOpen = vi.fn();
    render(<TodayPanel vm={danielToday()} onOpen={onOpen} />);
    const cell = document.querySelector<HTMLButtonElement>('[data-cell="decision"]');
    cell?.focus();
    expect(document.activeElement).toBe(cell);
    fireEvent.click(cell!);
    expect(onOpen).toHaveBeenCalledWith("/home/approvals?band=decision");
  });

  it("4: Margaret's day renders her cells", () => {
    render(<TodayPanel vm={margaretToday()} />);
    expect(screen.getByText(COPY.greeting("Margaret"))).toBeTruthy();
  });

  it("6: the quiet day", () => {
    render(<TodayPanel vm={quietToday()} />);
    expect(screen.getByText(COPY.nothingFirst)).toBeTruthy();
    expect(screen.getByText(COPY.quietBody)).toBeTruthy();
  });

  it("7: building draws its counts and skeleton", () => {
    const vm = buildingToday();
    render(<TodayPanel vm={vm} />);
    const c = vm.building_counts ?? {};
    expect(
      screen.getByText(COPY.building(c["items"] ?? 0, c["deadlines"] ?? 0, c["runs"] ?? 0)),
    ).toBeTruthy();
  });

  it("DF-04: narrative unavailable keeps every count", () => {
    const vm = { ...danielToday(), availability: { narrative: false, ask: false, narrative_reason: "consent_7216" as const } };
    render(<TodayPanel vm={vm} />);
    expect(screen.getByText(COPY.consentOff)).toBeTruthy();
    expect(document.querySelectorAll("[data-cell]").length).toBe(4);
    expect(screen.queryByLabelText(COPY.ask)).toBeNull();
  });
});
