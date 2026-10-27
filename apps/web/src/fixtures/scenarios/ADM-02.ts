// ADM-02 Users & roles: one fixture scenario per artboard (G-01-T06; G-01 §5.3). a to d are Grace
// Holloway at E0 (b the Role templates segment with Partner picked, c the invite drawer with every
// seat held, d Lena Park's drawer); e is Mon Nov 2, 2026 after the access-end job (five seasonal
// rows "Deactivated Oct 31", 41 of 46); f is Mon Jan 5, 2026, 10:12 AM with Lena Park's invite
// pending (46 of 46 · 1 pending, no 47th name); g is Margaret Okonkwo on the annual independence
// segment (DF-07: no design data, so every member reads "Not yet").

import type { CapabilitiesOut } from "@abacus/api-client";
import { type FixtureRequest, defineScenarios, json } from "../../app-core/fixture-mode";
import { firmSettingsHandlers } from "../handlers/firm-settings";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { type PeopleSnapshot, seatOf, userIdOf } from "../seed/firm-people";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

/** The matrix's answers for the two viewers (identity.yaml): Grace Holloway is the firm admin;
 * Margaret Okonkwo is a partner (`firm.read_people`, `independence.annual_read`, the wall
 * register), who can't read the people list while it stays on `firm.manage_users` (DEC-286). */
const ACTIONS: Readonly<Record<string, readonly string[]>> = {
  "grace-holloway": [
    "firm.read_settings",
    "firm.manage_settings",
    "firm.read_people",
    "firm.manage_users",
    "security_role.assign",
    "independence.annual_read",
    "wall.list",
    "wall.create",
  ],
  "margaret-okonkwo": [
    "firm.read_settings",
    "firm.read_people",
    "independence.annual_read",
    "wall.list",
    "wall.create",
  ],
};

function capabilities(persona: string | undefined): CapabilitiesOut {
  const slug = persona ?? "grace-holloway";
  const base = capabilitiesFor(seed, slug);
  return {
    ...base,
    capabilities: [...base.capabilities, ...(ACTIONS[slug] ?? [])],
  };
}
export const CLOCK_E = "2026-11-02T09:24:00-06:00";
export const CLOCK_F = "2026-01-05T10:12:00-06:00";
export const LENA = userIdOf(seatOf("LP"));

function at(state: string, persona: string, clock: string, snapshot: PeopleSnapshot) {
  const own = firmSettingsHandlers(persona === "grace-holloway" ? "admin" : "partner", snapshot);
  return {
    state,
    persona,
    clock,
    handlers: {
      ...own,
      ...E0.handlers,
      ...own,
      "GET /v1/me/capabilities": ({ persona: who }: FixtureRequest) => json(capabilities(who)),
    },
  };
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
