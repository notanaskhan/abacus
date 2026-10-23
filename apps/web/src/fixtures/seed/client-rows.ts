// CLI-01's row facts for the 184 clients (P-07-T11; docs/screens/CLI-01.md): the descriptor, the
// read model's `kind`, the open requests and the last activity of the 16 named clients (CLI-01
// spec ROWS 1-16, blueprint 01 §9.3), and a deterministic older activity for the 168 others, so
// the 16 named clients are the first page, newest first. The figures that the seed's own request
// lists carry (Northwind 13 = 24 − 11, Feld 2, Granite Peak "Binder draft") are computed from
// them in fixtures/handlers/clients.ts, never restated here.

import type { ClientRowOut } from "@abacus/api-client";
import type { SeedClient } from "./clients";
import { DEMO_MS, daysBefore } from "./clock";

type ApiKind = NonNullable<ClientRowOut["kind"]>;

export interface NamedRowFacts {
  descriptor: string;
  /** Overrides the kind the seed's own kind maps to (Northwind is a plan sponsor on CLI-01). */
  kind?: ApiKind;
  /** Open requests the seed holds no request list for (requested + uploaded + returned). */
  openRequests?: number;
  /** Minutes before the demo instant of the client's latest activity. */
  minutesAgo: number;
  /** The audit event type of that activity (docs/contracts/clients.md). */
  eventType: string | null;
}

const HOUR = 60;
const DAY = 24 * HOUR;
/** Minutes from the demo instant (Mon Sep 14, 9:24 AM CT) back to `h:mm` on Sep `day`, CT. */
function at(day: number, hour: number, minute: number): number {
  return (14 - day) * DAY + (9 * HOUR + 24) - (hour * HOUR + minute);
}

/** Copperleaf's August close: 9 requests, 7 received (blueprint 01 §9.4). Its 3 open transaction
 * questions are not requests. */
export const COPPERLEAF_CLOSE = { requests: 9, received: 7 } as const;

/** By client name, in CLI-01 order (spec ROWS 1-16). */
export const NAMED_ROW_FACTS: Readonly<Record<string, NamedRowFacts>> = {
  "Jonah & Claire Feld": {
    descriptor: "Brooklyn, NY · MFJ",
    minutesAgo: at(14, 9, 12),
    eventType: "evidence.uploaded",
  },
  "Copperleaf Coffee Roasters, Inc.": {
    descriptor: "Denver, CO · café + online store",
    openRequests: COPPERLEAF_CLOSE.requests - COPPERLEAF_CLOSE.received,
    minutesAgo: at(14, 9, 2),
    eventType: "request_item.received",
  },
  "Meera Shah": {
    descriptor: "Chicago, IL · Schedule C consulting",
    openRequests: 1,
    minutesAgo: at(14, 8, 55),
    eventType: "evidence.uploaded",
  },
  "Northwind Robotics, Inc.": {
    descriptor: "Plan sponsor · Northwind Robotics 401(k) Plan",
    kind: "plan_sponsor",
    minutesAgo: at(14, 8, 47),
    eventType: "evidence.uploaded",
  },
  "Ridgeline Property Partners, LP": {
    descriptor: "Real estate · Chicago, Denver, Brooklyn",
    // Its five waiting-on-client issues (TXP-10).
    openRequests: 5,
    minutesAgo: at(14, 8, 40),
    eventType: null,
  },
  "Granite Peak Outdoor Supply, Inc.": {
    descriptor: "Denver, CO · FYE 6/30",
    minutesAgo: at(12, 10, 5),
    eventType: "engagement.letter_recorded",
  },
  "Harborview Dental Properties, LP": {
    descriptor: "New York · three dental office buildings",
    minutesAgo: at(11, 16, 40),
    eventType: null,
  },
  "Marcus & Dana Whitley": {
    descriptor: "Denver, CO · MFJ",
    minutesAgo: at(11, 15, 10),
    eventType: "evidence.uploaded",
  },
  "Estate of Walter Thornbury": {
    descriptor: "Chicago, IL · date of death 2/2/2026",
    openRequests: 1,
    minutesAgo: at(11, 14, 20),
    eventType: "engagement.created",
  },
  "Bluestem Analytics, LLC": {
    descriptor: "New York · SaaS · S election",
    minutesAgo: at(11, 11, 30),
    eventType: null,
  },
  "Lakeshore Literacy Alliance": {
    descriptor: "Chicago, IL · 501(c)(3) · FYE 6/30",
    openRequests: 4,
    minutesAgo: at(10, 15, 45),
    eventType: "evidence.uploaded",
  },
  "Elena Varga": {
    descriptor: "Chicago, IL",
    minutesAgo: at(10, 10, 15),
    eventType: null,
  },
  "Calloway Family Trust": {
    descriptor: "Illinois · complex trust",
    minutesAgo: at(9, 16, 5),
    eventType: "evidence.uploaded",
  },
  "Ashford Manufacturing Co.": {
    descriptor: "Chicago, IL · ASC 740 provision",
    openRequests: 2,
    minutesAgo: at(9, 11, 50),
    eventType: "evidence.uploaded",
  },
  "Juniper & Oak Interiors, LLC": {
    descriptor: "Denver, CO · retail",
    minutesAgo: at(4, 13, 0),
    eventType: "engagement.delivered",
  },
  "Daniel & Ruth Okafor": {
    descriptor: "Evanston, IL · Schedule E rentals",
    // Apr 13, 2026: 154 days before Sep 14.
    minutesAgo: 154 * DAY + 3 * HOUR,
    eventType: "engagement.delivered",
  },
};

/** DEC-62: a client's display name is its own field and never follows an entity. The interim
 * seed (and the Python golden file it matches) still names this client by its estate entity; the
 * clients read model shows the client's own name. */
export const CLIENT_DISPLAY_NAME: Readonly<Record<string, string>> = {
  "Estate of Walter Thornbury": "Walter Thornbury",
};

/** The read model's `kind` for a seed client (DEC-62: households and individuals are clients). */
export function apiKindOf(client: SeedClient): ApiKind {
  const named = NAMED_ROW_FACTS[client.name]?.kind;
  if (named !== undefined) return named;
  switch (client.kind) {
    case "individual":
    case "household":
      return "household";
    case "business":
    case "partnership":
      return "business";
    case "exempt_org":
      return "nonprofit";
    case "trust":
    case "estate":
      return "trust_family";
    case "plan":
      return "plan_sponsor";
  }
}

/** The client's latest activity, as an ISO instant: the named clients' from the spec rows; every
 * other client older than Okafor's, one day apart in seed order, at a fixed hour. */
export function lastActivityOf(client: SeedClient, index: number): string {
  const named = NAMED_ROW_FACTS[client.name];
  if (named !== undefined) return new Date(DEMO_MS - named.minutesAgo * 60_000).toISOString();
  return daysBefore(160 + index);
}

/** The descriptor (the row's sub-line) of a named client; null for the others. */
export function descriptorOf(client: SeedClient): string | null {
  return NAMED_ROW_FACTS[client.name]?.descriptor ?? null;
}
