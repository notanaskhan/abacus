// F-07-T10 (TASK-7630; F-07 §F1, §F4; T13a): "T13a passes Tier D (weekday header 30, cells at least
// 110, chips 22) and the grid is navigable with arrows, Home/End and PageUp/PageDown under
// role=grid." The data is Grace Holloway's September 2026 (synthetic; the specimen's own fixtures
// are F-07-T12's).
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CalendarLayout } from "./calendar-layout";
import { monthWeeks, weekday } from "./dates";
import { chipName } from "./due-chip";
import { CHIP_H, HEADER_H, MIN_CELL_H, MonthGrid, chipsThatFit } from "./month-grid";
import type { CalendarCopy, DeadlineChip } from "./types";

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
  more: (n) => `+${n} more`,
  deadlines: (n) => `${n} deadlines`,
  empty: "No deadlines match these filters.",
  clearFilters: "Clear filters",
  postponed: (d) => `Postponed → ${d}`,
};

const chip = (
  id: string,
  date: string,
  tier: DeadlineChip["tier"],
  extra: Partial<DeadlineChip> = {},
): DeadlineChip => ({
  id,
  date,
  label: `${id} · Form 1065`,
  client: id,
  filing: "Form 1065",
  tier,
  ...extra,
});

const SEP15 = Array.from({ length: 13 }, (_, i) => chip(`c${i}`, "2026-09-15", "due_7"));
const CHIPS = [
  ...SEP15,
  chip("Copperleaf", "2026-09-10", "overdue", {
    label: "Copperleaf · August close",
    note: "4 days past due",
  }),
  chip("Calloway", "2026-09-30", "postponed", { postponedTo: "2026-11-02" }),
  chip("Granite", "2026-09-01", "done"),
];

describe("MonthGrid", () => {
  it("is Sunday-start: September 2026 begins on Tuesday the 1st, five weeks", () => {
    const weeks = monthWeeks("2026-09");
    expect(weeks).toHaveLength(5);
    expect(weeks[0]?.[0]).toBe("2026-08-30");
    expect(weekday("2026-09-01")).toBe(2);
    expect(weeks[0]?.[2]).toBe("2026-09-01");
  });

  it("geometry: weekday header 30, cells at least 110, chips 22", () => {
    expect(HEADER_H).toBe(30);
    expect(MIN_CELL_H).toBe(110);
    expect(CHIP_H).toBe(22);
    const { container } = render(
      <MonthGrid month="2026-09" today="2026-09-14" chips={CHIPS} copy={COPY} height={300} />,
    );
    const cell = container.querySelector<HTMLElement>('[data-day="2026-09-15"]');
    expect(Number.parseInt(cell?.style.height ?? "0", 10)).toBeGreaterThanOrEqual(110);
  });

  it("fits 3 chips and +10 more at 144 h, never more than 4", () => {
    expect(chipsThatFit(144, 13)).toBe(3);
    expect(chipsThatFit(400, 13)).toBe(4);
    expect(chipsThatFit(144, 2)).toBe(2);
    const height = HEADER_H + 5 * 144;
    render(
      <MonthGrid month="2026-09" today="2026-09-14" chips={CHIPS} copy={COPY} height={height} />,
    );
    expect(screen.getByText("+10 more")).toBeTruthy();
  });

  it("circles today from the prop, labels a holiday from data, dims out-of-month days", () => {
    const { container } = render(
      <MonthGrid
        month="2026-09"
        today="2026-09-14"
        chips={[]}
        holidays={[{ date: "2026-09-07", label: "Labor Day" }]}
        copy={COPY}
      />,
    );
    expect(container.querySelector('[data-day="2026-09-14"] [data-today]')).not.toBeNull();
    expect(screen.getByText("Labor Day")).toBeTruthy();
    expect(container.querySelector('[data-day="2026-08-30"] .text-ink-4')).not.toBeNull();
  });

  it("chips state client, filing, due date and risk in words; postponed and done read so", () => {
    expect(chipName(SEP15[0] as DeadlineChip, COPY)).toBe(
      "c0, Form 1065, due Tue Sep 15, 2026, Due this week",
    );
    const postponed = CHIPS.find((c) => c.id === "Calloway") as DeadlineChip;
    expect(chipName(postponed, COPY)).toContain("Postponed → Nov 2");
    const overdue = CHIPS.find((c) => c.id === "Copperleaf") as DeadlineChip;
    expect(chipName(overdue, COPY)).toContain("Past due, 4 days past due");
  });

  it("announces each day with its count and moves by arrows, Home/End and PageUp/PageDown", () => {
    vi.useFakeTimers();
    const onMonth = vi.fn();
    const onExpandDay = vi.fn();
    const { container } = render(
      <MonthGrid
        month="2026-09"
        today="2026-09-14"
        chips={CHIPS}
        copy={COPY}
        height={HEADER_H + 5 * 144}
        onMonth={onMonth}
        onExpandDay={onExpandDay}
      />,
    );
    const grid = screen.getByRole("grid");
    const focused = () =>
      container.querySelector('[role="gridcell"][tabindex="0"]')?.getAttribute("data-day");
    expect(focused()).toBe("2026-09-14");
    expect(container.querySelector('[data-day="2026-09-15"]')?.getAttribute("aria-label")).toBe(
      "Tuesday, September 15, 2026, 13 deadlines",
    );
    const key = (k: string) => {
      fireEvent.keyDown(grid, { key: k });
      act(() => {
        vi.runAllTimers();
      });
    };
    key("ArrowRight");
    expect(focused()).toBe("2026-09-15");
    key("Enter");
    expect(onExpandDay).toHaveBeenCalledWith("2026-09-15");
    key("ArrowDown");
    expect(focused()).toBe("2026-09-22");
    key("Home");
    expect(focused()).toBe("2026-09-20");
    key("End");
    expect(focused()).toBe("2026-09-26");
    key("ArrowLeft");
    expect(focused()).toBe("2026-09-25");
    key("ArrowUp");
    expect(focused()).toBe("2026-09-18");
    key("PageDown");
    key("PageUp");
    expect(onMonth.mock.calls).toEqual([[1], [-1]]);
    vi.useRealTimers();
  });
});

describe("CalendarLayout", () => {
  it("renders the stepper title, the views and the filter chips, and emits intents", () => {
    const onView = vi.fn();
    const onFilter = vi.fn();
    render(
      <CalendarLayout
        view="month"
        month="2026-09"
        today="2026-09-14"
        chips={CHIPS}
        filters={[
          { key: "office", label: "Office" },
          { key: "service", label: "Service" },
          { key: "person", label: "Person" },
        ]}
        copy={COPY}
        onView={onView}
        onFilter={onFilter}
      />,
    );
    expect(screen.getByRole("heading", { name: "September 2026" })).toBeTruthy();
    fireEvent.click(screen.getByText("Office"));
    expect(onFilter).toHaveBeenCalledWith("office");
    fireEvent.click(screen.getByText("Week"));
    expect(onView).toHaveBeenCalledWith("week");
  });

  it("an empty filter shows the empty line with Clear filters", () => {
    const onClear = vi.fn();
    render(
      <CalendarLayout
        view="month"
        month="2026-09"
        today="2026-09-14"
        chips={[]}
        filters={[{ key: "office", label: "Office", value: "New York" }]}
        copy={COPY}
        onClearFilters={onClear}
      />,
    );
    fireEvent.click(screen.getByText("Clear filters"));
    expect(onClear).toHaveBeenCalled();
    expect(screen.getByText("No deadlines match these filters.")).toBeTruthy();
  });
});
