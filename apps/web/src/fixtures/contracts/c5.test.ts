// P-06-T02: C5 v1 consumer fixture assertions (A-01, R-01, T-02, C-01). Each fixture below is typed
// with the generated client, so a breaking change to a C5 shape fails `tsc`; each is also checked
// against the OpenAPI document at run time, for what a type cannot say (formats, lengths, closed
// enums, a field the schema does not have). Brightwater Hale, synthetic; shapes from the contract's
// examples (docs/contracts/c5-requests-binders.md §8). The pytest half lives in
// backend/tests/contracts/c5_requests_binders/.
import type {
  BinderClientPreviewOut,
  BinderMarkedDoneOut,
  BinderOut,
  BinderRowOut,
  BinderStatus,
  ClientPreviewItemOut,
  ClientResponseIn,
  EvidenceScreeningStatus,
  IgnoreIn,
  IgnoredOut,
  LinkedRefOut,
  ListPageBinderRowOut,
  RequestItemV2Out,
  RequestStatus,
  UploadIntentOut,
  WithdrawalOut,
} from "@abacus/api-client";
import { type EnumCovered, STATUS_REGISTRY } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import { validateSchema } from "../schema-check";

/** `true` only when each of A and B is assignable to the other (two unions of the same literals). */
type Equal<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;

// Fields that exist only while a request is drafted, or only for the firm (INV-4, DV-11).
type FirmOnly =
  | "drafted_by_run_id"
  | "drafted_wording_source"
  | "client_visible"
  | "sent_by"
  | "na_by"
  | "na_reason"
  | "firm_owner_user_id"
  | "supports_ref"
  | "linked_ref"
  | "linked_count"
  | "screening"
  | "incorporation_state"
  | "undo_until"
  | "allowed_actions"
  | "preparer_user_id"
  | "unpublish_reason"
  | "template_ref"
  | "prior_year_source_ref"
  | "follow_up_override"
  | "source_tag";
type ClientSafe<T> = [Extract<keyof T, FirmOnly>] extends [never] ? true : false;

const ID = {
  binder: "6f1c2b0e-3d4a-4c5b-9e6f-7a8b9c0d1e2f",
  engagement: "0b7e9a52-1c3d-4e5f-8a6b-2c4d6e8f0a1b",
  workItem: "3c5e7a9b-2d4f-4a6c-8e0b-1d3f5a7c9e2b",
  preparer: "8a2c4e6f-0b1d-4f3a-9c5e-7b9d1f3a5c7e",
  item: "5d7f9b1c-3e5a-4c7e-a0b2-4d6f8a0c2e4f",
  run: "9e1a3c5f-7b9d-4e1f-b3a5-6c8e0a2c4e6a",
  k1: "2a4c6e8a-0c2e-4a4c-8e6a-9b1d3f5b7d9f",
  version: "7c9e1b3d-5f7b-4d9f-a1c3-8e0a2c4e6a8c",
  category: "4b6d8f0a-2c4e-4b6d-9f1a-3c5e7a9c1e3b",
} as const;

// ---- Shapes (A-01 and the BND-01 index) -------------------------------------------------------

// GET /v1/binders?service=tax_returns&season=TY2025 (BND-01 a): the contract's §8 example.
const BND01: ListPageBinderRowOut = {
  items: [
    {
      id: ID.binder,
      engagement_id: ID.engagement,
      work_item_id: ID.workItem,
      client_name: "Claire Feld",
      work_item_label: "2025 Form 1040",
      name: "Feld 2025 Binder",
      kind: "pbc",
      part: 1,
      status: "published",
      preparer_user_id: ID.preparer,
      done_count: 5,
      total_count: 7,
      last_client_activity_at: "2026-09-14T14:02:00Z",
      tags: [],
      allowed_actions: ["binder.read"],
    },
  ],
  next_cursor: "c2",
  total: 241,
  total_capped: false,
  counts: { draft: 1, published: 48, unpublished: 0, complete: 40, closed: 152 },
  facets: {},
};
const TILES = {
  draft: 1,
  published: 48,
  unpublished: 0,
  complete: 40,
  closed: 152,
} satisfies Record<BinderStatus, number>;

const RECORD: BinderOut = {
  id: ID.binder,
  engagement_id: ID.engagement,
  work_item_id: ID.workItem,
  name: "Feld 2025 Binder",
  kind: "pbc",
  part: 1,
  status: "published",
  created_from: "prior_year_binder",
  prior_year_source_ref: ID.binder,
  categories: [{ id: ID.category, name: "Income", position: 1, done_count: 5, total_count: 7 }],
  done_count: 5,
  total_count: 7,
  published_at: "2026-09-01T14:00:00Z",
  published_by: ID.preparer,
  undo_until: null,
  follow_up_override: { every_days: 7, max: 4 },
  allowed_actions: ["binder.read", "binder.publish"],
};

describe("C5 shapes as A-01 reads them", () => {
  it("validates the BND-01 page and its tiles foot to the visible total", () => {
    expect(validateSchema("ListPage_BinderRowOut_", BND01)).toEqual([]);
    expect(BND01.counts).toEqual(TILES);
    expect(Object.values(TILES).reduce((a, b) => a + b, 0)).toBe(BND01.total);
  });

  it("validates the BND-02 record and refuses a field the schema lacks", () => {
    expect(validateSchema("BinderOut", RECORD)).toEqual([]);
    expect(validateSchema("BinderOut", { ...RECORD, approved_by_agent: true })).toEqual([
      "BinderOut.approved_by_agent: not in the schema",
    ]);
  });

  it("validates an agent-drafted request awaiting a person's send", () => {
    const drafted: RequestItemV2Out = {
      id: ID.item,
      engagement_id: ID.engagement,
      binder_id: ID.binder,
      title: "Brokerage statements",
      description: "Upload every 2025 year-end brokerage statement.",
      status: "draft",
      client_visible: false,
      drafted_by_run_id: ID.run,
      drafted_wording_source: "model",
      sent_by: null,
      allowed_actions: ["request_item.update", "request_item.send"],
    };
    expect(validateSchema("RequestItemV2Out", drafted)).toEqual([]);
  });
});

// ---- The 9.5.6 codes and the client's words (R-01) --------------------------------------------

type Entry = { label: string; derived: boolean; clientLabel?: string };
const REQUEST = STATUS_REGISTRY.request as Record<string, Entry>;

// Chapter 09 §9.5.6, the firm's words for each stored request code.
const FIRM_WORDS = {
  draft: "Draft",
  requested: "Requested {date}",
  uploaded: "Uploaded – needs review",
  received: "Received ✓",
  returned: "Returned · {reason}",
  not_applicable: "Not applicable",
} satisfies Record<RequestStatus, string>;

// What the client reads; a draft has no client word because a client never sees one.
const CLIENT_WORDS = {
  requested: "To do",
  uploaded: "Done",
  received: "Done",
  returned: "Returned",
  not_applicable: "Ignored",
} satisfies Record<Exclude<RequestStatus, "draft">, string>;

describe("C5 status codes and client words", () => {
  it("covers the registry's binder, request and screening codes in the generated enums", () => {
    const covered = [
      true satisfies EnumCovered<"binder", BinderStatus>,
      true satisfies EnumCovered<"request", RequestStatus>,
      true satisfies EnumCovered<"evidence_screening", EvidenceScreeningStatus>,
    ];
    expect(covered).toEqual([true, true, true]);
  });

  it("reads each 9.5.6 request code in the registry's firm words, overdue derived", () => {
    for (const [code, label] of Object.entries(FIRM_WORDS)) {
      expect(REQUEST[code]?.label).toBe(label);
    }
    expect(REQUEST.overdue?.derived).toBe(true);
  });

  it("gives every client-visible code a client word and a draft none", () => {
    for (const [code, word] of Object.entries(CLIENT_WORDS)) {
      expect(REQUEST[code]?.clientLabel).toBe(word);
    }
    expect(REQUEST.draft?.clientLabel).toBeUndefined();
    expect(new Set(Object.values(CLIENT_WORDS))).toEqual(
      new Set(["To do", "Done", "Returned", "Ignored"]),
    );
  });
});

// ---- What a client principal receives (R-01) --------------------------------------------------

describe("C5 client shapes", () => {
  it("carries no draft or firm-only field in any client shape", () => {
    const safe = [
      true satisfies ClientSafe<ClientPreviewItemOut>,
      true satisfies ClientSafe<BinderClientPreviewOut>,
      true satisfies ClientSafe<IgnoredOut>,
      true satisfies ClientSafe<UploadIntentOut>,
      true satisfies ClientSafe<BinderMarkedDoneOut>,
      true satisfies ClientSafe<WithdrawalOut>,
    ];
    expect(safe.every(Boolean)).toBe(true);
    // The firm record does carry them: the check above is not vacuous.
    const firm: false = false satisfies ClientSafe<RequestItemV2Out>;
    expect(firm).toBe(false);
  });

  it("validates the preview as a recipient sees it, with an Ignore in the client's word", () => {
    const preview: BinderClientPreviewOut = {
      binder_id: ID.binder,
      name: "Thornbury 2025 Binder",
      status: "published",
      items: [
        {
          id: ID.item,
          category_name: "Income",
          title: "Brokerage statements",
          description: "Upload every 2025 year-end brokerage statement.",
          status: "requested",
          client_ignored: true,
          due_on: "2026-08-31",
        },
      ],
    };
    expect(validateSchema("BinderClientPreviewOut", preview)).toEqual([]);
    const [item] = preview.items;
    // A client Ignore keeps `requested` and reads "Ignored" (OQ-3).
    const word = item?.client_ignored ? REQUEST.not_applicable?.clientLabel : undefined;
    expect(word).toBe("Ignored");
  });

  it("validates the portal answers", () => {
    const ignored: IgnoredOut = {
      request_item_id: ID.item,
      status: "requested",
      client_ignored_at: "2026-09-10T15:20:00Z",
    };
    const done: BinderMarkedDoneOut = {
      binder_id: ID.binder,
      status: "complete",
      marked_done_at: "2026-09-15T14:02:00Z",
      open_count: 2,
    };
    const intent: UploadIntentOut = {
      request_item_id: ID.item,
      files_expected: 2,
      expires_at: "2026-09-14T14:25:30Z",
    };
    const withdrawn: WithdrawalOut = {
      evidence_version_id: ID.version,
      request_item_id: ID.item,
      withdrawn_at: "2026-09-14T14:30:00Z",
      erase_after: "2026-10-14T14:30:00Z",
    };
    expect(validateSchema("IgnoredOut", ignored)).toEqual([]);
    expect(validateSchema("BinderMarkedDoneOut", done)).toEqual([]);
    expect(validateSchema("UploadIntentOut", intent)).toEqual([]);
    expect(validateSchema("WithdrawalOut", withdrawn)).toEqual([]);
    expect(validateSchema("UploadIntentIn", { files_expected: 2 })).toEqual([]);
  });

  it("takes SPEC-042's ignore reasons and nothing else", () => {
    const same: true = true satisfies Equal<IgnoreIn["reason"], ClientResponseIn["reason"]>;
    expect(same).toBe(true);
    const body: IgnoreIn = { reason: "not_this_year" };
    expect(validateSchema("IgnoreIn", body)).toEqual([]);
    expect(validateSchema("IgnoreIn", { reason: "not_applicable_this_year" })).toHaveLength(1);
  });
});

// ---- T-02 and C-01 -----------------------------------------------------------------------------

const LINK_KINDS = { workpaper: true, procedure_step: true, k1_package: true } satisfies Record<
  LinkedRefOut["kind"],
  true
>;
const INCORPORATION = {
  none: true,
  matched: true,
  pending_incorporation: true,
  incorporated: true,
} satisfies Record<NonNullable<RequestItemV2Out["incorporation_state"]>, true>;
const BINDER_KINDS = {
  organizer: true,
  pbc: true,
  close_intake: true,
  intake: true,
  third_party: true,
} satisfies Record<BinderRowOut["kind"], true>;

describe("C5 shapes as T-02 and C-01 read them", () => {
  it("links a firm-provided item to a K-1 package and tags a rolled request", () => {
    const k1: RequestItemV2Out = {
      id: ID.item,
      engagement_id: ID.engagement,
      binder_id: ID.binder,
      title: "Draft K-1 · pre-release",
      description: "Your draft Schedule K-1 for review.",
      status: "requested",
      client_visible: true,
      kind: "firm_provided",
      linked_ref: { kind: "k1_package", id: ID.k1 },
      source_tag: "prior_year",
    };
    expect(validateSchema("RequestItemV2Out", k1)).toEqual([]);
    for (const kind of Object.keys(LINK_KINDS)) {
      expect(validateSchema("LinkedRefOut", { kind, id: ID.k1 })).toEqual([]);
    }
    expect(validateSchema("LinkedRefOut", { kind: "return", id: ID.k1 })).toHaveLength(1);
  });

  it("holds a close-intake request pending incorporation over its period", () => {
    const close: RequestItemV2Out = {
      id: ID.item,
      engagement_id: ID.engagement,
      binder_id: ID.binder,
      description: "September bank statement.",
      status: "received",
      client_visible: true,
      period_start: "2026-09-01",
      period_end: "2026-09-30",
      incorporation_state: "pending_incorporation",
    };
    expect(validateSchema("RequestItemV2Out", close)).toEqual([]);
    for (const state of Object.keys(INCORPORATION)) {
      expect(validateSchema("RequestItemV2Out", { ...close, incorporation_state: state })).toEqual(
        [],
      );
    }
    for (const kind of Object.keys(BINDER_KINDS)) {
      expect(validateSchema("BinderOut", { ...RECORD, kind })).toEqual([]);
    }
  });
});
