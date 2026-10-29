// CLI-05's tax profiles (T-01-T14; docs/screens/CLI-05.md d and f; the handoff spec): the Whitley
// household (Consents d: use and AI disclosure signed Jan 20, 2026 by Marcus and Dana) and the
// Ferris household (f: envelope E17, Morgan ✓ Sep 9, Kai ○). The consents are ADM-05's rows
// (`seed/consents.ts`), so the registry and the profile agree. The identity band carries the last
// four only (DEC-52); a reveal answers the seed's synthetic value, never a real TIN.
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

const AUTHORIZATION_8821: TaxProfileOut["authorizations"][number] = {
  id: stableId("tax-authorization:whitley-8821"),
  form: "8821",
  state_form_code: null,
  designees: [],
  tax_matters: ["Income · Form 1040"],
  tax_years: [2022, 2023, 2024, 2025, 2026],
  received_on: "2026-02-03",
  expires_on: null,
  status: "on_file",
};

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
        tin: { kind: "ssn", presence: "on_file", last4: "0426" },
      },
      {
        role: "spouse",
        client_entity_id: WHITLEY_SPOUSE_ENTITY,
        name: "Dana Whitley",
        tin: { kind: "ssn", presence: "on_file", last4: "0519" },
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
        tin: { kind: "ssn", presence: "on_file", last4: "0733" },
      },
      {
        role: "spouse",
        client_entity_id: FERRIS_SPOUSE_ENTITY,
        name: "Kai Ferris",
        tin: { kind: "ssn", presence: "on_file", last4: "0841" },
      },
    ],
    portal_user_name: "Morgan Ferris",
    resident_state: "Illinois",
  },
};

/** What a reveal answers, by entity: synthetic values (an invalid SSN area, never a person's). */
export const SYNTHETIC_TINS: Readonly<Record<string, string>> = {
  [WHITLEY_ENTITY]: "000-00-0426",
  [WHITLEY_SPOUSE_ENTITY]: "000-00-0519",
  [FERRIS_ENTITY]: "000-00-0733",
  [FERRIS_SPOUSE_ENTITY]: "000-00-0841",
};
