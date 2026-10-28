// CLI-06 New client / prospect intake: one fixture scenario per artboard, single client (P-07-T49)
// and the bulk import g (P-07-T54) (docs/screens/CLI-06.md). Grace Holloway adds the
// Estate of Walter Thornbury under the existing Walter Thornbury client on Tue Sep 8, 2026,
// 2:10 PM CT, through handlers/intake.ts:
//
//   a  Conflict check: four names, "No conflicts" (the decedent same family, not adverse)
//   b  Entity details with the dedupe card (96% match · Walter Thornbury)
//   c  Related entities · d Contacts · e Services · f Review
//   h  Samuel Ito: Harborline Trust Company, a counterparty to review, "Clear as not adverse…"
//   i  Validation: Date of death empty → "Required for Form 706 due date"
//   g  Bulk import at 2:04 PM: the synthetic 212-row CCH Axcess Tax client list (P-07-T50's file,
//      backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/client_list.py) scored as the
//      live import scores it: 204 matched + 8 to review + 0 new = 212. The eight are the file's
//      rows 7, 8, 10, 15, 30, 33, 34 and 38 (practice-management spellings, 77–85%); Grace has
//      merged six and skipped rows 7 and 8, so "Import 210 records" (212 − 2)
//
// They live under fixtures/ (dev and test only); screens/CLI-06/scenarios.ts re-exports them.

import type {
  CapabilitiesOut,
  ClientImportOut,
  ClientImportRowOut,
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
import { importHandlers } from "../handlers/imports";
import { intakeHandlers } from "../handlers/intake";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { buildClients, entityIdOf, slugOfClient } from "../seed/clients";
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
export const IMPORT_ID = stableId("client-import:cch-client-list:2026-09-08");
const GRACE = stableId("user:grace-holloway");

// g: the file's eight rows a person reviews (row, as the file spells it, the client, its score:
// pg_trgm similarity of the normalised names, DEC-441). Rows 7 and 8 are skipped (handoff g).
const REVIEW: readonly (readonly [number, string, string, number])[] = [
  [7, "Harbourview Dental Properties LP", "Harborview Dental Properties, LP", 0.8438],
  [8, "Marcus & Dana Whiteley", "Marcus & Dana Whitley", 0.7826],
  [10, "Blue Stem Analytics LLC", "Bluestem Analytics, LLC", 0.7727],
  [15, "Juniper and Oak Interiors LLC", "Juniper & Oak Interiors, LLC", 0.8462],
  [30, "Kestrel Ventures Fund 1 LP", "Kestrel Ventures Fund I, LP", 0.8462],
  [33, "Summitline Logistics Inc", "Summit Line Logistics, Inc.", 0.8261],
  [34, "Pine Crest Pediatrics PC", "Pinecrest Pediatrics, PC", 0.7826],
  [38, "Riverbend Community Theatre", "Riverbend Community Theater", 0.8065],
];
const SKIPPED_ROWS = new Set([7, 8]);
const PLANS = ["Northwind Robotics 401(k) Plan", "Granite Peak Outdoor Supply 401(k) Plan"];
const PLAN_SPONSORS = ["Northwind Robotics, Inc.", "Granite Peak Outdoor Supply, Inc."];
const TRUSTS = 26;

/** The CLI-06 snapshot's name for a client (the holdout keeps Walter Thornbury, DEC-593). */
function atSnapshot(name: string): string {
  return name === "Estate of Walter Thornbury" ? "Walter Thornbury" : name;
}

function clientIdOf(name: string): string {
  return stableId(`client:${slugOfClient(name)}`);
}

/** The 212 rows as the import scored them, with g's decisions. */
export function importRows(): ClientImportRowOut[] {
  const clients = buildClients();
  const reviewed = new Set(REVIEW.map(([, , client]) => client));
  const matched = clients.map((c) => atSnapshot(c.name)).filter((n) => !reviewed.has(n));
  const at = new Map(REVIEW.map((r) => [r[0], r]));
  const out: ClientImportRowOut[] = [];
  const row = (name: string, client: string, score: number): void => {
    const rowNo = out.length + 1;
    const review = score < 0.9;
    out.push({
      id: stableId(`client-import-row:${String(rowNo)}`),
      row_no: rowNo,
      display_name: name,
      best_match_client_id: clientIdOf(client),
      best_match_name: client,
      score,
      decision: review ? (SKIPPED_ROWS.has(rowNo) ? "skip" : "merge") : "merge",
      decided_by: review ? GRACE : null,
      error_code: null,
      tin: null,
    });
  };
  let next = 0;
  for (let n = 1; n <= clients.length; n += 1) {
    const r = at.get(n);
    if (r !== undefined) {
      row(r[1], r[2], r[3]);
    } else {
      const name = matched[next] ?? "";
      next += 1;
      row(name, name, 1);
    }
  }
  PLANS.forEach((plan, i) => {
    row(plan, PLAN_SPONSORS[i] ?? "", 1);
  });
  const grantors = clients
    .filter((c) => (c.kind === "individual" || c.kind === "household") && !reviewed.has(c.name))
    .filter((c) => atSnapshot(c.name) === c.name)
    .slice(0, TRUSTS);
  for (const g of grantors) row(`${g.name} Revocable Trust`, g.name, 0.96);
  return out;
}

function clientImport(): ClientImportOut {
  return {
    id: IMPORT_ID,
    source: "cch_axcess_tax_export",
    stage: "reviewing",
    file_name: "cch-axcess-client-list.csv",
    mapping: { "Client Name": "client_name", "Client Type": "entity_type" },
    counts: { rows: 212, matched: 204, to_review: 8, new: 0, skipped: 0, imported: 0, failed: 0 },
    started_at: "2026-09-08T19:04:00Z",
    started_by: GRACE,
    completed_at: null,
    allowed_actions: ["client_import.run"],
  };
}

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
  g: "grace-holloway",
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
  g: "entity",
  h: "conflicts",
  i: "entity",
};

/** What each artboard opens on: the step, i's problem from the services step's Next, and g's
 * bulk import on its review. */
export const OPENS: Readonly<
  Record<
    Cli06State,
    {
      step: ClientIntakeDraftOut["step"];
      problems?: IntakeProblemOut[];
      screened?: boolean;
      bulk?: { importId: string; step: "review" };
    }
  >
> = {
  a: { step: "conflicts", screened: true },
  b: { step: "entity" },
  c: { step: "relationships" },
  d: { step: "contacts" },
  e: { step: "services" },
  f: { step: "review" },
  g: { step: "entity", bulk: { importId: IMPORT_ID, step: "review" } },
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

const CLOCK_G = "2026-09-08T14:04:00-05:00";

function build(state: Cli06State): Scenario {
  const handlers: Record<string, FixtureHandler> = {
    ...E0.handlers,
    ...intakeHandlers({
      draft: draft(STEP[state], payload({ dod: state !== "i", check: state !== "i" })),
      check: check(state === "h"),
      dedupe: { name: "Walter Thornbury", clientId: THORNBURY_CLIENT, score: 96 },
      now: NOW,
    }),
    ...importHandlers({
      import: clientImport(),
      rows: importRows(),
      now: "2026-09-08T19:04:00Z",
      decidedBy: GRACE,
    }),
    "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
  };
  return { state, persona: PERSONA[state], clock: state === "g" ? CLOCK_G : CLOCK, handlers };
}

export const scenarios = defineScenarios({
  a: build("a"),
  b: build("b"),
  c: build("c"),
  d: build("d"),
  e: build("e"),
  f: build("f"),
  g: build("g"),
  h: build("h"),
  i: build("i"),
});

export function freshScenario(state: Cli06State): Scenario {
  return build(state);
}
