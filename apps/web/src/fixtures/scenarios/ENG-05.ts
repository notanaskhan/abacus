// ENG-05 Team & roles: one fixture scenario per artboard (P-07-T39; docs/screens/ENG-05.md),
// inside the ENG-02 record on its Team tab, with `engagements.v2` on. Data: the team-roles seed
// (seed/team-roles.ts) through handlers/team-roles.ts, over ENG-02's record handlers:
//
//   a  Hannah Leclerc, Mon Sep 14, 9:24 AM CT: Northwind, five confirmed and Kira Ross pending
//   b  Hannah Leclerc, Fri Sep 11, 9:24 AM CT: Northwind before Kira was proposed; "+ Add person"
//      → Kira Ross opens "Assignment pending independence"
//   c  Laura Kemp (the canvas's viewer; DEC-386), Sep 14: Fairhaven's "Replace EQR…" with Thomas
//      Whitcombe picked, not eligible (cooling-off, PY2024)
//   d  Hannah Leclerc, Sep 14: a after Kira confirmed; the banner is gone
//   e  Hannah Leclerc, Sep 14: Granite Peak's new plan audit, no team
//
// They live under fixtures/ (dev and test only); screens/ENG-05/scenarios.ts re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { engagementRecordHandlers } from "../handlers/engagement-record";
import { type TeamFixture, type TeamSeen, teamRoleHandlers } from "../handlers/team-roles";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";
import {
  ADD_POOL,
  FAIRHAVEN_EQR,
  FAIRHAVEN_TEAM,
  NORTHWIND_EQR,
  NORTHWIND_TEAM,
  PARTNER_POOL,
  candidatesOf,
  emptyApproval,
  fairhavenApproval,
  fairhavenRecord,
  granitePlanRecord,
  northwindApproval,
  northwindRecord,
  rosterOf,
  userIdOf,
} from "../seed/team-roles";

const E0 = seedScenario();
const seed = getSeed();

/** b's clock: Fri Sep 11, 2026, 9:24 AM CT. */
const SEP_11 = "2026-09-11T09:24:00-05:00";

export const KIRA = userIdOf("Kira Ross");
export const THOMAS = userIdOf("Thomas Whitcombe");

const NORTHWIND = northwindRecord(seed);
const FAIRHAVEN = fairhavenRecord(seed);
const GRANITE = granitePlanRecord();

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return { ...base, flags: { ...base.flags, "engagements.v2": true } };
}

function northwind(state: "a" | "b" | "d"): TeamFixture {
  const roster = rosterOf(NORTHWIND_TEAM);
  const id = NORTHWIND.record.id;
  if (state === "b") {
    const before = roster.filter((m) => m.user_id !== KIRA);
    return {
      record: {
        ...NORTHWIND,
        record: { ...NORTHWIND.record, tab_counts: { ...NORTHWIND.record.tab_counts, team: 5 } },
      },
      roster: before,
      approval: { ...northwindApproval(id), changed: false, added_since: [] },
      candidates: candidatesOf(ADD_POOL),
      eqr: [...NORTHWIND_EQR],
    };
  }
  return {
    record: NORTHWIND,
    roster:
      state === "d"
        ? roster.map((m) => (m.user_id === KIRA ? { ...m, independence: "confirmed" } : m))
        : roster,
    approval: northwindApproval(id),
    candidates: candidatesOf(ADD_POOL),
    eqr: [...NORTHWIND_EQR],
  };
}

const TEAMS = {
  fairhaven: (): TeamFixture => ({
    record: FAIRHAVEN,
    roster: rosterOf(FAIRHAVEN_TEAM),
    approval: fairhavenApproval(FAIRHAVEN.record.id),
    candidates: candidatesOf(ADD_POOL),
    eqr: [...FAIRHAVEN_EQR],
  }),
  granite: (): TeamFixture => ({
    record: GRANITE,
    roster: [],
    approval: emptyApproval(GRANITE.record.id),
    candidates: candidatesOf(PARTNER_POOL),
    eqr: [],
  }),
};

function at(
  state: string,
  team: TeamFixture,
  options: { persona?: string; clock?: string; seen?: TeamSeen } = {},
): Scenario {
  const clock = options.clock ?? DEMO_INSTANT;
  const handlers: Record<string, FixtureHandler> = {
    ...E0.handlers,
    ...engagementRecordHandlers(seed, [team.record]),
    ...teamRoleHandlers(seed, [team], {
      now: new Date(clock).toISOString(),
      ...(options.seen === undefined ? {} : { seen: options.seen }),
    }),
    "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
  };
  return { state, persona: options.persona ?? "hannah-leclerc", clock, handlers };
}

const BUILD = {
  a: (seen?: TeamSeen) => at("a", northwind("a"), seen === undefined ? {} : { seen }),
  b: (seen?: TeamSeen) =>
    at("b", northwind("b"), { clock: SEP_11, ...(seen === undefined ? {} : { seen }) }),
  c: (seen?: TeamSeen) =>
    at("c", TEAMS.fairhaven(), {
      persona: "laura-kemp",
      ...(seen === undefined ? {} : { seen }),
    }),
  d: (seen?: TeamSeen) => at("d", northwind("d"), seen === undefined ? {} : { seen }),
  e: (seen?: TeamSeen) => at("e", TEAMS.granite(), seen === undefined ? {} : { seen }),
} as const;

export const scenarios = defineScenarios({
  a: BUILD.a(),
  b: BUILD.b(),
  c: BUILD.c(),
  d: BUILD.d(),
  e: BUILD.e(),
});

export type Eng05State = keyof typeof scenarios;

/** A scenario with fresh handler state (tests that write); `seen` records reminders sent. */
export function freshScenario(state: Eng05State, seen?: TeamSeen): Scenario {
  return BUILD[state](seen);
}

/** The engagement each artboard opens. */
export const OPENS: Readonly<Record<Eng05State, string>> = {
  a: NORTHWIND.record.id,
  b: NORTHWIND.record.id,
  c: FAIRHAVEN.record.id,
  d: NORTHWIND.record.id,
  e: GRANITE.record.id,
};

/** The overlay each artboard opens on (the gallery passes it; the route never does). */
export const OVERLAYS: Readonly<
  Partial<Record<Eng05State, { blocked: string } | { eqr: string }>>
> = {
  b: { blocked: KIRA },
  c: { eqr: THOMAS },
};
