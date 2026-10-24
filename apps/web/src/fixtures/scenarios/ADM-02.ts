// ADM-02 Users & roles: one fixture scenario per artboard (G-01-T06; G-01 §5.3). a to d are Grace
// Holloway at E0 (b the Role templates segment with Partner picked, c the invite drawer with every
// seat held, d Lena Park's drawer); e is Mon Nov 2, 2026 after the access-end job (five seasonal
// rows "Deactivated Oct 31", 41 of 46); f is Mon Jan 5, 2026, 10:12 AM with Lena Park's invite
// pending (46 of 46 · 1 pending, no 47th name); g is Margaret Okonkwo on the annual independence
// segment (DF-07: no design data, so every member reads "Not yet").

import { defineScenarios } from "../../app-core/fixture-mode";
import { firmSettingsHandlers } from "../handlers/firm-settings";
import { seedScenario } from "../scenario";
import { DEMO_INSTANT } from "../seed/clock";
import { type PeopleSnapshot, seatOf, userIdOf } from "../seed/firm-people";

const E0 = seedScenario();
export const CLOCK_E = "2026-11-02T09:24:00-06:00";
export const CLOCK_F = "2026-01-05T10:12:00-06:00";
export const LENA = userIdOf(seatOf("LP"));

function at(state: string, persona: string, clock: string, snapshot: PeopleSnapshot) {
  const own = firmSettingsHandlers(persona === "grace-holloway" ? "admin" : "partner", snapshot);
  return { state, persona, clock, handlers: { ...own, ...E0.handlers, ...own } };
}

export const scenarios = defineScenarios({
  a: at("a", "grace-holloway", DEMO_INSTANT, "e0"),
  b: at("b", "grace-holloway", DEMO_INSTANT, "e0"),
  c: at("c", "grace-holloway", DEMO_INSTANT, "e0"),
  d: at("d", "grace-holloway", DEMO_INSTANT, "e0"),
  e: at("e", "grace-holloway", CLOCK_E, "after-season"),
  f: at("f", "grace-holloway", CLOCK_F, "pending-invite"),
  g: at("g", "margaret-okonkwo", DEMO_INSTANT, "e0"),
});

export type Adm02State = keyof typeof scenarios;

/** The search params each state opens with (G-01 §5.1). */
export const OPENS: Readonly<Record<Adm02State, string>> = {
  a: "",
  b: "?segment=templates&template=partner",
  c: "?ov=invite",
  d: `?ov=person:${LENA}`,
  e: "",
  f: "",
  g: "?segment=independence",
};
