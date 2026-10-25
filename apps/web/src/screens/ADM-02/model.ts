// ADM-02's search params and the words it builds from data (G-01 §5.1). The URL carries the
// segment, the filters, the highlighted template column and the open overlay; never a name, an
// email or a TIN (an overlay names a person by id).

import { date, sameDay, time, weekdayDate } from "@abacus/ui";
import { COPY } from "./copy";

export const SEGMENTS = ["users", "templates", "invitations", "independence"] as const;
export type Segment = (typeof SEGMENTS)[number];

export interface Adm02Search {
  segment?: Segment;
  /** A role template key. */
  role?: string;
  /** An office id. */
  office?: string;
  /** A team id. */
  team?: string;
  /** active · invited · deactivated; absent is every status. */
  status?: string;
  q?: string;
  /** The template whose grid column is highlighted. */
  template?: string;
  /** `invite` or `person:<userId>`. */
  ov?: string;
}

/** A change to the search: a key set to undefined is cleared. */
export type Adm02Patch = { [K in keyof Adm02Search]?: Adm02Search[K] | undefined };

const KEYS = ["role", "office", "team", "status", "q", "template", "ov"] as const;

/** The search a route or a `?…` string carries, keeping only what ADM-02 knows. */
export function parseSearch(raw: Readonly<Record<string, unknown>> | string): Adm02Search {
  const source: Readonly<Record<string, unknown>> =
    typeof raw === "string" ? Object.fromEntries(new URLSearchParams(raw)) : raw;
  const out: Adm02Search = {};
  const segment = source.segment;
  if (typeof segment === "string" && (SEGMENTS as readonly string[]).includes(segment)) {
    out.segment = segment as Segment;
  }
  for (const key of KEYS) {
    const value = source[key];
    if (typeof value === "string" && value !== "") out[key] = value;
  }
  return out;
}

/** "MO" for Margaret Okonkwo: the first letters of the first and last names. */
export function initialsOf(name: string): string {
  const words = name.trim().split(/\s+/);
  const first = words[0]?.[0] ?? "";
  const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? "") : "";
  return `${first}${last}`.toUpperCase();
}

interface When {
  now: Date;
  tz: string;
}

/** "Fri Sep 11": a short weekday and the date (the year only when it isn't this year). */
function dayText(at: string, { now, tz }: When): string {
  return `${weekdayDate(at, { now, tz }).slice(0, 3)} ${date(at, { now, tz })}`;
}

/** Last active: "Today 9:10 AM" or "Fri Sep 11". */
export function lastActiveText(at: string | null | undefined, when: When): string {
  if (at === null || at === undefined) return COPY.none;
  if (sameDay(at, when.now.toISOString(), { tz: when.tz })) {
    return COPY.today(time(at, { tz: when.tz }));
  }
  return dayText(at, when);
}

/** A sign-in: "Today 8:18 AM" or "Fri Sep 11, 4:40 PM". */
export function signInText(at: string, when: When): string {
  if (sameDay(at, when.now.toISOString(), { tz: when.tz })) {
    return COPY.today(time(at, { tz: when.tz }));
  }
  return `${dayText(at, when)}, ${time(at, { tz: when.tz })}`;
}

/** When a wall was added: "today 9:20 AM" or "Feb 3, 2026". */
export function addedText(at: string, when: When): string {
  if (sameDay(at, when.now.toISOString(), { tz: when.tz })) {
    return `today ${time(at, { tz: when.tz })}`;
  }
  return date(at, { now: when.now, tz: when.tz, withYear: true });
}

/** A calendar date in a sentence or pill: "Jan 19", "Oct 31" (with the year when not this one). */
export function dayOf(on: string, when: When): string {
  return date(on, { now: when.now, tz: when.tz });
}

/** A calendar date with its year: "Oct 31, 2026". */
export function fullDayOf(on: string, when: When): string {
  return date(on, { now: when.now, tz: when.tz, withYear: true });
}
