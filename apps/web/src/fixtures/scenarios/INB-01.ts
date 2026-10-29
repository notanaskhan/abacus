// INB-01 Inbox: one fixture scenario per artboard (N-01-T10; docs/screens/INB-01.md), at E0, seen
// by Grace Holloway. src/screens/INB-01/scenarios.ts re-exports them.
export { INB01_SCENARIOS as scenarios } from "../handlers/inbox";

import { stableId } from "../seed/prng";

const thread = (id: string): string => stableId(`inbox-thread:${id}`);

/** The thread each artboard opens: a Feld, b Sound Electric (row 9, unmatched), c Harold Stein
 * (row 3), d Feld after triage; e, f and g open none. */
export const OPENS: Readonly<Record<string, string | null>> = {
  a: thread("feld"),
  b: thread("sound"),
  c: thread("stein"),
  d: thread("feld"),
  e: null,
  f: null,
  g: null,
};
