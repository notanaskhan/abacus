// The seed's one instant: Mon 14 Sep 2026, 9:24 AM CT (CDT, UTC-5), the E0 demo instant
// (SPEC-307 AC-1, AC-7). Every relative timestamp is an offset from it. The seed never reads
// the device clock; fixture mode stands the browser clock here through the scenario.

export const DEMO_INSTANT = "2026-09-14T09:24:00-05:00";
export const DEMO_MS = Date.parse(DEMO_INSTANT);

const DAY_MS = 86_400_000;

/** The UTC instant `days` before the demo instant, at the given UTC hour. */
export function daysBefore(days: number, hourUtc = 15): string {
  const base = new Date(DEMO_MS - days * DAY_MS);
  base.setUTCHours(hourUtc, 0, 0, 0);
  return base.toISOString();
}

/** A calendar date (`2026-02-03`) at a fixed UTC hour, as an ISO timestamp. */
export function onDate(date: string, hourUtc = 15): string {
  return `${date}T${String(hourUtc).padStart(2, "0")}:00:00.000Z`;
}
