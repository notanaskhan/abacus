// BND-02's binders at E0, Mon Sep 14, 2026, 9:24 AM CT (P-06-T12): the Feld 2025 Binder (a, f),
// its TY2026 roll-forward Draft (b) and its Complete form (c), and the Estate of Walter Thornbury's
// 2025 Binder (d, e). Titles, file names, dates, people and rail values are the handoff's
// (spec.md and the canvas `Wave 2 - Home & Records.dc.html#bnd02`, `BN.FELD`, `DONE`, `DRAFT`,
// `THORN`, `KV`); the client wording follows the canvas's rule ("Please upload your …" unless a
// request names its own). Every body is typed against the generated client.
//
// Footing (BND-02 acceptance): Feld 7 = 3 + 1 + 1 + 1 + 1; 5 satisfied (4 Received ✓ + the
// firm-provided draft K-1) and 2 open. Thornbury 15, 6 received, 9 open, 3 of them past Aug 31.

import type {
  ActivityEventOut,
  BinderCategoryOut,
  BinderClientPreviewOut,
  BinderLiveOut,
  BinderOut,
  BinderRequestRowOut,
  BinderStatus,
  EngagementOut,
  RequestStatus,
  UploadOut,
  WorkItemOut,
} from "@abacus/api-client";
import { entityIdOf, slugOfClient } from "./clients";
import { SEATS, slugOf } from "./people";
import { stableId } from "./prng";

/** The nine portal categories, in the platform-portal order (C-16). */
export const BINDER_CATEGORIES = [
  "Personal & Household Information",
  "Income Sources",
  "Home & Property",
  "Health & Medical",
  "Education & Student",
  "Retirement",
  "Charitable & Donations",
  "Business & Self-Employment",
  "Other Activity",
] as const;
type Category = (typeof BINDER_CATEGORIES)[number];

const FELD = "Jonah & Claire Feld";
const THORNBURY = "Estate of Walter Thornbury";

function userId(initials: string): string {
  const seat = SEATS.find((s) => s.initials === initials);
  if (seat === undefined) throw new Error(`no seat ${initials}`);
  return stableId(`user:${slugOf(seat.name)}`);
}

export const KEVIN_OSEI = userId("KO");
const OLIVIA_BRANDT = userId("OB");

/** Noon CT (CDT) on a calendar day: the handoff gives dates only. */
const noon = (day: string): string => `${day}T17:00:00.000Z`;

/** The binders' ids, as BND-01's rows carry them (fixtures/seed/binders.ts `toBinderRow`). */
export function binderIdOf(client: string, season = "TY2025"): string {
  return stableId(`binder:${slugOfClient(client)}:${season}:1`);
}

export const FELD_BINDER_ID = binderIdOf(FELD);
export const FELD_DRAFT_ID = binderIdOf(FELD, "TY2026");
export const THORNBURY_BINDER_ID = binderIdOf(THORNBURY);

/** A request as the handoff draws it. */
interface Spec {
  key: string;
  category: Category;
  title: string;
  status: RequestStatus;
  requested: string | null;
  due: string;
  prior: boolean;
  kind?: "client_upload" | "firm_provided";
  overdue?: boolean;
  wording?: string;
  files?: readonly { name: string; by: string; at: string }[];
}

const FELD_ROWS: readonly Spec[] = [
  {
    key: "w2",
    category: "Income Sources",
    title: "2025 W-2 From Mercer Hill Health",
    status: "received",
    requested: "2026-02-03",
    due: "2026-03-15",
    prior: true,
    files: [
      { name: "Claire_Feld_2025_W2_MercerHill.pdf", by: "Claire Feld", at: noon("2026-08-03") },
    ],
  },
  {
    key: "brk",
    category: "Income Sources",
    title: "2025 Consolidated 1099 From Halvard Securities (Acct ••3318)",
    status: "received",
    requested: "2026-02-03",
    due: "2026-03-15",
    prior: true,
    files: [
      {
        name: "Jonah_Feld_2025_1099_Composite_Halvard.pdf",
        by: "Jonah Feld",
        at: noon("2026-08-05"),
      },
    ],
  },
  {
    key: "k1",
    category: "Income Sources",
    title: "Schedule K-1 from Ridgeline Property Partners, LP",
    status: "received",
    kind: "firm_provided",
    requested: "2026-02-03",
    due: "2026-03-15",
    prior: true,
    wording: "Brightwater Hale prepares this K-1 and adds it for you. Nothing to upload.",
    files: [
      {
        name: "Ridgeline_2025_K-1_JonahFeld_DRAFT.pdf",
        by: "Olivia Brandt",
        at: noon("2026-08-24"),
      },
    ],
  },
  {
    key: "m1098",
    category: "Home & Property",
    title: "2025 Form 1098 From Hudson Mutual Savings (co-op loan)",
    status: "received",
    requested: "2026-02-03",
    due: "2026-03-15",
    prior: true,
    files: [
      {
        name: "Claire_Feld_2025_1098_HudsonMutual.pdf",
        by: "Claire Feld",
        at: noon("2026-08-03"),
      },
    ],
  },
  {
    key: "aca",
    category: "Health & Medical",
    title: "Form 1095-C From Mercer Hill Health",
    status: "requested",
    requested: "2026-02-03",
    due: "2026-03-15",
    prior: true,
  },
  {
    key: "gift",
    category: "Charitable & Donations",
    title: "2025 donation receipts and acknowledgment letters",
    status: "received",
    requested: "2026-02-03",
    due: "2026-03-15",
    prior: true,
    files: [{ name: "Feld_2025_Donations.pdf", by: "Claire Feld", at: noon("2026-08-07") }],
  },
  {
    key: "est",
    category: "Other Activity",
    title: "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
    status: "requested",
    requested: "2026-09-01",
    due: "2026-09-21",
    prior: false,
  },
];

/** The Feld 2025 binder's requests at E0 as TPL-19 counts them (F-06-T02): open (to do),
 * received from the client, or provided by the firm. Derived from the rows above. */
export const FELD_REQUEST_FACTS: readonly {
  key: string;
  title: string;
  state: "to_do" | "received" | "provided";
}[] = FELD_ROWS.map((r) => ({
  key: r.key,
  title: r.title,
  state: r.kind === "firm_provided" ? "provided" : r.status === "requested" ? "to_do" : "received",
}));

/** c: the 1095-C filed from the Inbox and the estimates matched, both Sep 14. */
const FELD_DONE_ROWS: readonly Spec[] = FELD_ROWS.map((r) => {
  if (r.key === "aca") {
    return {
      ...r,
      status: "received",
      files: [{ name: "Feld_1095C_2025.pdf", by: "Claire Feld", at: noon("2026-09-14") }],
    };
  }
  if (r.key === "est") {
    return {
      ...r,
      status: "received",
      files: [
        { name: "Feld_2025_Estimated_Payments.pdf", by: "Claire Feld", at: noon("2026-09-14") },
        { name: "Feld_2025_IT2105_Confirmations.pdf", by: "Claire Feld", at: noon("2026-09-14") },
      ],
    };
  }
  return r;
});

/** g (R2): Mon Sep 14, 9:31 AM: Claire's two estimated-payment files land through the portal and
 * wait for review ("Uploaded – needs review"); the files are c's (the same confirmations). */
export const ESTIMATES_UPLOADED_AT = "2026-09-14T14:31:00.000Z";
const FELD_UPLOADED_ROWS: readonly Spec[] = FELD_ROWS.map((r) =>
  r.key === "est"
    ? {
        ...r,
        status: "uploaded",
        files: [
          {
            name: "Feld_2025_Estimated_Payments.pdf",
            by: "Claire Feld",
            at: ESTIMATES_UPLOADED_AT,
          },
          {
            name: "Feld_2025_IT2105_Confirmations.pdf",
            by: "Claire Feld",
            at: ESTIMATES_UPLOADED_AT,
          },
        ],
      }
    : r,
);

/** b: the seven carried into the TY2026 Draft, unsent. */
const FELD_DRAFT_ROWS: readonly Spec[] = FELD_ROWS.map(
  ({ key, category, kind, wording, title }) => ({
    key,
    category,
    ...(kind === undefined ? {} : { kind }),
    ...(wording === undefined ? {} : { wording }),
    title: title.replace(/2025/g, "2026"),
    status: "draft",
    requested: null,
    due: "2027-03-15",
    prior: true,
  }),
);

const late = { due: "2026-08-31", overdue: true } as const;
const thorn = (
  key: string,
  category: Category,
  title: string,
  extra: Partial<Spec> = {},
): Spec => ({
  key,
  category,
  title,
  status: "requested",
  requested: "2026-07-27",
  due: "2026-09-30",
  prior: true,
  ...extra,
});
const got = (name: string, day: string): Partial<Spec> => ({
  status: "received",
  files: [{ name, by: "Paul Thornbury", at: noon(day) }],
});

const THORNBURY_ROWS: readonly Spec[] = [
  thorn("t1", "Personal & Household Information", "Letters of office (executor appointment)", {
    ...got("Thornbury_Letters_of_Office.pdf", "2026-08-04"),
    prior: false,
  }),
  thorn("t2", "Personal & Household Information", "Certified death certificate", {
    ...got("Thornbury_Death_Certificate.pdf", "2026-08-04"),
    prior: false,
  }),
  thorn(
    "t3",
    "Income Sources",
    "2025 SSA-1099 (Social Security benefits)",
    got("Walter_Thornbury_2025_SSA-1099.pdf", "2026-08-12"),
  ),
  thorn("t4", "Income Sources", "2025 Form 1099-R From Lakeview Pension Plan", late),
  thorn("t5", "Income Sources", "2025 Consolidated 1099 From Northern Lakes Brokerage", late),
  thorn("t6", "Income Sources", "2025 Form 1099-INT From Prairie State Bank"),
  thorn("t7", "Income Sources", "2025 Form 1099-DIV From Lakeshore Mutual Funds"),
  thorn(
    "t8",
    "Home & Property",
    "2025 Form 1098 (mortgage interest)",
    got("Walter_Thornbury_2025_1098.pdf", "2026-08-18"),
  ),
  thorn("t9", "Home & Property", "2025 Cook County property tax bills", late),
  thorn("t10", "Health & Medical", "2025 medical and long-term care expenses"),
  thorn(
    "t11",
    "Charitable & Donations",
    "2025 donation receipts and acknowledgment letters",
    got("Thornbury_2025_Donations.pdf", "2026-09-09"),
  ),
  thorn("t12", "Retirement", "2025 IRA contribution confirmations"),
  thorn(
    "t13",
    "Retirement",
    "2025 Form 5498 (IRA year-end value)",
    got("Walter_Thornbury_2025_5498.pdf", "2026-08-12"),
  ),
  thorn("t14", "Other Activity", "2025 estimated tax payment confirmations"),
  thorn("t15", "Other Activity", "2024 Form 1040 as filed"),
];

/** The canvas's client wording rule. */
function wordingOf(spec: Spec): string {
  return spec.wording ?? `Please upload your ${spec.title.replace(/ From /, " from ")}.`;
}

const ROW_ACTIONS = [
  "request_item.read",
  "request_item.update",
  "request_item.waive",
  "request_item.return",
] as const;

/** One binder's fixture: the record, its rows, and what the dock and the preview read. */
export interface BinderFixture {
  binder: BinderOut;
  rows: BinderRequestRowOut[];
  live: BinderLiveOut;
  preview: BinderClientPreviewOut;
  uploads: Readonly<Record<string, UploadOut[]>>;
  activity: ActivityEventOut[];
  /** Per request: who sent it (`request_item.sent`). */
  requestActivity: Readonly<Record<string, ActivityEventOut[]>>;
  /** The record's own key per row id, for the scenarios (`k1`, `t12`). */
  keys: Readonly<Record<string, string>>;
}

interface BinderSpec {
  id: string;
  client: string;
  name: string;
  status: BinderStatus;
  engagementId: string;
  workItemId: string;
  published: string | null;
  recipients: readonly string[];
  sourceRef: string;
  rows: readonly Spec[];
  markedDone?: { at: string; by: string };
  /** Row overrides by key: visibility off (f), the client's Ignore (e), live counts (a). */
  hidden?: readonly string[];
  ignored?: Readonly<Record<string, { at: string; reason: "not_this_year" }>>;
  live?: Readonly<Record<string, { uploading?: number; waiting?: number }>>;
}

const contactId = (name: string): string => stableId(`contact:${slugOf(name)}`);

function categories(id: string, rows: readonly BinderRequestRowOut[]): BinderCategoryOut[] {
  return BINDER_CATEGORIES.map((name, position) => {
    const catId = stableId(`request-category:${id}:${name}`);
    const mine = rows.filter((r) => r.category_id === catId);
    return {
      id: catId,
      name,
      position,
      total_count: mine.length,
      done_count: mine.filter((r) => r.status === "received" || r.status === "not_applicable")
        .length,
    };
  });
}

function build(spec: BinderSpec): BinderFixture {
  const keys: Record<string, string> = {};
  const uploads: Record<string, UploadOut[]> = {};
  const requestActivity: Record<string, ActivityEventOut[]> = {};
  const rows: BinderRequestRowOut[] = spec.rows.map((r) => {
    const id = stableId(`request:${spec.id}:${r.key}`);
    keys[id] = r.key;
    const ignored = spec.ignored?.[r.key];
    uploads[id] = (r.files ?? []).map((f, i) => ({
      evidence_version_id: stableId(`evidence-version:${id}:${String(i)}`),
      file_name: f.name,
      media_type: "application/pdf",
      size_bytes: 0,
      uploaded_at: f.at,
      uploaded_by: f.by === "Olivia Brandt" ? OLIVIA_BRANDT : null,
      uploaded_by_name: f.by,
    }));
    requestActivity[id] =
      r.requested === null
        ? []
        : [
            {
              id: stableId(`event:sent:${id}`),
              event_type: "request_item.sent",
              at: noon(r.requested),
              actor_kind: "human",
              actor_user_id: KEVIN_OSEI,
              via_agent: false,
              target_type: "request_item",
              target_id: id,
            },
          ];
    return {
      id,
      category_id: stableId(`request-category:${spec.id}:${r.category}`),
      title: r.title,
      status: r.status,
      overdue: r.overdue === true,
      client_visible: !(spec.hidden ?? []).includes(r.key),
      kind: r.kind ?? "client_upload",
      due_on: r.due,
      requested_at: r.requested === null ? null : noon(r.requested),
      client_ignored_at: ignored?.at ?? null,
      client_ignore_reason: ignored?.reason ?? null,
      source_tag: r.prior ? "prior_year" : null,
      incorporation_state: "none",
      // R2 (P-06-T22): a client's upload carries its screening glyph; Linked (n) counts the live
      // fulfilments, "—" at none. The firm-provided K-1 is not screened (it is no client upload).
      screening:
        (r.kind ?? "client_upload") === "client_upload" && (r.files ?? []).length > 0
          ? "passed"
          : null,
      linked_count: (r.files ?? []).length > 0 ? (r.files ?? []).length : null,
      upload_count: (r.files ?? []).length,
      allowed_actions: [...ROW_ACTIONS, ...(r.status === "draft" ? ["request_item.send"] : [])],
    };
  });
  const cats = categories(spec.id, rows);
  const done = rows.filter((r) => r.status === "received" || r.status === "not_applicable").length;
  const binder: BinderOut = {
    id: spec.id,
    engagement_id: spec.engagementId,
    work_item_id: spec.workItemId,
    kind: "organizer",
    name: spec.name,
    part: 1,
    status: spec.status,
    created_from: "engine_import",
    prior_year_source_ref: spec.sourceRef,
    template_ref: "1040 · prior-year",
    default_due_on: null,
    recipients: spec.recipients.map((name) => ({ contact_id: contactId(name), name })),
    categories: cats,
    done_count: done,
    total_count: rows.length,
    published_at: spec.published === null ? null : noon(spec.published),
    published_by: spec.published === null ? null : KEVIN_OSEI,
    unpublished_at: null,
    unpublished_by: null,
    unpublish_reason: null,
    marked_done_at: spec.markedDone?.at ?? null,
    marked_done_by: spec.markedDone === undefined ? null : contactId(spec.markedDone.by),
    marked_done_open_count: spec.markedDone === undefined ? null : 0,
    closed_at: null,
    closed_reason: null,
    follow_up_override: { every_days: 7, max: 4 },
    undo_until: null,
    allowed_actions: [
      "binder.read",
      "binder.publish",
      "binder.update",
      "binder.create",
      "follow_up.draft", // P-06-T16: "Send reminder…"
      "follow_up.send",
    ],
  };
  const live: BinderLiveOut = {
    as_of: "2026-09-14T14:24:00.000Z",
    items: rows.map((row) => {
      const counts = spec.live?.[keys[row.id] ?? ""];
      return {
        request_item_id: row.id,
        uploading_files: counts?.uploading ?? 0,
        inbox_waiting: counts?.waiting ?? 0,
        screening_running: false,
      };
    }),
  };
  const preview: BinderClientPreviewOut = {
    binder_id: spec.id,
    name: spec.name,
    status: spec.status,
    items: spec.rows
      .map((r, i) => ({ r, row: rows[i] }))
      .filter(({ row }) => row?.client_visible === true)
      .map(({ r, row }) => ({
        id: row?.id ?? "",
        category_name: r.category,
        title: r.title,
        description: wordingOf(r),
        status: r.status,
        client_ignored: row?.client_ignored_at != null,
        due_on: r.due,
      })),
  };
  const activity: ActivityEventOut[] =
    spec.published === null
      ? []
      : [
          {
            id: stableId(`event:published:${spec.id}`),
            event_type: "binder.published",
            at: noon(spec.published),
            actor_kind: "human",
            actor_user_id: KEVIN_OSEI,
            via_agent: false,
            target_type: "binder",
            target_id: spec.id,
          },
        ];
  return { binder, rows, live, preview, uploads, activity, requestActivity, keys };
}

/** The Feld household's engagement and its work items, as the seed has them. */
const feldEngagement = (feldId: string): string => feldId;

export interface BinderSet {
  feld: BinderFixture;
  feldHidden: BinderFixture;
  feldDraft: BinderFixture;
  feldDone: BinderFixture;
  /** g (R2): the estimates uploaded and waiting for review. */
  feldUploaded: BinderFixture;
  thornbury: BinderFixture;
  thornburyIgnored: BinderFixture;
  /** The Thornbury engagement and work item (not in the audit-core seed). */
  thornburyEngagement: EngagementOut;
  thornburyWorkItems: WorkItemOut[];
  /** The TY2026 return the Draft roll-forward sits on. */
  feldDraftWorkItem: WorkItemOut;
}

export function binderSet(feldEngagementId: string, feldWorkItemId: string): BinderSet {
  const feld: Omit<BinderSpec, "rows"> = {
    id: FELD_BINDER_ID,
    client: FELD,
    name: "2025 Binder",
    status: "published",
    engagementId: feldEngagement(feldEngagementId),
    workItemId: feldWorkItemId,
    published: "2026-02-03",
    recipients: ["Claire Feld", "Jonah Feld"],
    sourceRef: "2024 return (CCH Axcess)",
    live: { aca: { waiting: 2 }, est: { uploading: 2 } },
  };
  const thornSlug = slugOfClient(THORNBURY);
  const thornEngagement = stableId(`engagement:tax:${thornSlug}:2025`);
  const thornItem = stableId(`work-item:${thornSlug}:2025 Form 1040`);
  const thornbury: BinderSpec = {
    id: THORNBURY_BINDER_ID,
    client: THORNBURY,
    name: "2025 Binder",
    status: "published",
    engagementId: thornEngagement,
    workItemId: thornItem,
    published: "2026-07-27",
    recipients: ["Paul Thornbury"],
    sourceRef: "2024 return (CCH Axcess)",
    rows: THORNBURY_ROWS,
  };
  const draftItem: WorkItemOut = {
    id: stableId("work-item:feld:TY2026"),
    kind: "tax_return",
    name: "TY2026 Form 1040",
    status: "active",
    period_start: "2026-01-01",
    period_end: "2026-12-31",
    due_on: "2027-04-15",
    phase: null,
  };
  return {
    feld: build({ ...feld, rows: FELD_ROWS }),
    feldHidden: build({ ...feld, rows: FELD_ROWS, hidden: ["k1"] }),
    feldDraft: build({
      ...feld,
      id: FELD_DRAFT_ID,
      name: "2026 Binder",
      status: "draft",
      workItemId: draftItem.id,
      published: null,
      sourceRef: "2025 return (CCH Axcess)",
      rows: FELD_DRAFT_ROWS,
      live: {},
    }),
    feldDone: build({
      ...feld,
      status: "complete",
      rows: FELD_DONE_ROWS,
      live: {},
      markedDone: { at: "2026-09-15T14:02:00.000Z", by: "Claire Feld" },
    }),
    feldUploaded: build({ ...feld, rows: FELD_UPLOADED_ROWS, live: { aca: { waiting: 2 } } }),
    thornbury: build(thornbury),
    thornburyIgnored: build({
      ...thornbury,
      ignored: { t12: { at: noon("2026-09-09"), reason: "not_this_year" } },
    }),
    thornburyEngagement: {
      id: thornEngagement,
      name: "TY2025 Form 1040",
      type: "tax_compliance",
      status: "active",
      service_line: "tax",
      client_id: stableId(`client:${thornSlug}`),
      client_name: THORNBURY,
      client_entity_id: entityIdOf(thornSlug, THORNBURY),
      client_entity_name: THORNBURY,
      fiscal_period_start: "2025-01-01",
      fiscal_period_end: "2025-12-31",
      created_at: noon("2026-07-20"),
      team: [],
      gates: [
        { gate: "G1", met: true, blockers: [] },
        { gate: "G3", met: true, blockers: [] },
      ],
    },
    thornburyWorkItems: [
      {
        id: thornItem,
        kind: "tax_return",
        name: "TY2025 Form 1040",
        status: "active",
        period_start: "2025-01-01",
        period_end: "2025-12-31",
        due_on: "2026-10-15",
        phase: null,
      },
    ],
    feldDraftWorkItem: draftItem,
  };
}
