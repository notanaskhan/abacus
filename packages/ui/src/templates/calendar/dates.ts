// Civil-date helpers for the month grid (F-07-T10). Pure arithmetic on firm-local ISO dates in UTC
// fields, so no browser time zone ever enters (P-50). Nothing here decides a deadline.

const MS_DAY = 86_400_000;

/** "2026-09-15" → a UTC midnight timestamp. */
export function toUtc(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1);
}

export function isoOf(utc: number): string {
  return new Date(utc).toISOString().slice(0, 10);
}

export function addDays(iso: string, n: number): string {
  return isoOf(toUtc(iso) + n * MS_DAY);
}

/** "2026-09" ± n months. */
export function addMonths(month: string, n: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1 + n, 1));
  return d.toISOString().slice(0, 7);
}

/** 0 = Sunday. */
export function weekday(iso: string): number {
  return new Date(toUtc(iso)).getUTCDay();
}

/** The Sunday-start weeks covering a month, each seven ISO dates (out-of-month days included). */
export function monthWeeks(month: string): string[][] {
  const first = `${month}-01`;
  const start = addDays(first, -weekday(first));
  const next = `${addMonths(month, 1)}-01`;
  const weeks: string[][] = [];
  for (let day = start; toUtc(day) < toUtc(next) || weeks.length === 0;) {
    const week = Array.from({ length: 7 }, (_, i) => addDays(day, i));
    weeks.push(week);
    day = addDays(day, 7);
  }
  return weeks;
}

// Names from fixed tables, not Intl (format.ts owns locale formatting; these are the civil
// calendar's English names, which the kit's copy uses verbatim).
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;
const DAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
] as const;

function parts(iso: string): { y: number; m: number; d: number; w: number } {
  const t = new Date(toUtc(iso));
  return { y: t.getUTCFullYear(), m: t.getUTCMonth(), d: t.getUTCDate(), w: t.getUTCDay() };
}

const month = (m: number): string => MONTHS[m] ?? "";
const day = (w: number): string => DAYS[w] ?? "";

/** "September 2026". */
export function monthTitle(m: string): string {
  const p = parts(`${m}-01`);
  return `${month(p.m)} ${String(p.y)}`;
}

/** "Tuesday, September 15, 2026". */
export function longDay(iso: string): string {
  const p = parts(iso);
  return `${day(p.w)}, ${month(p.m)} ${String(p.d)}, ${String(p.y)}`;
}

/** "Tue Sep 15, 2026". */
export function shortDay(iso: string): string {
  const p = parts(iso);
  return `${day(p.w).slice(0, 3)} ${month(p.m).slice(0, 3)} ${String(p.d)}, ${String(p.y)}`;
}

/** "Nov 2". */
export function monthDay(iso: string): string {
  const p = parts(iso);
  return `${month(p.m).slice(0, 3)} ${String(p.d)}`;
}

export const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;
