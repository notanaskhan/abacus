// CLI-04 Contacts & portal access: one fixture scenario per artboard (P-07-T33;
// docs/screens/CLI-04.md). All stand at E0, Mon Sep 14, 2026, 9:24 AM CT, seen by Grace Holloway
// (Firm Admin; the README's "Sam Ortiz" for d and e is a label error, OQ-13). Data: the client
// records (seed/client-records.ts) and the contacts (handlers/contacts.ts), with `contacts.v2`
// on. Each artboard is a data condition and the overlay it opens on:
//
//   a  Northwind's six contacts: 3 active · 1 invited · 2 not invited; 10 + 9 + 2 + 2 + 1 = 24
//   b  a, Harborline's "Invite…" sheet open with its two delegated requests ticked
//   c  Harborline Invited, sent Sep 14 (the state after b's send)
//   d  Sam Ortiz's portal user Locked after three incorrect codes (DF-24): "Unlock…"
//   e  Sam Ortiz's "Change scope…" sheet with his 9 delegated requests
//   f  Summit's "Revoke…" dialog
//   g  Copperleaf (non-attest): Tess Moreno owner, Ben Ashby controller
//
// They live under fixtures/ (dev and test only); screens/CLI-04/scenarios.ts re-exports them.

import type { CapabilitiesOut, ClientRecordOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { clientRecordHandlers } from "../handlers/client-record";
import { type ContactFixture, contactHandlers, seedContacts } from "../handlers/contacts";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { COPPERLEAF, NORTHWIND, clientIdOf } from "../seed/client-records";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();
const CONTACTS = seedContacts(seed);

function idOf(name: string): string {
  return CONTACTS.find((c) => c.row.name === name)?.row.id ?? "";
}

export const HARBORLINE = idOf("Harborline Trust Company");
export const SAM_ORTIZ = idOf("Sam Ortiz");
export const SUMMIT = idOf("Summit Plan Administrators");
export const NORTHWIND_ID = clientIdOf(NORTHWIND);
export const COPPERLEAF_ID = clientIdOf(COPPERLEAF);

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "grace-holloway");
  return {
    ...base,
    capabilities: [...base.capabilities, "client.read"],
    flags: { ...base.flags, "contacts.v2": true },
  };
}

function set(name: string, change: (c: ContactFixture) => void) {
  return (contacts: ContactFixture[]): void => {
    const found = contacts.find((c) => c.row.name === name);
    if (found !== undefined) change(found);
  };
}

function at(state: string, change?: (contacts: ContactFixture[]) => void): Scenario {
  const records = clientRecordHandlers(seed);
  const record = records["GET /v1/clients/{client_id}"];
  const contacts = contactHandlers(seed, change === undefined ? {} : { change });
  const handlers: Record<string, FixtureHandler> = {
    ...E0.handlers,
    ...records,
    ...contacts,
    // The record's "Contacts & access" count is its contacts (6 on Northwind, 2 on Copperleaf).
    "GET /v1/clients/{client_id}": async (request) => {
      const answer = record === undefined ? json({}, 404) : await record(request);
      if (!answer.ok) return answer;
      const body = (await answer.json()) as ClientRecordOut;
      const n = CONTACTS.filter((c) => c.clientId === body.id).length;
      return json({ ...body, tab_counts: { ...body.tab_counts, contacts: n } });
    },
    "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
  };
  return { state, persona: "grace-holloway", clock: DEMO_INSTANT, handlers };
}

const BUILD = {
  a: () => at("a"),
  b: () => at("b"),
  c: () =>
    at(
      "c",
      set("Harborline Trust Company", (c) => {
        c.row = {
          ...c.row,
          portal_status: "invited",
          invited_on: "2026-09-14",
          expires_on: "2026-09-28",
          invitation_id: "00000000-0000-4000-8000-000000000c04",
        };
      }),
    ),
  d: () =>
    at(
      "d",
      set("Sam Ortiz", (c) => {
        c.row = { ...c.row, portal_status: "locked" };
        c.signIns = [
          ...c.signIns,
          { kind: "code_failed", at: "2026-09-14T14:00:00Z" },
          { kind: "code_failed", at: "2026-09-14T14:01:00Z" },
          { kind: "locked", at: "2026-09-14T14:02:00Z" },
        ];
      }),
    ),
  e: () => at("e"),
  f: () => at("f"),
  g: () => at("g"),
} as const;

export const scenarios = defineScenarios({
  a: BUILD.a(),
  b: BUILD.b(),
  c: BUILD.c(),
  d: BUILD.d(),
  e: BUILD.e(),
  f: BUILD.f(),
  g: BUILD.g(),
});

export type Cli04State = keyof typeof scenarios;

/** A scenario with fresh handler state (tests that write). */
export function freshScenario(state: Cli04State): Scenario {
  return BUILD[state]();
}

/** The client each artboard opens. */
export const OPENS: Readonly<Record<Cli04State, string>> = {
  a: NORTHWIND_ID,
  b: NORTHWIND_ID,
  c: NORTHWIND_ID,
  d: NORTHWIND_ID,
  e: NORTHWIND_ID,
  f: NORTHWIND_ID,
  g: COPPERLEAF_ID,
};

/** The overlay each artboard opens on (the gallery passes it; the route never does). */
export const OVERLAYS: Readonly<
  Partial<
    Record<
      Cli04State,
      { sheet: string; mode: "invite" | "scope" } | { revoke: string } | { unlock: string }
    >
  >
> = {
  b: { sheet: HARBORLINE, mode: "invite" },
  e: { sheet: SAM_ORTIZ, mode: "scope" },
  f: { revoke: SUMMIT },
};
