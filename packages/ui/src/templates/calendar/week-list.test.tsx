// F-07-T11 (TASK-7631; F-07 §F2, §F3; T13b–d): "T13b to T13d render, the rule popover opens after
// 250 ms hover and on keyboard focus, and every chip states its risk in words to assistive
// technology."
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { type JSX } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HOVER_INTENT_MS, RulePopover, useRulePopover } from "./rule-popover";
import type { CalendarCopy, CalendarListCopy, DeadlineChip } from "./types";
import { ListView, WEEK_ROW_H, WeekView, riskWords } from "./week-list";

afterEach(cleanup);

const COPY: CalendarCopy = {
  today: "Today",
  views: "Calendar view",
  month: "Month",
  week: "Week",
  list: "List",
  export: "Export",
  previous: "Previous month",
  next: "Next month",
  more: (n) => `+${String(n)} more`,
  deadlines: (n) => `${String(n)} deadlines`,
  empty: "No deadlines match these filters.",
  clearFilters: "Clear filters",
  postponed: (d) => `Postponed → ${d}`,
};
const LIST: CalendarListCopy = {
  title: "Deadlines",
  noun: "deadlines",
  due: "Due",
  client: "Client",
  filing: "Filing",
  rule: "Rule",
  stage: "Stage",
  team: "Team",
  risk: "Risk",
  blockers: "Blockers",
  openReturn: "Open return →",
};

const RIDGELINE: DeadlineChip = {
  id: "ridgeline",
  date: "2026-09-15",
  label: "Ridgeline · Form 1065",
  client: "Ridgeline Property Partners, LP",
  filing: "Form 1065",
  tier: "due_7",
  title: "2025 Form 1065 · Ridgeline Property Partners, LP",
  rule: "15th day of the 3rd month (Mar 15, 2026 was a Sunday, so Mon Mar 16) + 6-month extension to Sep 15 via Form 7004, filed Mar 12",
  stage: "In review · Partner",
  initials: "OB",
  team: "OB / SI · signer DR",
  blockers: "11 open issues",
};
const CALLOWAY: DeadlineChip = {
  id: "calloway",
  date: "2026-09-30",
  label: "Calloway Trust · Form 1041",
  client: "Calloway Family Trust",
  filing: "Form 1041",
  tier: "postponed",
  postponedTo: "2026-11-02",
};

describe("WeekView (T13c)", () => {
  it("lists every item that week as a 40 h row with its stage and initials", () => {
    const { container } = render(
      <WeekView start="2026-09-13" today="2026-09-14" chips={[RIDGELINE, CALLOWAY]} copy={COPY} />,
    );
    expect(WEEK_ROW_H).toBe(40);
    expect(container.querySelector('[data-week="2026-09-13"]')).not.toBeNull();
    expect(container.querySelectorAll("[data-week-row]")).toHaveLength(1);
    expect(screen.getByText("In review · Partner")).toBeTruthy();
    expect(screen.getByText("OB")).toBeTruthy();
    expect(container.textContent).not.toMatch(/more/u);
  });
});

describe("ListView (T13d)", () => {
  it("renders the seven columns with the Rule and the risk in words", () => {
    render(<ListView chips={[RIDGELINE, CALLOWAY]} copy={COPY} listCopy={LIST} />);
    for (const h of ["Due", "Client", "Filing", "Rule", "Stage", "Team", "Risk"]) {
      expect(screen.getAllByText(h).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("Due this week")).toBeTruthy();
    expect(screen.getByText("Postponed → Nov 2")).toBeTruthy();
    expect(riskWords(RIDGELINE, COPY)).toBe("Due this week");
  });

  it("an empty filter is filtered-empty with Clear filters", () => {
    const onClear = vi.fn();
    render(<ListView chips={[]} filtered copy={COPY} listCopy={LIST} onClearFilters={onClear} />);
    expect(screen.getByText(COPY.empty)).toBeTruthy();
  });
});

function Harness(): JSX.Element {
  const p = useRulePopover();
  return (
    <div>
      <button
        type="button"
        onMouseEnter={(e) => {
          p.hover(RIDGELINE, e.currentTarget);
        }}
        onFocus={(e) => {
          p.focus(RIDGELINE, e.currentTarget);
        }}
        onMouseLeave={p.leave}
      >
        chip
      </button>
      {p.open === null ? null : <RulePopover chip={p.open.chip} copy={COPY} listCopy={LIST} />}
    </div>
  );
}

describe("RulePopover (T13a, F2)", () => {
  it("opens after 250 ms of hover, not before, and closes on leave", () => {
    vi.useFakeTimers();
    render(<Harness />);
    fireEvent.mouseEnter(screen.getByText("chip"));
    act(() => {
      vi.advanceTimersByTime(HOVER_INTENT_MS - 1);
    });
    expect(screen.queryByRole("tooltip")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.getByRole("tooltip").textContent).toContain("Tue Sep 15, 2026");
    fireEvent.mouseLeave(screen.getByText("chip"));
    expect(screen.queryByRole("tooltip")).toBeNull();
    vi.useRealTimers();
  });

  it("opens at once on keyboard focus, with Rule, Due, Stage, Team, Blockers and Open return", () => {
    render(<Harness />);
    fireEvent.focus(screen.getByText("chip"));
    const tip = screen.getByRole("tooltip");
    expect(tip.textContent).toContain("2025 Form 1065 · Ridgeline Property Partners, LP");
    expect(tip.textContent).toContain("15th day of the 3rd month");
    expect(tip.textContent).toContain("In review · Partner");
    expect(tip.textContent).toContain("OB / SI · signer DR");
    expect(tip.textContent).toContain("11 open issues");
    expect(tip.textContent).toContain("Open return →");
  });

  it("a postponed chip strikes its original date and names the new one", () => {
    render(<RulePopover chip={CALLOWAY} copy={COPY} listCopy={LIST} />);
    expect(screen.getByRole("tooltip").querySelector("s")?.textContent).toBe("Wed Sep 30, 2026");
    expect(screen.getByRole("tooltip").textContent).toContain("Postponed → Mon Nov 2, 2026");
  });
});
