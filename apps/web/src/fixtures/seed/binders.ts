// The Brightwater Hale binder slice as BND-01 reads it (P-06-T09, ahead of P-06-T08's Python slice):
// the TY2025 tax-return binders at E0, Mon Sep 14, 2026, 9:24 AM CT. The 15 named rows are spec.md
// ROWS 1–15 verbatim (BND-01a, newest client activity within each state); Benjamin Osterberg's
// binder is the c artboard's row (Unpublished Sep 2 by Remy Vidal, "fixing 2 requests", 0 of 9, RV,
// from the BND-01c screenshot). The tiles and the summary are the §9.5 figures: 1 + 48 + 0 + 40 +
// 152 = 241 binders, 224 returns + 17 second-part binders. The other 226 binders are not named in
// the handoff, so the slice carries only their counts; P-06-T08 replaces this file with the exported
// scenario (`make fixtures`, F-04-T31).
//
// Every body is typed against the generated client (`BinderRowOut`). Times without a clock in the
// handoff stand at noon CT; only the date is ever shown.

import type { BinderRowOut, BinderStatus, Facet } from "@abacus/api-client";
import type { Seed } from "./index";
import { type OfficeName, SEATS, slugOf } from "./people";
import { stableId } from "./prng";

/** The demo season and service (BND-01a's two amber chips). */
export const BINDER_SEASON = "TY2025";
export const BINDER_SERVICE = "tax_returns";
/** The season before season setup has run (BND-01d). */
export const EMPTY_SEASON = "TY2026";

/** §9.5 "binders 241": the tiles at E0 (BND-01a). */
export const BINDER_COUNTS: Readonly<Record<BinderStatus, number>> = {
  draft: 1,
  published: 48,
  unpublished: 0,
  complete: 40,
  closed: 152,
};

/** "224 returns · 17 second-part binders". */
export const BINDER_PARTS = { returns: 224, secondParts: 17 } as const;

interface Row {
  name: string;
  client: string;
  workItem: string;
  done: number;
  total: number;
  status: BinderStatus;
  /** Last client activity, ISO 8601 UTC, or null ("—"). */
  activity: string | null;
  /** The preparer's initials (a seat holder). */
  prep: string;
  part?: number;
}

/** Noon CT (CDT) on a calendar day. */
const noon = (day: string): string => `${day}T17:00:00.000Z`;

/** spec.md ROWS 1–15, in the screen's order. */
export const BINDER_ROWS: readonly Row[] = [
  {
    name: "2025 Binder",
    client: "Jonah & Claire Feld",
    workItem: "2025 Form 1040",
    done: 5,
    total: 7,
    status: "published",
    activity: "2026-09-14T14:12:00.000Z", // 9:12 AM CT
    prep: "KO",
  },
  {
    name: "2025 Binder",
    client: "Ridgeline Property Partners, LP",
    workItem: "2025 Form 1065",
    done: 21,
    total: 21,
    status: "complete",
    activity: noon("2026-06-01"),
    prep: "OB",
  },
  {
    name: "2025 Binder pt 2",
    client: "Ridgeline Property Partners, LP",
    workItem: "2025 Form 1065",
    done: 1,
    total: 3,
    status: "published",
    activity: noon("2026-09-11"),
    prep: "OB",
    part: 2,
  },
  {
    name: "2025 Binder",
    client: "Meera Shah",
    workItem: "2025 Form 1040",
    done: 15,
    total: 17,
    status: "published",
    activity: noon("2026-09-09"),
    prep: "LP",
  },
  {
    name: "2025 Binder",
    client: "Calloway Family Trust",
    workItem: "2025 Form 1041",
    done: 9,
    total: 9,
    status: "complete",
    activity: noon("2026-09-09"),
    prep: "KO",
  },
  {
    name: "2025 Binder",
    client: "Harborview Dental Properties, LP",
    workItem: "2025 Form 1065",
    done: 18,
    total: 18,
    status: "complete",
    activity: noon("2026-08-28"),
    prep: "DS",
  },
  {
    name: "2025 Binder",
    client: "Elena Varga",
    workItem: "2025 Form 1040",
    done: 8,
    total: 8,
    status: "complete",
    activity: noon("2026-08-30"),
    prep: "LP",
  },
  {
    name: "2025 Binder",
    client: "Estate of Walter Thornbury",
    workItem: "2025 Form 1040",
    done: 6,
    total: 15,
    status: "published",
    activity: noon("2026-09-09"),
    prep: "BN",
  },
  {
    name: "2025 Binder",
    client: "Gloria Mendez",
    workItem: "2025 Form 1040",
    done: 4,
    total: 11,
    status: "published",
    activity: noon("2026-09-13"), // "Yesterday"
    prep: "NK",
  },
  {
    name: "2025 Binder",
    client: "Morgan & Kai Ferris",
    workItem: "2025 Form 1040",
    done: 2,
    total: 12,
    status: "published",
    activity: noon("2026-09-09"),
    prep: "DS",
  },
  {
    name: "2025 Binder",
    client: "Rafael Quintero",
    workItem: "2025 Form 1040",
    done: 0,
    total: 10,
    status: "draft",
    activity: null,
    prep: "LW",
  },
  {
    name: "2025 Binder",
    client: "Lakeshore Literacy Alliance",
    workItem: "2025 Form 990 (FYE Jun 30, 2026)",
    done: 7,
    total: 16,
    status: "published",
    activity: noon("2026-09-10"),
    prep: "BN",
  },
  {
    name: "2025 Binder",
    client: "Fenwick Family Foundation",
    workItem: "2025 Form 990-PF",
    done: 5,
    total: 14,
    status: "published",
    activity: noon("2026-08-11"),
    prep: "BN",
  },
  {
    name: "2025 Binder",
    client: "Marcus & Dana Whitley",
    workItem: "2025 Form 1040",
    done: 14,
    total: 14,
    status: "closed",
    activity: noon("2026-04-02"),
    prep: "KO",
  },
  {
    name: "2025 Binder",
    client: "Copperleaf Coffee Roasters, Inc.",
    workItem: "2025 Form 1120-S",
    done: 12,
    total: 12,
    status: "closed",
    activity: noon("2026-03-06"),
    prep: "LW",
  },
];

/** BND-01c: Remy Vidal pulled Benjamin Osterberg's binder back on Sep 2 to fix 2 requests. */
export const OSTERBERG_ROW: Row = {
  name: "2025 Binder",
  client: "Benjamin Osterberg",
  workItem: "2025 Form 1040",
  done: 0,
  total: 9,
  status: "unpublished",
  activity: null,
  prep: "RV",
};
export const OSTERBERG_UNPUBLISH = {
  at: noon("2026-09-02"),
  by: "Remy Vidal",
  reason: "fixing 2 requests",
} as const;

/** What a firm person may do on a TY2025 binder in the fixture. Assumes Brightwater Hale's
 * `client_service_can_publish` is on (the BND-01 canvas has Grace publish and unpublish from the
 * row menu); P-06-T08's firm settings own the real value. */
export const BINDER_ACTIONS = ["binder.read", "binder.publish", "binder.create"] as const;

function userIdOf(initials: string): string | null {
  const seat = SEATS.find((s) => s.initials === initials);
  return seat === undefined ? null : stableId(`user:${slugOf(seat.name)}`);
}

function slugOfClient(seed: Seed, name: string): string {
  return seed.clients.find((c) => c.name === name)?.slug ?? slugOf(name);
}

/** The client's office, for the Office chip; null for a client outside the seed. */
export function officeOfClient(seed: Seed, name: string): OfficeName | null {
  return seed.clients.find((c) => c.name === name)?.office ?? null;
}

export function toBinderRow(seed: Seed, row: Row): BinderRowOut {
  const slug = slugOfClient(seed, row.client);
  const part = row.part ?? 1;
  const unpublished =
    row.status === "unpublished"
      ? {
          unpublished_at: OSTERBERG_UNPUBLISH.at,
          unpublished_by: stableId(`user:${slugOf(OSTERBERG_UNPUBLISH.by)}`),
          unpublish_reason: OSTERBERG_UNPUBLISH.reason,
        }
      : { unpublished_at: null, unpublished_by: null, unpublish_reason: null };
  return {
    id: stableId(`binder:${slug}:TY2025:${String(part)}`),
    engagement_id:
      row.client === "Jonah & Claire Feld"
        ? (seed.engagementIds.feld ?? stableId(`engagement:tax:${slug}:2025`))
        : stableId(`engagement:tax:${slug}:2025`),
    work_item_id: stableId(`work-item:${slug}:${row.workItem}`),
    client_name: row.client,
    work_item_label: row.workItem,
    name: row.name,
    kind: "organizer",
    part,
    status: row.status,
    preparer_user_id: userIdOf(row.prep),
    done_count: row.done,
    total_count: row.total,
    last_client_activity_at: row.activity,
    ...unpublished,
    tags: [],
    allowed_actions: [...BINDER_ACTIONS],
  };
}

/** The facets the chips read (`facets` of the list envelope). */
export function binderFacets(seed: Seed, rows: readonly BinderRowOut[]): Record<string, Facet[]> {
  const preparers = new Map<string, number>();
  for (const r of rows) {
    if (r.preparer_user_id !== null) {
      preparers.set(r.preparer_user_id, (preparers.get(r.preparer_user_id) ?? 0) + 1);
    }
  }
  const offices = new Map<string, number>();
  for (const r of rows) {
    const office = officeOfClient(seed, r.client_name);
    if (office !== null) offices.set(office, (offices.get(office) ?? 0) + 1);
  }
  return {
    service: [{ value: BINDER_SERVICE, label: "Tax returns", n: rows.length }],
    season: [
      { value: BINDER_SEASON, label: BINDER_SEASON, n: rows.length },
      { value: EMPTY_SEASON, label: EMPTY_SEASON, n: 0 },
    ],
    office: seed.firm.offices.map((o) => ({
      value: stableId(`office:${o.name}`),
      label: o.name,
      n: offices.get(o.name) ?? 0,
    })),
    preparer: [...preparers.entries()].map(([id, n]) => ({
      value: id,
      label: seed.staff.find((s) => s.user_id === id)?.display_name ?? id,
      n,
    })),
    client_activity: [
      { value: "any", label: "Any", n: rows.length },
      { value: "none_30_days", label: "None in 30 days", n: 0 },
    ],
  };
}
