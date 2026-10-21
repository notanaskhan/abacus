import { useEffect, useState } from "react";

// The browser's business clock (F-04-T03; ADR-143; F-04.7). `useNow()` resolves in this order:
// 1. the fixture scenario's clock (`setScenarioClock`, fixture mode);
// 2. `?clock=` in dev, fixture and preview builds (never production);
// 3. the server's time from `/v1/me` as an offset (`setServerNow`), so a demo tenant reads its
//    demo instant;
// 4. the device's time.
// F-05-T10's ClockProvider wraps this; screens read time only through these hooks.

let scenarioClock: number | null = null;
let serverOffsetMs = 0;

const QUERY_CLOCK_ALLOWED =
  import.meta.env.DEV ||
  import.meta.env.VITE_UI_GALLERY === "1" ||
  import.meta.env.VITE_FIXTURES === "1";

/** Fixture mode: the scenario's instant (ISO 8601 with an offset), or null to clear it. */
export function setScenarioClock(iso: string | null): void {
  scenarioClock = iso === null ? null : Date.parse(iso);
}

/** The server's `server_now`: business time runs at the server's offset from the device. */
export function setServerNow(iso: string): void {
  const server = Date.parse(iso);
  if (!Number.isNaN(server)) serverOffsetMs = server - Date.now();
}

function queryClock(): number | null {
  if (!QUERY_CLOCK_ALLOWED || typeof window === "undefined") return null;
  const raw = new URLSearchParams(window.location.search).get("clock");
  if (raw === null) return null;
  const parsed = Date.parse(raw);
  return Number.isNaN(parsed) ? null : parsed;
}

/** Business time now, in epoch milliseconds (see the order above). */
export function nowMs(): number {
  return scenarioClock ?? queryClock() ?? Date.now() + serverOffsetMs;
}

/** The nth Sunday of a month (UTC date), for the US daylight-saving rule. */
function nthSunday(year: number, month: number, n: number): number {
  const first = new Date(Date.UTC(year, month, 1)).getUTCDay();
  return 1 + ((7 - first) % 7) + 7 * (n - 1);
}

/** Central time's offset from UTC in hours at an instant: -5 (CDT) from the second Sunday of
 * March, 2 AM, to the first Sunday of November, 2 AM; else -6 (CST). Formatting proper is
 * format.ts's (F-05-T10); this only finds the business date. */
function centralOffset(at: number): number {
  const year = new Date(at).getUTCFullYear();
  const start = Date.UTC(year, 2, nthSunday(year, 2, 2), 8); // 2 AM CST = 08:00 UTC
  const end = Date.UTC(year, 10, nthSunday(year, 10, 1), 7); // 2 AM CDT = 07:00 UTC
  return at >= start && at < end ? -5 : -6;
}

/** The business date in the firm's zone (Central), as YYYY-MM-DD. */
export function todayIso(at: number = nowMs()): string {
  return new Date(at + centralOffset(at) * 3_600_000).toISOString().slice(0, 10);
}

/** Business time, re-read every `tickMs` (a minute by default) so relative words stay true. */
export function useNow(tickMs = 60_000): Date {
  const [now, setNow] = useState(() => new Date(nowMs()));
  useEffect(() => {
    const id = window.setInterval(() => {
      setNow(new Date(nowMs()));
    }, tickMs);
    return () => {
      window.clearInterval(id);
    };
  }, [tickMs]);
  return now;
}

/** Today's business date (YYYY-MM-DD, Central). */
export function useToday(): string {
  return todayIso(useNow().getTime());
}
