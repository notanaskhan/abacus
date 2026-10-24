// BND-02 binder builder and tracker: one fixture scenario per artboard P-06-T12 builds (a–f; g and
// the R2 rows are P-06-T22's). All six stand at E0, Mon Sep 14, 2026, 9:24 AM CT, seen by Kevin
// Osei, the Feld preparer (DV-4: e's README viewer is a client; this is a firm screen). Data:
// fixtures/seed/binder-detail.ts. The binder record, rows and preview routes are P-06-T07's; the
// live poll, uploads and the row writes answer here in the C5 shapes until P-06-T10 lands.
//
// Each artboard also names the binder it opens and the request its dock shows:
//   a  Feld, published, 5 of 7, 1095-C "Waiting 2", estimates "Uploading 2 files…"; K-1 selected
//   b  Feld TY2026 roll-forward Draft, 7 "Not published"; K-1 selected
//   c  Feld complete, marked done by Claire Feld Sep 15, 9:02 AM, 7 of 7; 1095-C selected
//   d  Thornbury, 6 of 15, 3 past Aug 31; the Lakeview 1099-R selected
//   e  Thornbury with Paul Thornbury's Ignore on the IRA confirmations (selected)
//   f  Feld with the K-1 hidden from the client (selected)
//
// They live under fixtures/ (dev and test only); src/screens/BND-02/scenarios.ts re-exports them.

import type {
  ListPageActivityEventOut,
  ListPageBinderRequestRowOut,
  RequestItemDeletedOut,
  WaiveIn,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { type FollowUpSpec, followUpHandlers } from "../handlers/follow-ups";
import { type BinderFixture, binderSet } from "../seed/binder-detail";
import { stableId } from "../seed/prng";

const E0 = seedScenario();
const seed = getSeed();

const feldEngagementId = seed.engagementIds.feld ?? "";
const feldWorkItemId = seed.workItems[feldEngagementId]?.[0]?.id ?? "";
export const BINDERS = binderSet(feldEngagementId, feldWorkItemId);

const NOT_FOUND = { detail: "not found" };

/** The row the dock opens on, by the canvas's key. */
function rowId(fixture: BinderFixture, key: string): string {
  const found = Object.entries(fixture.keys).find(([, k]) => k === key);
  if (found === undefined) throw new Error(`no request ${key}`);
  return found[0];
}

// BND-04 c's Paul Thornbury card, verbatim (DEC-221): the Request Chaser's draft for the
// Thornbury binder's open requests. The Feld binders have no designed draft, so they draft none.
const THORNBURY_DRAFT =
  "Hi Paul, thank you for what you have sent so far. 9 items are still open for 2025 Form 1040, " +
  "3 of them past the due date. You can upload them in the portal. Bianca Novak is your contact " +
  "at Brightwater Hale.";

function followUpsOf(data: () => BinderFixture, thorn: boolean): Record<string, FixtureHandler> {
  const kevin = seed.people.find((p) => p.slug === "kevin-osei")?.userId ?? "";
  return followUpHandlers(
    (asked): FollowUpSpec[] => {
      if (!thorn) return [];
      const { binder, rows } = data();
      const ids = new Set(asked.request_item_ids ?? []);
      const items = rows
        .filter(
          (r) =>
            ids.has(r.id) &&
            (r.status === "requested" || r.status === "returned") &&
            r.client_visible,
        )
        .map((r) => ({ id: r.id, title: r.title, due_on: r.due_on ?? null, overdue: r.overdue }));
      return [
        {
          engagementId: binder.engagement_id,
          binderId: binder.id,
          recipientUserId: stableId("contact:Paul Thornbury"),
          recipientName: "Paul Thornbury",
          body: THORNBURY_DRAFT,
          items,
        },
      ];
    },
    () => kevin,
  );
}

function page<T>(items: T[]): { items: T[]; next_cursor: null; total: number } {
  return { items, next_cursor: null, total: items.length };
}

/** The scenario's handlers over one binder. Writes change this scenario's own copy. */
function handlers(start: BinderFixture): Record<string, FixtureHandler> {
  let data: BinderFixture = structuredClone(start);
  const mine = (request: FixtureRequest): boolean => request.params.binder_id === data.binder.id;
  const item = (request: FixtureRequest) => data.rows.find((r) => r.id === request.params.item_id);
  const patchRow = (id: string, patch: Partial<BinderFixture["rows"][number]>): void => {
    data = { ...data, rows: data.rows.map((r) => (r.id === id ? { ...r, ...patch } : r)) };
  };
  const thorn = data.binder.engagement_id === BINDERS.thornburyEngagement.id;
  const draft = data.binder.work_item_id === BINDERS.feldDraftWorkItem.id;
  return {
    ...E0.handlers,
    ...followUpsOf(() => data, thorn),
    "GET /v1/binders/{binder_id}": (r) => (mine(r) ? json(data.binder) : json(NOT_FOUND, 404)),
    "GET /v1/binders/{binder_id}/requests": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      const body: ListPageBinderRequestRowOut = page(data.rows);
      return json(body);
    },
    "GET /v1/binders/{binder_id}/live": (r) => (mine(r) ? json(data.live) : json(NOT_FOUND, 404)),
    "GET /v1/binders/{binder_id}/client-preview": (r) =>
      mine(r) ? json(data.preview) : json(NOT_FOUND, 404),
    "GET /v1/binders/{binder_id}/activity": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      const body: ListPageActivityEventOut = page(data.activity);
      return json(body);
    },
    "POST /v1/binders/{binder_id}/publish": () => {
      data = { ...data, binder: { ...data.binder, status: "published" } };
      return json(data.binder);
    },
    "POST /v1/binders/{binder_id}/publish/undo": () => {
      data = { ...data, binder: { ...data.binder, status: start.binder.status } };
      return json(data.binder);
    },
    "POST /v1/binders/{binder_id}/unpublish": ({ body }) => {
      const reason = (body as { reason?: string } | null)?.reason ?? "";
      if (reason.trim() === "") return json({ detail: "reason_required" }, 422);
      data = {
        ...data,
        binder: {
          ...data.binder,
          status: "unpublished",
          unpublish_reason: reason,
          unpublished_at: "2026-09-14T14:24:00.000Z",
        },
      };
      return json(data.binder);
    },
    ...(thorn
      ? {
          "GET /v1/engagements/{engagement_id}": () => json(BINDERS.thornburyEngagement),
          "GET /v1/engagements/{engagement_id}/work-items": () => json(BINDERS.thornburyWorkItems),
        }
      : {}),
    ...(draft
      ? {
          "GET /v1/engagements/{engagement_id}/work-items": () =>
            json([...(seed.workItems[feldEngagementId] ?? []), BINDERS.feldDraftWorkItem]),
        }
      : {}),
    "GET /v1/engagements/{engagement_id}/request-items/{item_id}/uploads": (r) =>
      json(data.uploads[r.params.item_id ?? ""] ?? []),
    "GET /v1/engagements/{engagement_id}/request-items/{item_id}/activity": (r) =>
      json(page(data.requestActivity[r.params.item_id ?? ""] ?? [])),
    "PUT /v1/engagements/{engagement_id}/request-items/{item_id}/client-visibility": (r) => {
      const row = item(r);
      if (row === undefined) return json(NOT_FOUND, 404);
      const visible = (r.body as { client_visible?: boolean } | null)?.client_visible === true;
      patchRow(row.id, { client_visible: visible });
      return json({ id: row.id, client_visible: visible });
    },
    "POST /v1/engagements/{engagement_id}/request-items/{item_id}/waive": (r) => {
      const row = item(r);
      const body = r.body as Partial<WaiveIn> | null;
      if (row === undefined) return json(NOT_FOUND, 404);
      if (body?.na_reason === undefined || (body.note ?? "").trim() === "") {
        return json({ detail: "reason_required" }, 422);
      }
      patchRow(row.id, { status: "not_applicable", overdue: false });
      return json({ id: row.id, status: "not_applicable" });
    },
    "POST /v1/engagements/{engagement_id}/request-items/{item_id}/return-to-client": (r) => {
      const row = item(r);
      if (row === undefined) return json(NOT_FOUND, 404);
      patchRow(row.id, {
        status: "requested",
        client_ignored_at: null,
        client_ignore_reason: null,
      });
      return json({ id: row.id, status: "requested" });
    },
    "DELETE /v1/engagements/{engagement_id}/request-items/{item_id}": (r) => {
      const row = item(r);
      if (row === undefined) return json(NOT_FOUND, 404);
      if (row.status !== "draft") return json({ detail: "request_already_sent" }, 409);
      data = { ...data, rows: data.rows.filter((x) => x.id !== row.id) };
      const body: RequestItemDeletedOut = {
        request_item_id: row.id,
        deleted_at: "2026-09-14T14:24:00.000Z",
      };
      return json(body);
    },
  };
}

const at = (state: string, fixture: BinderFixture): Scenario => ({
  state,
  persona: "kevin-osei",
  clock: E0.clock ?? "2026-09-14T09:24:00-05:00",
  handlers: handlers(fixture),
});

export const scenarios = defineScenarios({
  a: at("a", BINDERS.feld),
  b: at("b", BINDERS.feldDraft),
  c: at("c", BINDERS.feldDone),
  d: at("d", BINDERS.thornbury),
  e: at("e", BINDERS.thornburyIgnored),
  f: at("f", BINDERS.feldHidden),
});

export type Bnd02State = keyof typeof scenarios;

/** What each artboard opens: the binder and the request in the dock. */
export const OPENS: Readonly<Record<Bnd02State, { binderId: string; request: string }>> = {
  a: { binderId: BINDERS.feld.binder.id, request: rowId(BINDERS.feld, "k1") },
  b: { binderId: BINDERS.feldDraft.binder.id, request: rowId(BINDERS.feldDraft, "k1") },
  c: { binderId: BINDERS.feldDone.binder.id, request: rowId(BINDERS.feldDone, "aca") },
  d: { binderId: BINDERS.thornbury.binder.id, request: rowId(BINDERS.thornbury, "t4") },
  e: {
    binderId: BINDERS.thornburyIgnored.binder.id,
    request: rowId(BINDERS.thornburyIgnored, "t12"),
  },
  f: { binderId: BINDERS.feldHidden.binder.id, request: rowId(BINDERS.feldHidden, "k1") },
};
