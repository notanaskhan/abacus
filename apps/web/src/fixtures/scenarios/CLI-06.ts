// CLI-06 New client / prospect intake, single client: one fixture scenario per artboard P-07-T49
// builds (docs/screens/CLI-06.md; g, the bulk import, is P-07-T54's). Grace Holloway adds the
// Estate of Walter Thornbury under the existing Walter Thornbury client on Tue Sep 8, 2026,
// 2:10 PM CT, through handlers/intake.ts:
//
//   a  Conflict check: four names, "No conflicts" (the decedent same family, not adverse)
//   b  Entity details with the dedupe card (96% match · Walter Thornbury)
//   c  Related entities · d Contacts · e Services · f Review
//   h  Samuel Ito: Harborline Trust Company, a counterparty to review, "Clear as not adverse…"
//   i  Validation: Date of death empty → "Required for Form 706 due date"
//
// They live under fixtures/ (dev and test only); screens/CLI-06/scenarios.ts re-exports them.

import type {
  CapabilitiesOut,
  ClientIntakeDraftOut,
  ClientIntakeDraftPayload,
  ConflictCheckOut,
  IntakeProblemOut,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { intakeHandlers } from "../handlers/intake";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { entityIdOf, slugOfClient } from "../seed/clients";
import { stableId } from "../seed/prng";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();
const CLOCK = "2026-09-08T14:10:00-05:00";
const NOW = "2026-09-08T19:10:00Z";

export const THORNBURY_CLIENT = stableId(`client:${slugOfClient("Walter Thornbury")}`);
export const DRAFT_ID = stableId("intake-draft:thornbury-estate");
const CHECK_ID = stableId("conflict-check:thornbury-estate:2026-09-08");
const DECEDENT_ENTITY = entityIdOf(slugOfClient("Walter Thornbury"), "Walter Thornbury");

function payload(options: { dod?: boolean; check?: boolean } = {}): ClientIntakeDraftPayload {
  return {
    entity: {
      mode: "existing_client",
      client_id: THORNBURY_CLIENT,
      client_display_name: "Walter Thornbury",
      entity_name: "Estate of Walter Thornbury",
      entity_type: "estate",
      date_of_death: options.dod === false ? null : "2026-02-02",
    },
    relationships: [{ kind: "estate_of", related_entity_id: DECEDENT_ENTITY }],
    contacts: [
      {
        display_name: "Paul Thornbury",
        email: "paul.thornbury@thornburylaw.com",
        roles: ["executor"],
      },
    ],
    services: [
      { type_code: "forms_706_709", forms: ["706"] },
      {
        type_code: "form_1041",
        fiscal_period_start: "2026-02-02",
        fiscal_period_end: "2027-01-31",
      },
      {
        type_code: "form_1040",
        fiscal_period_start: "2026-01-01",
        fiscal_period_end: "2026-02-02",
      },
      { type_code: "form_56" },
    ],
    engagement_partner_user_id: stableId("user:daniel-reyes"),
    ...(options.check === false ? {} : { conflict_check_id: CHECK_ID }),
  };
}

function draft(
  step: ClientIntakeDraftOut["step"],
  p: ClientIntakeDraftPayload,
): ClientIntakeDraftOut {
  return {
    id: DRAFT_ID,
    created_by: stableId("user:grace-holloway"),
    step,
    payload: p,
    saved_at: NOW,
    version: 3,
    allowed_actions: ["client.intake"],
  };
}

function check(hit: boolean): ConflictCheckOut {
  return {
    id: CHECK_ID,
    names_count: 4,
    outcome: hit ? "hits" : "clear",
    run_at: "2026-09-08T19:09:00Z",
    run_by: stableId("user:grace-holloway"),
    subject: { kind: "client_intake_draft", id: DRAFT_ID },
    results: hit
      ? [
          {
            id: stableId("conflict-result:harborline"),
            match_kind: "counterparty",
            matched_name: "Harborline Trust Company",
            assessment: "counterparty_review",
            redacted: false,
            allowed_actions: ["conflict.clear"],
          },
        ]
      : [
          {
            id: stableId("conflict-result:walter-thornbury"),
            match_kind: "relationship",
            matched_name: "Walter Thornbury",
            matched_client_id: THORNBURY_CLIENT,
            assessment: "same_family_not_adverse",
            redacted: false,
          },
        ],
  };
}

const PERSONA = {
  a: "grace-holloway",
  b: "grace-holloway",
  c: "grace-holloway",
  d: "grace-holloway",
  e: "grace-holloway",
  f: "grace-holloway",
  h: "samuel-ito",
  i: "grace-holloway",
} as const;

export type Cli06State = keyof typeof PERSONA;

const STEP: Readonly<Record<Cli06State, ClientIntakeDraftOut["step"]>> = {
  a: "conflicts",
  b: "entity",
  c: "relationships",
  d: "contacts",
  e: "services",
  f: "review",
  h: "conflicts",
  i: "entity",
};

/** What each artboard opens on: the step, and i's problem from the services step's Next. */
export const OPENS: Readonly<
  Record<
    Cli06State,
    { step: ClientIntakeDraftOut["step"]; problems?: IntakeProblemOut[]; screened?: boolean }
  >
> = {
  a: { step: "conflicts", screened: true },
  b: { step: "entity" },
  c: { step: "relationships" },
  d: { step: "contacts" },
  e: { step: "services" },
  f: { step: "review" },
  h: { step: "conflicts" },
  i: {
    step: "entity",
    problems: [{ field: "entity.date_of_death", code: "date_of_death_required" }],
  },
};

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "grace-holloway");
  return { ...base, flags: { ...base.flags, "clients.v2": true } };
}

function build(state: Cli06State): Scenario {
  const handlers: Record<string, FixtureHandler> = {
    ...E0.handlers,
    ...intakeHandlers({
      draft: draft(STEP[state], payload({ dod: state !== "i", check: state !== "i" })),
      check: check(state === "h"),
      dedupe: { name: "Walter Thornbury", clientId: THORNBURY_CLIENT, score: 96 },
      now: NOW,
    }),
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
  h: build("h"),
  i: build("i"),
});

export function freshScenario(state: Cli06State): Scenario {
  return build(state);
}
