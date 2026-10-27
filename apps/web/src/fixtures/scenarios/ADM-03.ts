// ADM-03 Offices, teams, walls & offshore: one fixture scenario per artboard (G-01-T14; G-01 §5.3;
// docs/screens/ADM-03.md). a, c, g and h are Grace Holloway at E0, 9:24 AM; b and f are 9:20 AM,
// when she adds the Lena Park ✕ Ashford wall (f: the new row tinted for 2 s); d puts Remy Vidal
// in the offshore group; e is Daniel Reyes (partner): offices, teams and offshore locked, his wall
// actions, and the service lines a partner manages (ADR-183 condition 4); g opens
// Lena Park's wall log after Margaret Okonkwo approved it; h narrows Tax to "Engagement team
// only" (the change is the test's: a dirty form is not a URL).

import type { CapabilitiesOut } from "@abacus/api-client";
import { type FixtureRequest, defineScenarios, json } from "../../app-core/fixture-mode";
import { type Adm03Options, adm03Handlers, firmSettingsHandlers } from "../handlers/firm-settings";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import {
  ASHFORD_CLIENT,
  ASHFORD_PARTNER,
  ASHFORD_WALL,
  seatOf,
  userIdOf,
} from "../seed/firm-people";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

/** The matrix's answers for the two viewers (identity.yaml, organisations.yaml). */
const ACTIONS: Readonly<Record<string, readonly string[]>> = {
  "grace-holloway": [
    "firm.read_settings",
    "firm.manage_settings",
    "firm.read_people",
    "firm.manage_users",
    "org_structure.read",
    "org_structure.manage",
    "service_line_policy.manage",
    "wall.list",
    "wall.create",
  ],
  "daniel-reyes": [
    "firm.read_settings",
    "firm.read_people",
    "org_structure.read",
    "service_line_policy.manage", // ADR-183 condition 4: partners manage service lines
    "wall.list",
    "wall.create",
    "wall.approve",
    "wall.remove",
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

export const CLOCK_920 = "2026-09-14T09:20:00-05:00";
export const LENA = userIdOf(seatOf("LP"));
export const NEIL = userIdOf(seatOf(ASHFORD_PARTNER));
export { ASHFORD_CLIENT, ASHFORD_WALL };

function at(
  state: string,
  persona: "grace-holloway" | "daniel-reyes",
  clock: string,
  more: Partial<Adm03Options> = {},
) {
  const grace = persona === "grace-holloway";
  const own = {
    ...firmSettingsHandlers(grace ? "admin" : "partner", "e0"),
    ...adm03Handlers({ viewer: grace ? "GH" : "DR", manage: grace, manageLines: true, ...more }),
  };
  return {
    state,
    persona,
    clock,
    handlers: {
      ...E0.handlers,
      ...own,
      "GET /v1/me/capabilities": ({ persona: who }: FixtureRequest) => json(capabilities(who)),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "grace-holloway", DEMO_INSTANT),
  b: at("b", "grace-holloway", CLOCK_920, { beforeLenaWall: true }),
  c: at("c", "grace-holloway", DEMO_INSTANT),
  d: at("d", "grace-holloway", DEMO_INSTANT, { offshoreRemy: true }),
  e: at("e", "daniel-reyes", DEMO_INSTANT),
  f: at("f", "grace-holloway", CLOCK_920),
  g: at("g", "grace-holloway", DEMO_INSTANT, { wallState: "approved" }),
  h: at("h", "grace-holloway", DEMO_INSTANT),
});

export type Adm03State = keyof typeof scenarios;

/** The search (and anchor) each state opens with (G-01 §5.1). The new-wall sheet may carry the
 * person and client it opens on, as ids (b, c). */
export const OPENS: Readonly<Record<Adm03State, string>> = {
  a: "?expand=CHI",
  b: `?expand=CHI&ov=wall:new:${LENA}:${ASHFORD_CLIENT}`,
  c: `?expand=CHI&ov=wall:new:${NEIL}:${ASHFORD_CLIENT}`,
  d: "?expand=CHI#offshore",
  e: "?expand=CHI",
  f: "?expand=CHI#walls",
  g: `?expand=CHI&ov=wall:${ASHFORD_WALL}`,
  h: "?expand=CHI",
};
