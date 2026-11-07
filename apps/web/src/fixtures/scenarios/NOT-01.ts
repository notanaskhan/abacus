// NOT-01 Notices index: one fixture scenario per artboard (N-04-T05; docs/screens/NOT-01.md), all
// seen by Kevin Osei (Tax Preparer) at E0, Mon Sep 14, 2026, 9:24 AM CT. Data: seed/notices.ts
// through handlers/notices.ts on the notices v1 stub's shapes. Each artboard is a data condition:
//
//   a    nine open notices by deadline risk (N4 red 7 days, N1 amber 9 days)
//   e    the New tile pressed (`?tile=new`): N5 and N9
//   f    no visible notices: "No open notices."
//   g    `GET /v1/notices` never answers: skeleton rows
//
//   b    the intake sheet over a: Aurelio Santos's CP14, read (Sep 10, 2:16 PM; N-04-T09)
//   c    the agent still reading 2 pages: Create notice disabled
//   d    "Respond by" read at 71% · date partly obscured: Create notice disabled until confirmed
//
// Dev and test only; src/screens/NOT-01/scenarios.ts re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { noticeHandlers } from "../handlers/notices";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  type IntakeVariant,
  SANTOS_ENGAGEMENT,
  SANTOS_INTAKE,
  SANTOS_NOTICE,
  santosIntake,
} from "../seed/notice-intake";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

/** Mon Sep 14, 2026, 9:24 AM CT (NOT-01 a). */
export const NOT01_INSTANT = "2026-09-14T09:24:00-05:00";
export const NOT01_PERSONA = "kevin-osei";

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? NOT01_PERSONA);
  return {
    ...base,
    capabilities: [...base.capabilities, "notice.read", "notice_intake.create"],
  };
}

function at(state: string, handlers: Record<string, FixtureHandler> = {}): Scenario {
  return {
    state,
    persona: NOT01_PERSONA,
    clock: NOT01_INSTANT,
    handlers: {
      ...E0.handlers,
      ...noticeHandlers(),
      "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
      ...handlers,
    },
  };
}

/** The intake sheet's handlers (b, c, d): the read, a confirm that marks the field confirmed,
 * and Create notice. */
function intake(variant: IntakeVariant): Record<string, FixtureHandler> {
  let current = santosIntake(variant);
  return {
    "GET /v1/notice-intakes/{intake_id}": () => json(current),
    "PUT /v1/notice-intakes/{intake_id}": () => {
      current = {
        ...current,
        version: current.version + 1,
        fields: current.fields.map((f) => (f.low_confidence ? { ...f, confirmed: true } : f)),
      };
      return json(current);
    },
    "POST /v1/notice-intakes/{intake_id}/create": () =>
      json({ notice_id: SANTOS_NOTICE, engagement_id: SANTOS_ENGAGEMENT }, 201),
    "POST /v1/notice-intakes/{intake_id}/attach": () => json(current),
    "GET /v1/firm/members": () =>
      json([{ user_id: "fixture-grace", display_name: "Grace Holloway" }]),
  };
}

export const scenarios = defineScenarios({
  a: at("a"),
  b: at("b", intake("b")),
  c: at("c", intake("c")),
  d: at("d", intake("d")),
  duplicate: at("duplicate", intake("duplicate")),
  manual: at("manual", intake("manual")),
  no_client: at("no_client", intake("no_client")),
  e: at("e"),
  f: at("f", noticeHandlers([])),
  g: at("g", { "GET /v1/notices": () => never(), "GET /v1/notices/summary": () => never() }),
});

export type Not01State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Not01State[];
/** The search each artboard opens on (journeys and the gallery). */
export const OPENS: Readonly<Record<string, string>> = { e: "?tile=new" };

/** The intake each sheet state opens on. */
export const INTAKE: Readonly<Partial<Record<Not01State, string>>> = {
  b: SANTOS_INTAKE,
  c: SANTOS_INTAKE,
  d: SANTOS_INTAKE,
  duplicate: SANTOS_INTAKE,
  manual: SANTOS_INTAKE,
  no_client: SANTOS_INTAKE,
};
