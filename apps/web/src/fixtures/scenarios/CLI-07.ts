// CLI-07 Acceptance & continuance: one fixture scenario per artboard (P-07-T46;
// docs/screens/CLI-07.md). Data: the acceptance seed (seed/acceptance.ts) through
// handlers/acceptance.ts, which answer exactly as the live routes do (P-07-T35):
//
//   a  Daniel Reyes, Mon Sep 14, 9:40 AM CT: Thornbury Awaiting partner, three flags, Moderate
//   b  Samuel Ito, Fri Sep 11, 4:10 PM: Draft, Grace Holloway's fee check open
//   c  Daniel Reyes, Fri Sep 11, 4:01 PM: Pre-screening, 4 of 9 sections (fixture only, DEC-64)
//   d  Daniel Reyes, Mon Sep 14, 9:46 AM: accepted with conditions, three open conditions
//   e  Daniel Reyes, Mon Sep 14, 9:40 AM: declined with reasons
//   f  Margaret Okonkwo, Mon Sep 14, 10:05 AM: Meridian's FY2026 continuance
//   g  Margaret Okonkwo, Thu Oct 1, 10:40 AM: Granite Peak's FY2027 continuance in Draft with the
//      responsiveness flag (fixture until I-03 registers INS-05)
//
// They live under fixtures/ (dev and test only); screens/CLI-07/scenarios.ts re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { type AcceptanceFixture, acceptanceHandlers } from "../handlers/acceptance";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  GRANITE_NOTE,
  type ThornburyStage,
  graniteEngagement,
  graniteRecord,
  meridianEngagement,
  meridianRecord,
  thornburyEngagement,
  thornburyRecord,
} from "../seed/acceptance";
import { capabilitiesFor } from "../seed/shell";
import { PARTNER_POOL, candidatesOf } from "../seed/team-roles";

const E0 = seedScenario();
const seed = getSeed();

const CLOCK = {
  a: "2026-09-14T09:40:00-05:00",
  b: "2026-09-11T16:10:00-05:00",
  c: "2026-09-11T16:01:00-05:00",
  d: "2026-09-14T09:46:00-05:00",
  e: "2026-09-14T09:40:00-05:00",
  f: "2026-09-14T10:05:00-05:00",
  g: "2026-10-01T10:40:00-05:00",
} as const;

export type Cli07State = keyof typeof CLOCK;

function capabilities(persona: string | undefined): CapabilitiesOut {
  return capabilitiesFor(seed, persona ?? "daniel-reyes");
}

function thornbury(stage: ThornburyStage): AcceptanceFixture {
  const status =
    stage === "accepted" ? "accepted" : stage === "declined" ? "declined" : "prospect";
  return {
    engagement: thornburyEngagement(status),
    record: thornburyRecord(stage),
    candidates: candidatesOf(PARTNER_POOL),
  };
}

const CONTINUANCE_PARTNERS = ["Daniel Reyes", "Thomas Whitcombe", "Celia Marsh"] as const;

const FIXTURES: Record<Cli07State, () => AcceptanceFixture> = {
  a: () => thornbury("awaiting"),
  b: () => thornbury("draft"),
  c: () => thornbury("screening"),
  d: () => thornbury("accepted"),
  e: () => thornbury("declined"),
  f: () => ({
    engagement: meridianEngagement(),
    record: meridianRecord(),
    candidates: candidatesOf(CONTINUANCE_PARTNERS),
  }),
  g: () => ({
    engagement: graniteEngagement(),
    record: graniteRecord(),
    candidates: candidatesOf(CONTINUANCE_PARTNERS),
  }),
};

const PERSONA: Record<Cli07State, string> = {
  a: "daniel-reyes",
  b: "samuel-ito",
  c: "daniel-reyes",
  d: "daniel-reyes",
  e: "daniel-reyes",
  f: "margaret-okonkwo",
  g: "margaret-okonkwo",
};

export interface Cli07Options {
  persona?: string;
  /** The decision answers 403 `mfa_required`. */
  staleMfa?: boolean;
}

function build(state: Cli07State, options: Cli07Options = {}): Scenario {
  const clock = CLOCK[state];
  const handlers: Record<string, FixtureHandler> = {
    ...E0.handlers,
    ...acceptanceHandlers([FIXTURES[state]()], {
      now: new Date(clock).toISOString(),
      ...(options.staleMfa === true ? { staleMfa: true } : {}),
    }),
    "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
  };
  return { state, persona: options.persona ?? PERSONA[state], clock, handlers };
}

export const scenarios = defineScenarios({
  a: build("a"),
  b: build("b"),
  c: build("c"),
  d: build("d"),
  e: build("e"),
  f: build("f"),
  g: build("g"),
});

/** A scenario with fresh handler state (tests that write), seen as another persona if asked. */
export function freshScenario(state: Cli07State, options: Cli07Options = {}): Scenario {
  return build(state, options);
}

/** The engagement and client each artboard opens. */
export const OPENS: Readonly<Record<Cli07State, { clientId: string; engagementId: string }>> =
  Object.fromEntries(
    (Object.keys(FIXTURES) as Cli07State[]).map((s) => {
      const e = FIXTURES[s]().engagement.record;
      return [s, { clientId: e.client_id, engagementId: e.id }];
    }),
  ) as Record<Cli07State, { clientId: string; engagementId: string }>;

/** g's dock note, typed by Margaret before the questionnaire is done (the gallery passes it; the
 * route never does: a note in progress is the viewer's own, not served). */
export const NOTES: Readonly<Partial<Record<Cli07State, string>>> = { g: GRANITE_NOTE };
