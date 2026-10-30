// CLI-05's tax profiles (T-01-T14; docs/screens/CLI-05.md d and f; the handoff spec): the Whitley
// household (Consents d: use and AI disclosure signed Jan 20, 2026 by Marcus and Dana) and the
// Ferris household (f: envelope E17, Morgan ✓ Sep 9, Kai ○). The consents are ADM-05's rows
// (`seed/consents.ts`), so the registry and the profile agree. The identity band carries the last
// four only (DEC-52); a reveal answers the seed's synthetic value, never a real TIN.
// T-01-T34 adds the 8821's designees with CAF last four only (c), Ridgeline's elections (e)
// and Aurelio Santos with no authorization on file (g).
import type { ConsentOut, TaxProfileOut } from "@abacus/api-client";
import { REGISTRY_CONSENTS } from "./consents";
import { stableId } from "./prng";

function consentsOf(client: string): ConsentOut[] {
  return REGISTRY_CONSENTS.filter((c) => c.client_name === client);
}

export const WHITLEY_CLIENT_ID = stableId("client:marcus-dana-whitley");
export const WHITLEY_ENTITY = stableId("client-entity:marcus-dana-whitley");
export const WHITLEY_SPOUSE_ENTITY = stableId("client-entity:dana-whitley");
export const FERRIS_CLIENT_ID = stableId("client:morgan-kai-ferris");
export const FERRIS_ENTITY = stableId("client-entity:morgan-kai-ferris");
export const FERRIS_SPOUSE_ENTITY = stableId("client-entity:kai-ferris");
export const RIDGELINE_ENTITY = stableId("client-entity:ridgeline-property-partners");
export const SANTOS_ENTITY = stableId("client-entity:aurelio-santos");

const AUTHORIZATION_8821: TaxProfileOut["authorizations"][number] = {
  id: stableId("tax-authorization:whitley-8821"),
  form: "8821",
  state_form_code: null,
  // The CAF numbers are sealed; the profile carries their last four only (T-01 §4.3).
  designees: [
    { user_id: stableId("user:daniel-reyes"), name: "Daniel Reyes", caf_last4: "0912" },
    { user_id: stableId("user:kevin-osei"), name: "Kevin Osei", caf_last4: "4471" },
  ],
  tax_matters: ["Income · Form 1040"],
  tax_years: [2022, 2023, 2024, 2025, 2026],
  received_on: "2026-02-03",
  expires_on: null,
  status: "on_file",
};

/** Ridgeline's elections for TY2025 (e; blueprint §9.8): the server's codes, worded by CLI-05. */
const RIDGELINE_ELECTIONS: TaxProfileOut["elections"] = [
  {
    kind: "section_754",
    status_code: "pending",
    jurisdiction: null,
    amount: null,
    tax_year: 2025,
  },
  { kind: "ptet", status_code: "elected", jurisdiction: "IL", amount: "28044", tax_year: 2025 },
  { kind: "ptet", status_code: "elected", jurisdiction: "CO", amount: "17070", tax_year: 2025 },
  { kind: "ptet", status_code: "elected", jurisdiction: "NY", amount: "18982", tax_year: 2025 },
  {
    kind: "bba_representative",
    status_code: "designated",
    jurisdiction: null,
    amount: null,
    tax_year: 2025,
  },
  {
    kind: "bba_opt_out",
    status_code: "not_eligible",
    jurisdiction: null,
    amount: null,
    tax_year: 2025,
  },
  {
    kind: "section_163j",
    status_code: "exempt",
    jurisdiction: null,
    amount: null,
    tax_year: 2025,
  },
  {
    kind: "accounting_method",
    status_code: "accrual",
    jurisdiction: null,
    amount: null,
    tax_year: 2025,
  },
];

export const TAX_PROFILES: Readonly<Record<string, TaxProfileOut>> = {
  [WHITLEY_ENTITY]: {
    client_entity_id: WHITLEY_ENTITY,
    taxpayer_tin: { kind: "ssn", presence: "on_file", last4: "0426" },
    consents: consentsOf("Marcus & Dana Whitley"),
    authorizations: [AUTHORIZATION_8821],
    elections: [],
    open_notices: 1,
    allowed_actions: ["tax_profile.read", "consent.read", "consent.request", "tin.reveal"],
    client_name: "Marcus & Dana Whitley",
    client_kind: "Household",
    partner_name: "Daniel Reyes",
    office_name: "Denver",
    identity: [
      {
        role: "taxpayer",
        client_entity_id: WHITLEY_ENTITY,
        name: "Marcus Whitley",
        masked_tin: { kind: "ssn", presence: "on_file", last4: "0426" },
      },
      {
        role: "spouse",
        client_entity_id: WHITLEY_SPOUSE_ENTITY,
        name: "Dana Whitley",
        masked_tin: { kind: "ssn", presence: "on_file", last4: "0519" },
      },
    ],
    portal_user_name: "Dana Whitley",
    resident_state: "Colorado",
  },
  [FERRIS_ENTITY]: {
    client_entity_id: FERRIS_ENTITY,
    taxpayer_tin: { kind: "ssn", presence: "on_file", last4: "0733" },
    consents: consentsOf("Morgan & Kai Ferris"),
    authorizations: [],
    elections: [],
    open_notices: 0,
    allowed_actions: ["tax_profile.read", "consent.read", "consent.request", "tin.reveal"],
    client_name: "Morgan & Kai Ferris",
    client_kind: "Household",
    partner_name: "Daniel Reyes",
    office_name: "Chicago",
    identity: [
      {
        role: "taxpayer",
        client_entity_id: FERRIS_ENTITY,
        name: "Morgan Ferris",
        masked_tin: { kind: "ssn", presence: "on_file", last4: "0733" },
      },
      {
        role: "spouse",
        client_entity_id: FERRIS_SPOUSE_ENTITY,
        name: "Kai Ferris",
        masked_tin: { kind: "ssn", presence: "on_file", last4: "0841" },
      },
    ],
    portal_user_name: "Morgan Ferris",
    resident_state: "Illinois",
  },
  [RIDGELINE_ENTITY]: {
    client_entity_id: RIDGELINE_ENTITY,
    taxpayer_tin: { kind: "ein", presence: "on_file", last4: "2716" },
    consents: [],
    authorizations: [],
    elections: RIDGELINE_ELECTIONS,
    open_notices: 0,
    allowed_actions: ["tax_profile.read", "consent.read", "tax_election.manage"],
    client_name: "Ridgeline Property Partners, LP",
    client_kind: "Partnership",
    partner_name: "Daniel Reyes",
    office_name: "Chicago",
    identity: [
      {
        role: "taxpayer",
        client_entity_id: RIDGELINE_ENTITY,
        name: "Ridgeline Property Partners, LP",
        masked_tin: { kind: "ein", presence: "on_file", last4: "2716" },
      },
    ],
    portal_user_name: null,
    resident_state: null,
  },
  [SANTOS_ENTITY]: {
    client_entity_id: SANTOS_ENTITY,
    taxpayer_tin: null,
    consents: [],
    authorizations: [],
    elections: [],
    open_notices: 0,
    allowed_actions: ["tax_profile.read", "consent.read", "tax_authorization.manage"],
    client_name: "Aurelio Santos",
    client_kind: "Individual",
    partner_name: null,
    office_name: "Chicago",
    identity: [
      {
        role: "taxpayer",
        client_entity_id: SANTOS_ENTITY,
        name: "Aurelio Santos",
        masked_tin: null,
      },
    ],
    portal_user_name: null,
    resident_state: null,
  },
};

/** What a reveal answers, by entity: synthetic values (an invalid SSN area, never a person's). */
export const SYNTHETIC_TINS: Readonly<Record<string, string>> = {
  [WHITLEY_ENTITY]: "000-00-0426",
  [WHITLEY_SPOUSE_ENTITY]: "000-00-0519",
  [FERRIS_ENTITY]: "000-00-0733",
  [FERRIS_SPOUSE_ENTITY]: "000-00-0841",
};
