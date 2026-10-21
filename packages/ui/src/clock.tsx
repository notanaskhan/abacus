import {
  type JSX,
  type ReactNode,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  DEFAULT_TZ,
  type DateOptions,
  type Instant,
  date,
  dateTime,
  isoDate,
  period,
  relative,
  since,
  time,
} from "./format";

// The app's business clock as the design system sees it (F-05-T10; ADR-143). packages/ui cannot
// import from apps/web, so the app hands `ClockProvider` its now-source (apps/web wires
// `nowMs` from app-core/clock.tsx at the root) and the firm's time zone. Screens read time only
// through `useNow`, `useToday` and `useFormat`, never `Date.now()`.

/** Business time now, in epoch milliseconds, or as a Date. */
export type NowSource = () => number | Date;

interface ClockValue {
  now: NowSource;
  tz: string;
}

// With no provider (a test, a specimen) the device clock stands in, in the default zone.
const ClockContext = createContext<ClockValue>({ now: () => Date.now(), tz: DEFAULT_TZ });

export interface ClockProviderProps {
  /** Where business time comes from: the fixture scenario, `?clock=`, the server, the device. */
  now: NowSource;
  /** The firm's IANA time zone. Default America/Chicago. */
  tz?: string;
  children: ReactNode;
}

export function ClockProvider({
  now,
  tz = DEFAULT_TZ,
  children,
}: ClockProviderProps): JSX.Element {
  const value = useMemo(() => ({ now, tz }), [now, tz]);
  return <ClockContext.Provider value={value}>{children}</ClockContext.Provider>;
}

function read(source: NowSource): Date {
  return new Date(source());
}

/** Business time, re-read every `tickMs` (a minute by default) so relative words stay true. */
export function useNow(tickMs = 60_000): Date {
  const { now: source } = useContext(ClockContext);
  const [now, setNow] = useState(() => read(source));
  useEffect(() => {
    setNow(read(source));
    const id = window.setInterval(() => {
      setNow(read(source));
    }, tickMs);
    return () => {
      window.clearInterval(id);
    };
  }, [source, tickMs]);
  return now;
}

/** The firm's time zone. */
export function useTimeZone(): string {
  return useContext(ClockContext).tz;
}

/** Today's business date, YYYY-MM-DD in the firm's zone. */
export function useToday(): string {
  const now = useNow();
  return isoDate(now, useTimeZone());
}

export interface BoundFormat {
  date: (v: Instant, options?: Pick<DateOptions, "withYear">) => string;
  dateTime: (v: Instant, options?: { zone?: boolean; seconds?: boolean }) => string;
  time: (v: Instant, options?: { zone?: boolean; seconds?: boolean }) => string;
  relative: (v: Instant) => string;
  since: (v: Instant) => string;
  period: (start: Instant, end: Instant) => string;
}

/** The date formatters with the business time and the firm's zone already filled in, for
 * building strings in components: `const f = useFormat(); f.date(row.created_at)`. */
export function useFormat(): BoundFormat {
  const now = useNow();
  const tz = useTimeZone();
  return useMemo(
    () => ({
      date: (v, o) => date(v, { now, tz, ...o }),
      dateTime: (v, o) => dateTime(v, { tz, ...o }),
      time: (v, o) => time(v, { tz, ...o }),
      relative: (v) => relative(v, { now, tz }),
      since: (v) => since(v, { now, tz }),
      period: (a, b) => period(a, b, { tz }),
    }),
    [now, tz],
  );
}
