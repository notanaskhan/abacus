// CLI-08 Independence & conflicts: one fixture scenario per artboard (P-07-T48;
// docs/screens/CLI-08.md), plus the undesigned declined-note state (DF-06). Northwind's PY2025
// EBP audit at E0, Mon Sep 14, 2026, 9:24 AM CT, through handlers/independence.ts:
//
//   a  Hannah Leclerc · Team confirmations: 4 of 5, Ana Cruz pending (2 reminders)
//   b  Hannah Leclerc · NAS matrix under ET 1.295, the SKE designee named
//   c  Hannah Leclerc · Conflicts: 7 names searched, Harborline "Not adverse"
//   d  Hannah Leclerc · Rotation: EP 5 years, EQR 3, Manager 4; review after 7
//   e  Ana Cruz · her own confirmation sheet (three statements → Confirm)
//   f  Margaret Okonkwo · 5 of 5, Conclude… enabled
//   g  Hannah Leclerc · a breach logged
//   declined  Hannah Leclerc · Ana declined with a note
//
// They live under fixtures/ (dev and test only); screens/CLI-08/scenarios.ts re-exports them.

import type { CapabilitiesOut, MemberConfirmationOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { type IndependenceFixture, independenceHandlers } from "../handlers/independence";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { stableId } from "../seed/prng";
import { capabilitiesFor } from "../seed/shell";
import { northwindRecord } from "../seed/team-roles";

const E0 = seedScenario();
const seed = getSeed();
const CLOCK = "2026-09-14T09:24:00-05:00";
const NORTHWIND = northwindRecord(seed).record;

export const ENGAGEMENT_ID = NORTHWIND.id;
export const CLIENT_ID = NORTHWIND.client_id;
export const CHECK_ID = stableId("conflict-check:northwind:2026-08-03");
export const SKE_CONTACT = stableId("contact:dana-kowalski");

const id = (slug: string): string => stableId(`user:${slug}`);

function member(
  slug: string,
  name: string,
  role: string,
  confirmation: MemberConfirmationOut["confirmation"],
  answered: string | null,
  reminders = 0,
): MemberConfirmationOut {
  return {
    user_id: id(slug),
    display_name: name,
    role,
    confirmation,
    answered_at: answered,
    annual_confirmed: true,
    reminder_count: reminders,
    statement_version: confirmation === "confirmed" ? "northwind-2025-v1" : null,
  };
}

function team(ana: MemberConfirmationOut["confirmation"], note?: string): MemberConfirmationOut[] {
  return [
    member(
      "margaret-okonkwo",
      "Margaret Okonkwo",
      "engagement_partner",
      "confirmed",
      "2026-08-03T15:00:00Z",
    ),
    member(
      "thomas-whitcombe",
      "Thomas Whitcombe",
      "eqr_reviewer",
      "confirmed",
      "2026-08-04T15:00:00Z",
    ),
    member("hannah-leclerc", "Hannah Leclerc", "manager", "confirmed", "2026-08-03T15:00:00Z"),
    member("marcus-delaney", "Marcus Delaney", "senior", "confirmed", "2026-08-03T15:00:00Z"),
    {
      ...member(
        "ana-cruz",
        "Ana Cruz",
        "staff",
        ana,
        ana === "requested" ? null : "2026-09-14T14:31:00Z",
        ana === "requested" ? 2 : 0,
      ),
      ...(note === undefined ? {} : { decline_note: note }),
    },
  ];
}

function fixture(
  options: { ana?: MemberConfirmationOut["confirmation"]; note?: string; breach?: boolean } = {},
): IndependenceFixture {
  return {
    engagementId: ENGAGEMENT_ID,
    members: team(options.ana ?? "requested", options.note),
    attest: true,
    nas: {
      attest_client: true,
      ske_designee_contact_id: SKE_CONTACT,
      rows: [
        {
          service_code: "fs_drafting",
          provided: true,
          status: "concluded",
          evaluation: "Permitted — management takes responsibility",
          safeguards:
            "Dana reviews and approves the FS; management-responsibility acknowledgment in the engagement letter",
          ske_contact_id: SKE_CONTACT,
        },
        {
          service_code: "form_5500",
          provided: false,
          status: "not_applicable",
          safeguards: "Prepared by Summit Plan Administrators (TPA)",
        },
        {
          service_code: "payroll_recordkeeping",
          provided: false,
          status: "not_applicable",
          safeguards: "PayGrid Payroll; Keystone Retirement Services",
        },
        {
          service_code: "corporate_tax",
          provided: false,
          status: "not_applicable",
          safeguards: "No other services to the sponsor",
        },
      ],
    },
    rotation: {
      review_years: 7,
      rows: [
        {
          user_id: id("margaret-okonkwo"),
          display_name: "Margaret Okonkwo",
          role: "engagement_partner",
          years_served: 5,
          familiarity_flag: false,
        },
        {
          user_id: id("thomas-whitcombe"),
          display_name: "Thomas Whitcombe",
          role: "eqr_reviewer",
          years_served: 3,
          familiarity_flag: false,
        },
        {
          user_id: id("hannah-leclerc"),
          display_name: "Hannah Leclerc",
          role: "manager",
          years_served: 4,
          familiarity_flag: false,
        },
      ],
    },
    check: {
      id: CHECK_ID,
      names_count: 7,
      outcome: "hits",
      run_at: "2026-08-03T15:12:00Z",
      run_by: id("hannah-leclerc"),
      subject: { kind: "client", id: CLIENT_ID },
      results: [
        {
          id: stableId("conflict-result:harborline"),
          match_kind: "relationship",
          matched_name: "Harborline Trust Company",
          assessment: "not_adverse",
          cleared_by: id("hannah-leclerc"),
          cleared_at: "2026-08-03T15:20:00Z",
          redacted: false,
        },
      ],
    },
    breach: options.breach === true,
    conclusion: null,
    now: "2026-09-14T14:31:00Z",
  };
}

const PERSONA = {
  a: "hannah-leclerc",
  b: "hannah-leclerc",
  c: "hannah-leclerc",
  d: "hannah-leclerc",
  e: "ana-cruz",
  f: "margaret-okonkwo",
  g: "hannah-leclerc",
  declined: "hannah-leclerc",
} as const;

export type Cli08State = keyof typeof PERSONA;

export type Cli08Tab = "conflicts" | "nas" | "team" | "rotation";

/** The tab each artboard opens on. */
export const OPENS: Readonly<Record<Cli08State, { tab: Cli08Tab; sheet?: boolean }>> = {
  a: { tab: "team" },
  b: { tab: "nas" },
  c: { tab: "conflicts" },
  d: { tab: "rotation" },
  e: { tab: "team", sheet: true },
  f: { tab: "team" },
  g: { tab: "team" },
  declined: { tab: "team" },
};

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return {
    ...base,
    flags: { ...base.flags, "engagements.v2": true, "engagements.acceptance_v2": true },
  };
}

function build(state: Cli08State): Scenario {
  const data =
    state === "f"
      ? fixture({ ana: "confirmed" })
      : state === "g"
        ? fixture({ breach: true })
        : state === "declined"
          ? fixture({
              ana: "declined",
              note: "My spouse joined Keystone Retirement Services in August.",
            })
          : fixture();
  const handlers: Record<string, FixtureHandler> = {
    ...E0.handlers,
    ...independenceHandlers(data),
    "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
  };
  return { state, persona: PERSONA[state], clock: CLOCK, handlers };
}

export const scenarios = defineScenarios({
  a: build("a"),
  b: build("b"),
  c: build("c"),
  d: build("d"),
  e: build("e"),
  f: build("f"),
  g: build("g"),
  declined: build("declined"),
});

/** A scenario with fresh handler state (tests that write). */
export function freshScenario(state: Cli08State): Scenario {
  return build(state);
}
