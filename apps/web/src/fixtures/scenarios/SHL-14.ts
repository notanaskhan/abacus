// SHL-14 Request composer drawer: one fixture scenario per state P-06-T13 and P-06-T24 build
// (docs/screens/SHL-14.md). a, b and e stand at Mon Sep 14, 2026, 9:41 AM CT, seen by Marcus
// Delaney (revision R2 wins over the README's Sep 24); f at Thu Sep 24, 2026, 10:58 AM CT, seen
// by Cole Hart. The binders are built from the seed's own request lists, so the counts foot
// (Northwind 11 of 24 received; a new request makes it 11 of 25):
//
//   a  `?ov=request:new` on the Northwind PY2025 binder, due from the binder default (Sep 21)
//   b  the existing "Bridge letter — Keystone, Oct–Dec 2025", requested Sep 1, due Sep 25
//   c  (A-03-T15) a with the Sample wave on: Northwind's approved Participants sample (25), one
//      request to Dana Kowalski per participant, "Create 25 requests"
//   e  a on a binder with no default due date: nothing to send without one
//   f  the Granite Peak FY2026 SURL Draft, drafted by the agent, assigned to Luis Ferrante
//   d  (P-06-T24) Raj Malhotra on Copperleaf's August `close_intake` binder: "Square payouts —
//      August", received Sep 3 and `pending_incorporation`, with Ben Ashby's upload
//
// d's binder is the backend seed's own (`abacus_tools/synthetic/scenarios/brightwater_hale/
// binders.py`, P-06-T08): "Requests", 8 recurring + 1 ad hoc = 9 requests, 7 received, in the
// seed's five categories, with the seed's ids. c is A-03-T15's (the sampling fan-out). They live under
// fixtures/ (dev and test only); screens/SHL-14/scenarios.ts re-exports them.

import type {
  ActivityEventOut,
  BinderClientPreviewOut,
  BinderOut,
  BinderRequestRowOut,
  DecisionOut,
  ListPageActivityEventOut,
  ListPageBinderRequestRowOut,
  RequestItemIn,
  RequestItemOut,
  RequestItemPatchIn,
  RequestItemV2Out,
  RequestStatus,
  UploadOut,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { generateHandlers, samplingHandlers } from "../handlers/sampling";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { stableId } from "../seed/prng";
import { northwindParticipants, northwindSampleSets } from "../seed/sampling";
import { SEND_BACK_REASONS } from "../seed/screening";

const E0 = seedScenario();
const seed = getSeed();

/** Mon Sep 14, 2026, 9:41 AM CT (revision R2, states 1–5). */
export const CLOCK_A = "2026-09-14T09:41:00-05:00";
/** Thu Sep 24, 2026, 10:58 AM CT (revision R2, state 6). */
export const CLOCK_F = "2026-09-24T10:58:00-05:00";

const NORTHWIND = seed.engagementIds.A1 ?? "";
const GRANITE_PEAK = seed.engagementIds.A2 ?? "";
const NOT_FOUND = { detail: "not found" };

export const NORTHWIND_BINDER = stableId("binder:northwind:py2025-pbc");
export const NORTHWIND_NO_DEFAULT = stableId("binder:northwind:py2025-pbc-no-default");
export const GRANITE_BINDER = stableId("binder:granite-peak:fy2026-pbc");

const BRIDGE_TITLE = "Bridge letter — Keystone, Oct–Dec 2025";
const BRIDGE_WORDING =
  "Keystone's SOC 1 Type 2 report covers Oct 1, 2024 – Sep 30, 2025. Please provide a bridge letter stating whether controls relevant to recordkeeping changed between Oct 1 and Dec 31, 2025.";
const SURL_TITLE = "Support for 40 subsequent disbursements (SURL)";

function contactIdOf(engagementId: string, name: string): string | null {
  return seed.contacts[engagementId]?.find((c) => c.display_name === name)?.id ?? null;
}

interface ComposerData {
  binder: BinderOut;
  rows: BinderRequestRowOut[];
  items: RequestItemOut[];
  preview: BinderClientPreviewOut;
  activity: Record<string, ActivityEventOut[]>;
  /** A request's files (`GET …/uploads`); none unless the state draws one. */
  uploads?: Record<string, UploadOut[]>;
}

function categoryId(binderId: string, name: string): string {
  return stableId(`request-category:${binderId}:${name}`);
}

function binderOf(
  id: string,
  engagementId: string,
  name: string,
  items: readonly RequestItemOut[],
  defaultDue: string | null,
): BinderOut {
  const names = [...new Set(items.map((i) => i.audit_area))];
  const done = (i: RequestItemOut): boolean => i.status === "received";
  return {
    id,
    engagement_id: engagementId,
    work_item_id: seed.workItems[engagementId]?.[0]?.id ?? null,
    kind: "pbc",
    name,
    part: 1,
    status: "published",
    created_from: "template",
    default_due_on: defaultDue,
    categories: names.map((n, position) => {
      const mine = items.filter((i) => i.audit_area === n);
      return {
        id: categoryId(id, n),
        name: n,
        position,
        total_count: mine.length,
        done_count: mine.filter(done).length,
      };
    }),
    done_count: items.filter(done).length,
    total_count: items.length,
    follow_up_override: { every_days: 3, max: 4 },
    allowed_actions: ["binder.read", "binder.update"],
  };
}

function rowOf(binderId: string, i: RequestItemOut): BinderRequestRowOut {
  return {
    id: i.id,
    category_id: categoryId(binderId, i.audit_area),
    title: i.description === BRIDGE_WORDING ? BRIDGE_TITLE : i.description,
    status: i.status,
    overdue: false,
    client_visible: i.client_visible ?? true,
    kind: "client_upload",
    due_on: i.due_on ?? null,
    requested_at: i.status === "draft" ? null : "2026-09-01T15:00:00Z",
    allowed_actions: ["request_item.update", "request_item.send", "request_item.delegate"],
  };
}

function northwind(binderId: string, defaultDue: string | null): ComposerData {
  const items = (seed.requestItems[NORTHWIND] ?? []).map((i) =>
    // b: the bridge letter is Dana Kowalski's request, delegated to Sam Ortiz (Keystone).
    i.description === BRIDGE_TITLE
      ? {
          ...i,
          description: BRIDGE_WORDING,
          client_assignee_user_id: contactIdOf(NORTHWIND, "Dana Kowalski"),
        }
      : i,
  );
  const binder = binderOf(binderId, NORTHWIND, "Northwind · PY2025", items, defaultDue);
  const rows = items.map((i) => rowOf(binderId, i));
  const bridge = rows.find((r) => r.title === BRIDGE_TITLE);
  return {
    binder,
    rows,
    items,
    preview: {
      binder_id: binderId,
      name: binder.name,
      status: binder.status,
      items:
        bridge === undefined
          ? []
          : [
              {
                id: bridge.id,
                category_name: "Form 5500 & SOC 1",
                title: BRIDGE_TITLE,
                description: BRIDGE_WORDING,
                status: bridge.status,
                client_ignored: false,
                due_on: bridge.due_on ?? null,
              },
            ],
    },
    activity: {},
  };
}

function granitePeak(): ComposerData {
  const luis = contactIdOf(GRANITE_PEAK, "Luis Ferrante");
  const surl: RequestItemOut = {
    id: stableId("request:granite-peak:surl"),
    engagement_id: GRANITE_PEAK,
    audit_area: "Payables & accrued",
    description: SURL_TITLE,
    status: "draft",
    created_at: "2026-09-24T15:40:00Z",
    due_on: "2026-10-02",
    client_visible: false,
    client_assignee_user_id: luis,
  };
  const items = [...(seed.requestItems[GRANITE_PEAK] ?? []), surl];
  const binder = binderOf(GRANITE_BINDER, GRANITE_PEAK, "Granite Peak · FY2026", items, null);
  const rows = items.map((i) => rowOf(GRANITE_BINDER, i));
  const drafted: ActivityEventOut = {
    id: stableId("event:drafted:granite-peak:surl"),
    event_type: "request_item.drafted",
    at: "2026-09-24T15:40:00Z",
    actor_kind: "agent",
    actor_user_id: null,
    via_agent: true,
    target_type: "request_item",
    target_id: surl.id,
  };
  return {
    binder,
    rows,
    items,
    preview: { binder_id: GRANITE_BINDER, name: binder.name, status: binder.status, items: [] },
    activity: { [surl.id]: [drafted] },
  };
}

// ---- d: Copperleaf's August close intake (P-06-T24) ---------------------------------------------

const CLOSE_LABEL = "close:copperleaf-2026-08";
export const COPPERLEAF_CLOSE = stableId("engagement:copperleaf:2026-close");
export const COPPERLEAF_BINDER = stableId(`binder:${CLOSE_LABEL}`);
const RAJ_MALHOTRA = stableId("user:raj-malhotra");
const BANK = "Bank & Cash Accounts";
const CLOSE_CATEGORIES = [
  BANK,
  "Revenue",
  "Payroll",
  "Loans & Payables",
  "Questions from review",
] as const;
const SQUARE_TITLE = "Square payouts — August";
/** The file CLS-03 and POR-11 name; uploaded by Ben Ashby, Sep 3, 2026. */
export const SQUARE_FILE = "square-2026-08-01_2026-08-31-payouts.xlsx";

type Incorporation = NonNullable<BinderRequestRowOut["incorporation_state"]>;
interface CloseRequest {
  category: (typeof CLOSE_CATEGORIES)[number];
  title: string;
  status: RequestStatus;
  requested: string;
  due: string | null;
  incorporation?: Incorporation;
}

// The seed's CLOSE_REQUESTS, in order (8 recurring from close plan v3 + 1 ad hoc; 7 received).
const CLOSE_REQUESTS: readonly CloseRequest[] = [
  {
    category: BANK,
    title: SQUARE_TITLE,
    status: "received",
    requested: "2026-09-01",
    due: "2026-09-03",
    incorporation: "pending_incorporation",
  },
  {
    category: BANK,
    title: "Shopify payouts — August",
    status: "received",
    requested: "2026-09-01",
    due: null,
    incorporation: "incorporated",
  },
  {
    category: BANK,
    title: "Front Range Bank statement — August (Savings ••4436)",
    status: "requested",
    requested: "2026-09-01",
    due: "2026-09-05",
  },
  {
    category: BANK,
    title: "Amex ••1009 statement — cycle ending Aug 22",
    status: "received",
    requested: "2026-09-01",
    due: null,
    incorporation: "incorporated",
  },
  {
    category: "Revenue",
    title: "Subscription billing report — August",
    status: "received",
    requested: "2026-09-01",
    due: null,
    incorporation: "incorporated",
  },
  {
    category: "Payroll",
    title: "Payroll register — August (pay dates Aug 3, 17, 31)",
    status: "received",
    requested: "2026-09-01",
    due: null,
    incorporation: "incorporated",
  },
  {
    category: "Loans & Payables",
    title: "Equipment loan statement — August",
    status: "received",
    requested: "2026-09-01",
    due: null,
    incorporation: "incorporated",
  },
  {
    category: "Loans & Payables",
    title: "AP aging — Aug 31",
    status: "received",
    requested: "2026-09-01",
    due: null,
    incorporation: "incorporated",
  },
  {
    category: "Questions from review",
    title: "Sound Electric invoice — Aug 18 ($3,200)",
    status: "requested",
    requested: "2026-09-11",
    due: null,
  },
];

const closeCategory = (name: string): string =>
  stableId(`request-category:${CLOSE_LABEL}:${name}`);
export const SQUARE_REQUEST = stableId(`request:${CLOSE_LABEL}:0`);

function copperleafClose(): ComposerData {
  const ids = CLOSE_REQUESTS.map((_, n) => stableId(`request:${CLOSE_LABEL}:${String(n)}`));
  const received = (r: CloseRequest): boolean => r.status === "received";
  const rows: BinderRequestRowOut[] = CLOSE_REQUESTS.map((r, n) => ({
    id: ids[n] ?? "",
    category_id: closeCategory(r.category),
    title: r.title,
    status: r.status,
    overdue: false,
    client_visible: true,
    kind: "client_upload",
    due_on: r.due,
    requested_at: `${r.requested}T15:00:00Z`,
    incorporation_state: r.incorporation ?? "none",
    allowed_actions: ["request_item.update"],
  }));
  const items: RequestItemOut[] = CLOSE_REQUESTS.map((r, n) => ({
    id: ids[n] ?? "",
    engagement_id: COPPERLEAF_CLOSE,
    audit_area: r.category,
    description: r.title,
    status: r.status,
    created_at: `${r.requested}T15:00:00Z`,
    due_on: r.due,
    client_visible: true,
  }));
  const binder: BinderOut = {
    id: COPPERLEAF_BINDER,
    engagement_id: COPPERLEAF_CLOSE,
    work_item_id: stableId("work-item:copperleaf:2026-08"),
    kind: "close_intake",
    name: "Requests",
    part: 1,
    status: "published",
    created_from: "template",
    default_due_on: null,
    categories: CLOSE_CATEGORIES.map((name, position) => {
      const mine = CLOSE_REQUESTS.filter((r) => r.category === name);
      return {
        id: closeCategory(name),
        name,
        position,
        total_count: mine.length,
        done_count: mine.filter(received).length,
      };
    }),
    done_count: CLOSE_REQUESTS.filter(received).length,
    total_count: CLOSE_REQUESTS.length,
    allowed_actions: ["binder.read", "binder.update"],
  };
  const sent = (id: string, day: string): ActivityEventOut => ({
    id: stableId(`event:sent:${id}`),
    event_type: "request_item.sent",
    at: `${day}T15:00:00Z`,
    actor_kind: "human",
    actor_user_id: RAJ_MALHOTRA,
    via_agent: false,
    target_type: "request_item",
    target_id: id,
  });
  return {
    binder,
    rows,
    items,
    preview: { binder_id: COPPERLEAF_BINDER, name: binder.name, status: binder.status, items: [] },
    activity: Object.fromEntries(
      ids.map((id, n) => [id, [sent(id, CLOSE_REQUESTS[n]?.requested ?? "")]]),
    ),
    uploads: {
      [SQUARE_REQUEST]: [
        {
          evidence_version_id: stableId(`evidence-version:${SQUARE_REQUEST}:0`),
          file_name: SQUARE_FILE,
          media_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          size_bytes: 0,
          uploaded_at: "2026-09-03T17:00:00Z",
          uploaded_by: null,
          uploaded_by_name: "Ben Ashby",
        },
      ],
    },
  };
}

/** The composer's routes over one or more binders. Writes change this scenario's own copy. */
function handlers(start: readonly ComposerData[]): Record<string, FixtureHandler> {
  const data = structuredClone(start) as ComposerData[];
  const byBinder = (r: FixtureRequest) => data.find((d) => d.binder.id === r.params.binder_id);
  const byEngagement = (r: FixtureRequest) =>
    data.find((d) => d.binder.engagement_id === r.params.engagement_id);
  const v2 = (
    d: ComposerData,
    item: RequestItemOut,
    patch: RequestItemPatchIn = {},
  ): RequestItemV2Out => {
    const row = d.rows.find((r) => r.id === item.id);
    return {
      id: item.id,
      engagement_id: item.engagement_id,
      binder_id: d.binder.id,
      title: patch.title ?? row?.title ?? null,
      description: item.description,
      status: item.status,
      client_visible: item.client_visible ?? false,
      due_on: item.due_on ?? null,
      category_id: row?.category_id ?? null,
      client_assignee_user_id: item.client_assignee_user_id ?? null,
      wave: patch.wave ?? null,
      allowed_actions: row?.allowed_actions ?? [],
    };
  };
  return {
    ...E0.handlers,
    "GET /v1/binders/{binder_id}": (r) => {
      const d = byBinder(r);
      return d === undefined ? json(NOT_FOUND, 404) : json(d.binder);
    },
    "GET /v1/binders/{binder_id}/requests": (r) => {
      const d = byBinder(r);
      if (d === undefined) return json(NOT_FOUND, 404);
      const body: ListPageBinderRequestRowOut = {
        items: d.rows,
        next_cursor: null,
        total: d.rows.length,
      };
      return json(body);
    },
    "GET /v1/binders/{binder_id}/client-preview": (r) => {
      const d = byBinder(r);
      return d === undefined ? json(NOT_FOUND, 404) : json(d.preview);
    },
    "GET /v1/engagements/{engagement_id}/request-items": (r) => {
      const d = byEngagement(r);
      return json(d?.items ?? seed.requestItems[r.params.engagement_id ?? ""] ?? []);
    },
    "GET /v1/engagements/{engagement_id}/request-items/{item_id}/activity": (r) => {
      const d = byEngagement(r);
      const body: ListPageActivityEventOut = {
        items: d?.activity[r.params.item_id ?? ""] ?? [],
        next_cursor: null,
        total: d?.activity[r.params.item_id ?? ""]?.length ?? 0,
      };
      return json(body);
    },
    "GET /v1/engagements/{engagement_id}/request-items/{item_id}/uploads": (r) =>
      json(byEngagement(r)?.uploads?.[r.params.item_id ?? ""] ?? []),
    "GET /v1/engagements/{engagement_id}/request-items/{item_id}/comments": () => json([]),
    "POST /v1/engagements/{engagement_id}/request-items": (r) => {
      const d = byEngagement(r);
      if (d === undefined) return json(NOT_FOUND, 404);
      const body = r.body as RequestItemIn;
      const item: RequestItemOut = {
        id: stableId(`request:new:${d.binder.id}:${String(d.items.length)}`),
        engagement_id: d.binder.engagement_id,
        audit_area: body.audit_area,
        description: body.description,
        status: "draft",
        created_at: "2026-09-14T14:41:00Z",
        client_visible: false,
      };
      d.items.push(item);
      d.rows.push({ ...rowOf(d.binder.id, item), title: body.description });
      d.binder = { ...d.binder, total_count: (d.binder.total_count ?? 0) + 1 };
      return json(item, 201);
    },
    "PATCH /v1/engagements/{engagement_id}/request-items/{item_id}": (r) => {
      const d = byEngagement(r);
      const item = d?.items.find((i) => i.id === r.params.item_id);
      if (d === undefined || item === undefined) return json(NOT_FOUND, 404);
      const patch = r.body as RequestItemPatchIn;
      Object.assign(item, {
        ...(patch.description == null ? {} : { description: patch.description }),
        ...(patch.due_on === undefined ? {} : { due_on: patch.due_on }),
        ...(patch.client_assignee_user_id == null
          ? {}
          : { client_assignee_user_id: patch.client_assignee_user_id }),
      });
      d.rows = d.rows.map((row) =>
        row.id === item.id
          ? {
              ...row,
              ...(patch.title == null ? {} : { title: patch.title }),
              ...(patch.category_id == null ? {} : { category_id: patch.category_id }),
              due_on: item.due_on ?? null,
            }
          : row,
      );
      return json(v2(d, item, patch));
    },
    "POST /v1/engagements/{engagement_id}/request-items/{item_id}/delegate": (r) => {
      const d = byEngagement(r);
      return d === undefined ? json(NOT_FOUND, 404) : json({ delegated: true });
    },
    "POST /v1/engagements/{engagement_id}/request-items/{item_id}/incorporate": (r) => {
      const d = byEngagement(r);
      const item = d?.items.find((i) => i.id === r.params.item_id);
      const row = d?.rows.find((x) => x.id === r.params.item_id);
      if (d === undefined || item === undefined || row === undefined) {
        return json(NOT_FOUND, 404);
      }
      if (row.incorporation_state !== "pending_incorporation") {
        return json({ detail: "illegal_transition" }, 409);
      }
      d.rows = d.rows.map((x) =>
        x.id === row.id ? { ...x, incorporation_state: "incorporated" as const } : x,
      );
      return json({
        ...v2(d, item),
        incorporation_state: "incorporated",
        incorporated_at: "2026-09-14T14:41:00Z",
        incorporated_by: r.persona === undefined ? null : stableId(`user:${r.persona}`),
      } satisfies RequestItemV2Out);
    },
    "GET /v1/engagements/{engagement_id}/review-reason-codes/{applies_to}": () =>
      json(SEND_BACK_REASONS),
    "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/send-back": (
      r,
    ) => {
      const d = byEngagement(r);
      const itemId = Object.entries(d?.uploads ?? {}).find(([, files]) =>
        files.some((f) => f.evidence_version_id === r.params.version_id),
      )?.[0];
      if (d === undefined || itemId === undefined) return json(NOT_FOUND, 404);
      d.rows = d.rows.map((x) => (x.id === itemId ? { ...x, status: "returned" as const } : x));
      const decision: DecisionOut = {
        id: `decision:${r.params.version_id ?? ""}`,
        decision: "send_back",
        evidence_version_id: r.params.version_id ?? "",
        reason_code: (r.body as { reason_code?: string } | null)?.reason_code ?? null,
        item_status: "returned",
        request_item_ids: [itemId],
        corrects_proposal: false,
      };
      return json(decision, 201);
    },
    "POST /v1/engagements/{engagement_id}/request-items/{item_id}/send": (r) => {
      const d = byEngagement(r);
      const item = d?.items.find((i) => i.id === r.params.item_id);
      if (d === undefined || item === undefined) return json(NOT_FOUND, 404);
      if (item.due_on == null) return json({ detail: "due_date_required" }, 422);
      item.status = "requested";
      item.client_visible = true;
      d.rows = d.rows.map((row) =>
        row.id === item.id
          ? {
              ...row,
              status: "requested",
              client_visible: true,
              requested_at: "2026-09-14T14:41:00Z",
            }
          : row,
      );
      return json(v2(d, item));
    },
  };
}

function at(
  state: string,
  persona: string,
  clock: string,
  data: readonly ComposerData[],
): Scenario {
  return { state, persona, clock, handlers: handlers(data) };
}

/** c (A-03-T15): a's binder with Northwind's approved sample behind the Sample wave. */
function sampleWave(): Scenario {
  const base = at("c", "marcus-delaney", CLOCK_A, [northwind(NORTHWIND_BINDER, "2026-09-21")]);
  const participants = northwindParticipants();
  return {
    ...base,
    handlers: {
      ...samplingHandlers({ sets: northwindSampleSets(), set: participants }),
      ...generateHandlers(participants, []),
      ...base.handlers,
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "marcus-delaney", CLOCK_A, [northwind(NORTHWIND_BINDER, "2026-09-21")]),
  b: at("b", "marcus-delaney", CLOCK_A, [northwind(NORTHWIND_BINDER, "2026-09-21")]),
  c: sampleWave(),
  e: at("e", "marcus-delaney", CLOCK_A, [northwind(NORTHWIND_NO_DEFAULT, null)]),
  f: at("f", "cole-hart", CLOCK_F, [granitePeak()]),
  d: at("d", "raj-malhotra", CLOCK_A, [copperleafClose()]),
});

export type Shl14State = keyof typeof scenarios;

const bridgeId =
  (seed.requestItems[NORTHWIND] ?? []).find((i) => i.description === BRIDGE_TITLE)?.id ?? null;

/** What each state opens: the binder and the request (null composes a new one). */
export const OPENS: Readonly<
  Record<
    Shl14State,
    {
      binderId: string;
      requestId: string | null;
      workItemId?: string;
      initial?: { title?: string; wave?: "sample"; assignee?: string };
    }
  >
> = {
  a: { binderId: NORTHWIND_BINDER, requestId: null },
  b: { binderId: NORTHWIND_BINDER, requestId: bridgeId },
  c: {
    binderId: NORTHWIND_BINDER,
    requestId: null,
    workItemId: northwindParticipants().work_item_id,
    initial: {
      title: "Enrollment and opt-out forms — sampled participants",
      wave: "sample",
      ...(contactIdOf(NORTHWIND, "Dana Kowalski") === null
        ? {}
        : { assignee: contactIdOf(NORTHWIND, "Dana Kowalski") ?? "" }),
    },
  },
  e: { binderId: NORTHWIND_NO_DEFAULT, requestId: null },
  f: { binderId: GRANITE_BINDER, requestId: stableId("request:granite-peak:surl") },
  d: { binderId: COPPERLEAF_BINDER, requestId: SQUARE_REQUEST },
};

/** The E0 day the seed stands at, for the scenario tests. */
export const E0_INSTANT = DEMO_INSTANT;
