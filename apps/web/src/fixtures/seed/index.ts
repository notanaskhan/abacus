// The interim TS seed (F-04-T05): the E0 audit-core slice plus the portal minimum of the
// Brightwater Hale LLP scenario (SPEC-307), typed against the generated API client so a schema
// change breaks the build, and generated deterministically (seeded PRNG and the scenario clock; no
// unseeded randomness and no wall clock). F-04-T31 retires it for the Python scenario's fixtures.
// Fixture mode reads it through fixtures/handlers.ts; nothing here touches the network.

import type {
  ClientContactOut,
  EngagementOut,
  EngagementSummaryOut,
  FirmClientOut,
  FirmMemberOut,
  MeOut,
  RequestItemOut,
  StaffMemberOut,
  WorkItemOut,
} from "@abacus/api-client";
import { buildEngagements, summaryOf } from "./audits";
import { type SeedClient, buildClients } from "./clients";
import { DEMO_INSTANT, DEMO_MS } from "./clock";
import { FIRM_ROLES, OFFICES, SEATS, type Seat, emailOf, slugOf } from "./people";
import { PORTAL_USERS, type PortalUser, THIRD_PARTIES, contactsOf } from "./portal";
import { stableId } from "./prng";
import { feldRequests, granitePeakRequests, northwindRequests } from "./requests";

export { DEMO_INSTANT, DEMO_MS };

/** Scenario holdouts (SPEC-307 AC-3): leave a client and its engagement out so a journey creates them. */
export type Holdout = "fairhaven_ebp" | "copperleaf";

const HOLDOUT_CLIENT: Record<Holdout, string> = {
  fairhaven_ebp: "Fairhaven Foods 401(k) Plan",
  copperleaf: "Copperleaf Coffee Roasters, Inc.",
};

export interface SeedPerson {
  slug: string;
  userId: string;
  name: string;
  email: string;
  /** A seat holder (firm app) or a portal user (client portal). */
  kind: "staff" | "client";
}

export interface Wall {
  clientId: string;
  clientName: string;
  /** The person walled off, as a persona slug. */
  personSlug: string;
  reason: string;
}

export interface Seed {
  firm: {
    id: string;
    name: string;
    shortName: string;
    synthetic: true;
    timeZone: string;
    offices: typeof OFFICES;
  };
  clock: { instant: string; ms: number };
  seats: readonly Seat[];
  /** `GET /v1/firm/staff`: the 46 seat holders. */
  staff: StaffMemberOut[];
  /** `GET /v1/firm/members`. */
  members: FirmMemberOut[];
  clients: SeedClient[];
  clientIds: Record<string, string>;
  /** `GET /v1/firm/clients`. */
  firmClients: FirmClientOut[];
  /** The 27 audits and assurance engagements, plus the Feld household's Form 1040. */
  engagements: EngagementOut[];
  summaries: EngagementSummaryOut[];
  /** Engagement ids by label: "A1" to "A27", "feld". */
  engagementIds: Record<string, string>;
  workItems: Record<string, WorkItemOut[]>;
  requestItems: Record<string, RequestItemOut[]>;
  /** Who answers each request, by request id. */
  requestOwners: Record<string, string>;
  portalUsers: readonly PortalUser[];
  thirdParties: readonly string[];
  contacts: Record<string, ClientContactOut[]>;
  walls: Wall[];
  people: SeedPerson[];
  /** Money is a decimal string, never a number (Northwind PY2025, blueprint 01 §9.4). */
  figures: { northwind: Record<string, string> };
}

const NORTHWIND_FIGURES: Record<string, string> = {
  netAssetsAvailable20251231: "16861000.00",
  netAssetsAvailable20250101: "14228500.00",
  netAssetsUnadjusted: "16812400.00",
  contributionsReceivable: "48600.00",
  materialityDecided: "252200.00",
};

export function buildSeed(options: { holdouts?: readonly Holdout[] } = {}): Seed {
  const held = new Set((options.holdouts ?? []).map((h) => HOLDOUT_CLIENT[h]));
  const clients = buildClients().filter((c) => !held.has(c.name));
  const clientIds = Object.fromEntries(clients.map((c) => [c.slug, stableId(`client:${c.slug}`)]));

  const staff: StaffMemberOut[] = SEATS.map((seat) => ({
    user_id: stableId(`user:${slugOf(seat.name)}`),
    display_name: seat.name,
    email: emailOf(seat.name),
    firm_role: FIRM_ROLES[seat.initials] ?? null,
    status: "active",
  }));

  const { engagements, workItems, ids } = buildEngagements(clients);
  const requestItems: Record<string, RequestItemOut[]> = {};
  const requestOwners: Record<string, string> = {};
  const lists: [string | undefined, ReturnType<typeof northwindRequests>][] = [
    [ids.A1, ids.A1 === undefined ? [] : northwindRequests(ids.A1)],
    [ids.A2, ids.A2 === undefined ? [] : granitePeakRequests(ids.A2)],
    [ids.feld, ids.feld === undefined ? [] : feldRequests(ids.feld)],
  ];
  for (const [id, list] of lists) {
    if (id === undefined) continue;
    requestItems[id] = list.map((r) => r.item);
    for (const r of list) requestOwners[r.item.id] = r.owner;
  }

  const contacts: Record<string, ClientContactOut[]> = {};
  if (ids.A1 !== undefined) contacts[ids.A1] = contactsOf("northwind");
  if (ids.A2 !== undefined) contacts[ids.A2] = contactsOf("granite-peak");
  if (ids.feld !== undefined) contacts[ids.feld] = contactsOf("feld");

  // ADM-03: Lena Park is walled from Ashford Manufacturing (personal relationship).
  const ashford = clients.find((c) => c.name === "Ashford Manufacturing Co.");
  const walls: Wall[] =
    ashford === undefined
      ? []
      : [
          {
            clientId: stableId(`client:${ashford.slug}`),
            clientName: ashford.name,
            personSlug: "lena-park",
            reason: "Personal relationship",
          },
        ];

  const people: SeedPerson[] = [
    ...SEATS.map((s) => ({
      slug: slugOf(s.name),
      userId: stableId(`user:${slugOf(s.name)}`),
      name: s.name,
      email: emailOf(s.name),
      kind: "staff" as const,
    })),
    ...PORTAL_USERS.map((u) => ({
      slug: u.slug,
      userId: u.id,
      name: u.name,
      email: u.email,
      kind: "client" as const,
    })),
  ];

  return {
    firm: {
      id: stableId("firm:brightwater-hale"),
      name: "Brightwater Hale LLP",
      shortName: "Brightwater Hale",
      synthetic: true,
      timeZone: "America/Chicago",
      offices: OFFICES,
    },
    clock: { instant: DEMO_INSTANT, ms: DEMO_MS },
    seats: SEATS,
    staff,
    members: staff.map((s) => ({ user_id: s.user_id, display_name: s.display_name })),
    clients,
    clientIds,
    firmClients: clients.map((c) => ({ client_id: clientIds[c.slug] ?? "", name: c.name })),
    engagements,
    summaries: engagements.map(summaryOf),
    engagementIds: ids,
    workItems,
    requestItems,
    requestOwners,
    portalUsers: PORTAL_USERS,
    thirdParties: THIRD_PARTIES,
    contacts,
    walls,
    people,
    figures: { northwind: NORTHWIND_FIGURES },
  };
}

let memo: Seed | undefined;

/** The default seed (E0, no holdout), built once. Treat it as read-only. */
export function getSeed(): Seed {
  memo ??= buildSeed();
  return memo;
}

/** The `GET /v1/me` body for a persona slug (`?as=`), or undefined when nobody has that slug. */
export function meFor(seed: Seed, slug: string): MeOut | undefined {
  const person = seed.people.find((p) => p.slug === slug);
  if (person === undefined) return undefined;
  const seat = seed.seats.find((s) => slugOf(s.name) === slug);
  const initials = seat?.initials;
  return {
    user_id: person.userId,
    email: person.email,
    display_name: person.name,
    active_tenant_id: seed.firm.id,
    server_now: DEMO_INSTANT,
    clock_mode: "offset",
    memberships: [
      {
        tenant_id: seed.firm.id,
        firm_name: seed.firm.shortName,
        firm_role: initials === undefined ? null : (FIRM_ROLES[initials] ?? null),
        kind: person.kind,
      },
    ],
  };
}
