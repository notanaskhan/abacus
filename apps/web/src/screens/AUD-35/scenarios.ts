// AUD-35 (A-09-T22): one fixture scenario per artboard.
//   a Draft (default, Mon 14 Sep 2026, 4:30 PM): §5 needs input, Send disabled with its reason
//   b Sent (Mon 21 Sep, 2:20 PM)     c Acknowledged (Wed 23 Sep) with the Questions thread
//   d Late deliverable (Tue 1 Dec)   e Received (Wed 2 Dec)
//   f Make reference on (variant)    g Flag off (ff.group_audit)
import { DELIVERABLE_STATUSES } from "./copy";

export const AUD35_SCENARIOS = ["a", "b", "c", "d", "e", "f", "g"] as const;
export type Aud35Scenario = (typeof AUD35_SCENARIOS)[number];
type Status = (typeof DELIVERABLE_STATUSES)[number];

export interface Aud35State {
  step: 0 | 1 | 2;
  stepDates: readonly (string | null)[];
  sectionFiveDone: boolean;
  queuePill: string;
  deliverables: readonly Status[];
  statusNote: readonly (string | null)[];
  questions: boolean;
  followUp: boolean;
  makeReference: boolean;
}

const EXPECTED: readonly Status[] = ["Expected", "Expected", "Expected", "Expected"];

export const AUD35_STATE: Record<Exclude<Aud35Scenario, "g">, Aud35State> = {
  a: { step: 0, stepDates: [null, null, null], sectionFiveDone: false, queuePill: "Instructions · Draft",
       deliverables: EXPECTED, statusNote: [null, null, null, null], questions: false, followUp: false, makeReference: false },
  b: { step: 1, stepDates: [null, "Sep 21 · Omar Haddad", null], sectionFiveDone: true,
       queuePill: "Sent · awaiting acknowledgement", deliverables: EXPECTED, statusNote: [null, null, null, null],
       questions: false, followUp: false, makeReference: false },
  c: { step: 2, stepDates: [null, "Sep 21 · Omar Haddad", "Sep 23 · Renee Pruett 9:46 AM"], sectionFiveDone: true,
       queuePill: "Acknowledged", deliverables: EXPECTED, statusNote: [null, null, null, null], questions: true,
       followUp: false, makeReference: false },
  d: { step: 2, stepDates: [null, "Sep 21 · Omar Haddad", "Sep 23 · Renee Pruett 9:46 AM"], sectionFiveDone: true,
       queuePill: "1 late", deliverables: ["Reviewed", "Late", "Expected", "Expected"],
       statusNote: [null, "Late · 1 day", null, null], questions: true, followUp: true, makeReference: false },
  e: { step: 2, stepDates: [null, "Sep 21 · Omar Haddad", "Sep 23 · Renee Pruett 9:46 AM"], sectionFiveDone: true,
       queuePill: "Acknowledged", deliverables: ["Reviewed", "Received", "Expected", "Expected"],
       statusNote: [null, "Received Dec 2", null, null], questions: true, followUp: false, makeReference: false },
  f: { step: 0, stepDates: [null, null, null], sectionFiveDone: false, queuePill: "Instructions · Draft",
       deliverables: EXPECTED, statusNote: [null, null, null, null], questions: false, followUp: false, makeReference: true },
}; // prettier-ignore
