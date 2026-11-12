// T13 CalendarLayout props (F-07-T10; SPEC-652 AC-6; F-07 §F1–F4). Generic shapes, no
// @abacus/api-client types. Dates are firm-local ISO dates ("2026-09-15") the server sends; the kit
// lays them out and never derives "today" from the browser, nor a due date or a risk tier
// (ADR-050, P-50). Rule text is C21 data (DEC-76), never composed here.
import type { RegistryCode } from "../../status";

export type CalendarView = "month" | "week" | "list";
export type DeadlineTier = RegistryCode<"filing_deadline">;

export interface DeadlineChip {
  id: string;
  /** The due date, firm-local ("2026-09-15"). */
  date: string;
  /** "Ridgeline · Form 1065": the chip's words. */
  label: string;
  /** The client's full name and the filing, for assistive technology and the popover title. */
  client: string;
  filing: string;
  /** The server's tier (`filing_deadline`). */
  tier: DeadlineTier;
  /** "4 days past due" after an overdue chip's label (the server's words). */
  note?: string;
  /** A postponed item's new date ("2026-11-02"): the original is struck and a muted pill reads
   * "Postponed → Nov 2". */
  postponedTo?: string;
  /** The C21 rule text the popover shows ("15th day of the 3rd month … + 6-month extension"). */
  rule?: string;
  /** F-07-T11: the work's stage as the server words it ("In review · Partner"). */
  stage?: string;
  /** Owner initials for the week row ("OB"). */
  initials?: string;
  /** The popover's team line ("OB / SI · signer DR"). */
  team?: string;
  /** The popover's blockers line ("11 open issues"). */
  blockers?: string;
  /** The popover's title ("2025 Form 1065 · Ridgeline Property Partners, LP"); `label` if absent. */
  title?: string;
}

export interface CalendarHoliday {
  date: string;
  /** "Labor Day" (data, not computed). */
  label: string;
}

/** The day popover's server-composed header ("Sep 15 · 13 items: 11 extended returns …"). */
export interface ExpandedDay {
  date: string;
  header: string;
}

export interface CalendarFilter {
  key: "office" | "service" | "person";
  label: string;
  /** The chosen value's words ("Denver"); omitted when no value is chosen. */
  value?: string;
}

export interface CalendarCopy {
  today: string;
  views: string;
  month: string;
  week: string;
  list: string;
  export: string;
  previous: string;
  next: string;
  /** "+{n} more". */
  more: (n: number) => string;
  /** "{n} deadlines" for a day cell's accessible name. */
  deadlines: (n: number) => string;
  empty: string;
  clearFilters: string;
  /** "Postponed → {date}". */
  postponed: (date: string) => string;
}

/** F-07-T11: the list view's and the rule popover's words. */
export interface CalendarListCopy {
  title: string;
  noun: string;
  due: string;
  client: string;
  filing: string;
  rule: string;
  stage: string;
  team: string;
  risk: string;
  blockers: string;
  openReturn: string;
}
