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

const FMT = (options: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat("en-US", { timeZone: "UTC", ...options });

/** "September 2026". */
export function monthTitle(month: string): string {
  return FMT({ month: "long", year: "numeric" }).format(toUtc(`${month}-01`));
}

/** "Tuesday, September 15, 2026". */
export function longDay(iso: string): string {
  return FMT({ weekday: "long", month: "long", day: "numeric", year: "numeric" }).format(
    toUtc(iso),
  );
}

/** "Tue Sep 15, 2026". */
export function shortDay(iso: string): string {
  const d = toUtc(iso);
  return `${FMT({ weekday: "short" }).format(d)} ${FMT({ month: "short", day: "numeric" }).format(d)}, ${FMT({ year: "numeric" }).format(d)}`;
}

/** "Nov 2". */
export function monthDay(iso: string): string {
  return FMT({ month: "short", day: "numeric" }).format(toUtc(iso));
}

export const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;
