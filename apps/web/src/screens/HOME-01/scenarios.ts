// HOME-01 (I-01-T05): one scenario per artboard and state; the data and handlers live under
// fixtures/scenarios/HOME-01.ts. office-denver opens with the Office chip on Denver.
import { scenarios } from "../../fixtures/scenarios/HOME-01";
import { officeIdOf } from "../../fixtures/seed/shell";

export { scenarios };

export type Home01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Home01State[];

/** The office each state opens on (null: all offices). */
export const OFFICE: Readonly<Partial<Record<Home01State, string>>> = {
  "office-denver": officeIdOf("Denver"),
};
