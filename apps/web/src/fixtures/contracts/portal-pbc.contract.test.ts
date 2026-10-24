// R-01-T02: C5 section portal-pbc consumer fixture assertions, on behalf of R-01 (POR-03, POR-04,
// POR-14), T-02 (POR-05 falls back to POR-04's upload), C-01 (POR-11 reuses the rows and the
// question slot) and A-09 (POR-23 reuses the room). Each fixture is typed with the generated
// client, so a breaking change fails `tsc`; each is also checked against the OpenAPI document at
// run time. A portal answer carries client words only, never a firm status code, an amount, a
// confidence or an agent field, at the type level and in the schema. Brightwater Hale, synthetic;
// shapes from docs/contracts/portal-pbc.md §8. The pytest half is
// backend/tests/contracts/c5_portal_pbc/.
import type {
  DropBatchOut,
  IgnoreUndoneOut,
  MarkDoneUndoneOut,
  PortalBinderListOut,
  PortalBinderOut,
  PortalReceiptOut,
  PortalRequestOut,
  PortalRoomOut,
  PortalRowOut,
  RoomSuggestOut,
} from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { validateResponse, validateSchema } from "../schema-check";

/** Every key of T and of every object type nested in it. */
type DeepKeys<T> = T extends readonly (infer U)[]
  ? DeepKeys<U>
  : T extends object
    ? { [K in keyof T & string]: K | DeepKeys<NonNullable<T[K]>> }[keyof T & string]
    : never;

// A firm status, an amount, a confidence or an agent reference, by field name (contract §1).
// `client_status` is the client's words (To do · Done · Ignored · Returned), asserted below.
type Forbidden =
  | "status"
  | `${string}_status`
  | "amount"
  | `${string}_amount`
  | "balance"
  | "materiality"
  | "currency"
  | "confidence"
  | `${string}confidence${string}`
  | `${string}score${string}`
  | "agent"
  | `agent_${string}`
  | `${string}_agent`
  | "run_id"
  | `${string}_run_id`;
/** `true` when the generated union U is exactly the listed values, in both directions. */
type Exactly<U extends string, L extends readonly string[]> = [
  Exclude<U, L[number]>,
  Exclude<L[number], U>,
] extends [never, never]
  ? true
  : { missingFromList: Exclude<U, L[number]>; missingFromSchema: Exclude<L[number], U> };
type Clean<T> = [Exclude<Extract<DeepKeys<T>, Forbidden>, "client_status">] extends [never]
  ? true
  : false;

const ID = {
  binder: "c15521b1-b3dc-450a-9daa-37e51b591d75",
  binder2024: "3f372617-f0ba-4f3a-86f0-ce2ea6ec39c1",
  engagement: "4a800646-417a-4105-bc31-99944567ceb1",
  w2: "732242fd-a890-4e32-9297-9bfcbbeb508f",
  k1: "df7142dc-af29-46f8-b774-4cca4d909eb2",
  c1095: "e8af30f7-c70b-43bf-a4d0-b50f658c6762",
  est: "deeda8b2-3927-47d6-8375-d0341e4f6f2a",
  donations: "cecf4f4e-5ba8-4780-90ce-f798e6c648e7",
  fileW2: "a1fa7d4a-cde5-40db-9c54-e05b42a9ba21",
  fileDon: "293a9acc-2652-48ff-842a-2f9da1b4ba07",
  fileEst1: "467c0714-a9fb-4797-aa59-c1698d242349",
  fileEst2: "11e760a5-a6d5-430a-82b7-075d2a3a0c78",
  fileScan: "071d1481-5649-48e9-9846-6a921f7ea79c",
  batch: "daa4ed3c-3454-4ae4-8628-7225154d1eb0",
  bridge: "e57b37e7-704b-4d09-af2e-ab42fd8cfe33",
  soc1: "a40f9ca3-df62-492c-982a-3add9b872a76",
  balances: "942af46d-1c8d-4358-a2db-0c01afd798c2",
  northwind: "bf3ba33a-183c-44e2-9d66-a3582e62fe86",
} as const;

// The client words, the receipt kinds and the action vocabulary, exhaustively (contract §4).
const CLIENT_WORDS = ["to_do", "done", "ignored", "returned"] as const;
const RECEIPT_KINDS = [
  "uploaded",
  "uploaded_by_other_contact",
  "emailed",
  "rule_linked_pending",
  "received",
] as const;
const ACTIONS = [
  "upload",
  "ignore",
  "undo_ignore",
  "withdraw",
  "mark_done",
  "undo_mark_done",
  "comment",
] as const;
const wordsCovered: Exactly<PortalRowOut["client_status"], typeof CLIENT_WORDS> = true;
const kindsCovered: Exactly<PortalReceiptOut["kind"], typeof RECEIPT_KINDS> = true;
const actionsCovered: Exactly<
  NonNullable<PortalRowOut["allowed_actions"]>[number],
  typeof ACTIONS
> = true;

const W2: PortalRowOut = {
  id: ID.w2,
  engagement_id: ID.engagement,
  title: "2025 W-2 From Mercer Hill Health",
  kind: "request",
  client_status: "done",
  files: [
    {
      id: ID.fileW2,
      name: "Claire_Feld_2025_W2_MercerHill.pdf",
      receipt: { kind: "emailed", on: "2026-08-03" },
      withdrawable: false,
    },
  ],
  allowed_actions: ["comment"],
};
const K1: PortalRowOut = {
  id: ID.k1,
  engagement_id: ID.engagement,
  title: "Schedule K-1 from Ridgeline Property Partners, LP",
  kind: "firm_provided",
  client_status: "to_do",
  allowed_actions: [],
};
const FORM_1095C: PortalRowOut = {
  id: ID.c1095,
  engagement_id: ID.engagement,
  title: "Form 1095-C From Mercer Hill Health",
  kind: "request",
  client_status: "to_do",
  allowed_actions: ["upload", "ignore", "comment"],
};
const DONATIONS: PortalRowOut = {
  id: ID.donations,
  engagement_id: ID.engagement,
  title: "2025 donation receipts and acknowledgment letters",
  kind: "request",
  client_status: "done",
  files: [
    {
      id: ID.fileDon,
      name: "Feld_2025_Donations.pdf",
      receipt: { kind: "uploaded", on: "2026-08-07" },
      withdrawable: true,
    },
  ],
  allowed_actions: ["withdraw", "comment"],
};
const ESTIMATES: PortalRowOut = {
  id: ID.est,
  engagement_id: ID.engagement,
  title: "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
  kind: "request",
  client_status: "to_do",
  uploading_count: 2,
  allowed_actions: ["upload", "ignore", "comment"],
};

// GET /v1/portal/binders/{id}?filter=requested as Claire Feld, Mon Sep 14, 2026 9:24 AM CT (POR-03 a).
const CLAIRE: PortalBinderOut = {
  binder: { id: ID.binder, title: "2025 Binder", year: 2025, closed: false, read_only: false },
  layout: "groups",
  filter: "requested",
  categories: [
    { code: "health_medical", label: "Health & Medical", complete: false, requested: 1 },
    { code: "charitable", label: "Charitable & Donations", complete: true, requested: 1 },
    { code: "education", label: "Education & Student", complete: true, requested: 0 },
  ],
  groups: [
    { code: "w2s", label: "W-2s", category_code: "income", rows: [W2] },
    { code: "k1s", label: "Partnership K-1s", category_code: "business", rows: [K1] },
    {
      code: "health",
      label: "Health insurance",
      category_code: "health_medical",
      rows: [FORM_1095C],
    },
    {
      code: "charity",
      label: "Charitable contributions",
      category_code: "charitable",
      rows: [DONATIONS],
    },
    {
      code: "estimates",
      label: "Estimated tax payments",
      category_code: "other",
      rows: [ESTIMATES],
    },
  ],
  total: 21,
  done_count: 19,
  open_count: 2,
  sorted_count: 37,
  mark_done: { state: "tonal" },
  other_parties: [],
  allowed_actions: ["upload", "mark_done"],
};

// POR-03 c: the two estimated-payment files, rule-linked and waiting for the firm to accept.
const SORTED: PortalRowOut = {
  ...ESTIMATES,
  client_status: "done",
  uploading_count: 0,
  files: [
    {
      id: ID.fileEst1,
      name: "Feld_2025_Estimated_Payments.pdf",
      receipt: { kind: "rule_linked_pending", on: "2026-09-14" },
      withdrawable: true,
    },
    {
      id: ID.fileEst2,
      name: "Feld_2025_IT2105_Confirmations.pdf",
      receipt: { kind: "rule_linked_pending", on: "2026-09-14" },
      withdrawable: true,
    },
  ],
  allowed_actions: ["withdraw", "comment"],
};

// POR-04 d: the 2024 form returned by Kevin Osei (alternate path).
const RETURNED: PortalRequestOut = {
  id: ID.c1095,
  engagement_id: ID.engagement,
  binder_id: ID.binder,
  variant: "request",
  category: { code: "health_medical", label: "Health insurance" },
  title: "Form 1095-C From Mercer Hill Health",
  client_status: "returned",
  requested_on: "2026-02-03",
  guidance:
    "Form 1095-C shows the health coverage Mercer Hill Health offered you each month of 2025. You don't attach it to your return, but we use it to confirm your coverage and that no premium tax credit needs to be repaid.",
  prior_year: { file_name: "Claire_Feld_2024_1095C_MercerHill.pdf", sent_on: "2025-03-03" },
  files: [],
  returned: {
    reason: "wrong_year",
    note: "This is the 2024 form. We need the 2025 Form 1095-C.",
    by_name: "Kevin Osei",
    on: "2026-09-14",
  },
  comment_count: 1,
  allowed_actions: ["upload", "comment"],
};

// GET /v1/portal/room as Sam Ortiz (Keystone Retirement Services), Sep 14 (POR-14 a, abridged).
const ROOM: PortalRoomOut = {
  engagement_label: "Northwind Robotics 401(k) Plan · 2025 audit",
  firm_name: "Brightwater Hale",
  organisation_name: "Keystone Retirement Services",
  uploaded_count: 4,
  total: 9,
  complete: false,
  bands: [
    {
      code: "recordkeeper_reports",
      label: "Recordkeeper reports",
      uploaded: 3,
      total: 5,
      rows: [
        {
          id: ID.balances,
          engagement_id: ID.northwind,
          title: "Schedule of account balances — every participant, 12/31/2025",
          state: "uploaded",
          state_on: "2026-09-02",
          disc: "done",
          allowed_actions: ["comment"],
        },
      ],
    },
    {
      code: "soc1_fees",
      label: "SOC 1 & fees",
      uploaded: 1,
      total: 4,
      rows: [
        {
          id: ID.soc1,
          engagement_id: ID.northwind,
          title: "SOC 1 Type 2 report — Oct 1, 2024 to Sep 30, 2025",
          state: "uploaded",
          state_on: "2026-09-02",
          disc: "done",
          allowed_actions: ["comment"],
        },
        {
          id: ID.bridge,
          engagement_id: ID.northwind,
          title: "Bridge letter — Oct 1 to Dec 31, 2025",
          state: "due",
          state_on: "2026-09-25",
          disc: "ring",
          comment_count: 2,
          allowed_actions: ["upload", "comment"],
        },
      ],
    },
  ],
};

// GET /v1/portal/drops/{batch} after Claire's three-file drop (POR-03 c, d).
const DROP: DropBatchOut = {
  batch_id: ID.batch,
  binder_id: ID.binder,
  settled: true,
  files: [
    {
      file_id: ID.fileEst1,
      file_name: "Feld_2025_Estimated_Payments.pdf",
      outcome: "rule_linked",
      request_item_id: ID.est,
    },
    {
      file_id: ID.fileEst2,
      file_name: "Feld_2025_IT2105_Confirmations.pdf",
      outcome: "rule_linked",
      request_item_id: ID.est,
    },
    { file_id: ID.fileScan, file_name: "Scan_0914.pdf", outcome: "waiting" },
  ],
};

describe("the portal binder as R-01, T-02 and C-01 read it", () => {
  it("serves Claire's binder in the schema, footing 21 = 19 + 2 with 37 sorted", () => {
    expect(validateResponse("get", "/v1/portal/binders/{binder_id}", CLAIRE)).toEqual([]);
    expect(CLAIRE.done_count + CLAIRE.open_count).toBe(CLAIRE.total);
    const open = CLAIRE.groups
      ?.flatMap((g) => g.rows)
      .filter((r) => r.kind === "request" && r.client_status === "to_do");
    expect(open?.map((r) => r.id)).toEqual([ID.c1095, ID.est]);
    expect(open).toHaveLength(CLAIRE.open_count);
  });

  it("lists the open binder and the closed 2024 one read-only", () => {
    const list: PortalBinderListOut = {
      items: [
        CLAIRE.binder,
        { id: ID.binder2024, title: "2024 Binder", year: 2024, closed: true, read_only: true },
      ],
      total: 2,
    };
    expect(validateResponse("get", "/v1/portal/binders", list)).toEqual([]);
  });

  it("carries no firm status, amount, confidence or agent field anywhere", () => {
    const clean: true = true satisfies Clean<PortalBinderOut>;

    expect(clean).toBe(true);
    expect([wordsCovered, kindsCovered, actionsCovered]).toEqual([true, true, true]);
  });

  it("accepts every client word, receipt kind and action the vocabulary names", () => {
    for (const word of CLIENT_WORDS) {
      expect(validateSchema("PortalRowOut", { ...FORM_1095C, client_status: word })).toEqual([]);
    }
    for (const kind of RECEIPT_KINDS) {
      expect(validateSchema("PortalReceiptOut", { kind, on: "2026-09-14" })).toEqual([]);
    }
    expect(
      validateSchema("PortalRowOut", { ...FORM_1095C, allowed_actions: [...ACTIONS] }),
    ).toEqual([]);
  });

  it("refuses a firm status word, an amount, a confidence or an agent field at run time", () => {
    expect(
      validateSchema("PortalRowOut", { ...FORM_1095C, client_status: "requested" }),
    ).toHaveLength(1);
    expect(validateSchema("PortalRowOut", { ...FORM_1095C, status: "uploaded" })).toHaveLength(1);
    expect(validateSchema("PortalRowOut", { ...FORM_1095C, amount: "3200.00" })).toHaveLength(1);
    expect(
      validateSchema("PortalReceiptOut", {
        kind: "rule_linked_pending",
        on: "2026-09-14",
        confidence: 0.94,
      }),
    ).toHaveLength(1);
    expect(validateSchema("PortalReceiptOut", { kind: "matched", on: "2026-09-14" })).toHaveLength(
      1,
    );
    expect(
      validateSchema("PortalRowOut", { ...FORM_1095C, agent_name: "Accrued Agent" }),
    ).toHaveLength(1);
    expect(
      validateSchema("PortalRowOut", { ...FORM_1095C, allowed_actions: ["accept"] }),
    ).toHaveLength(1);
  });

  it("reads a rule link as the client's own upload waiting for the firm (DEC-58 a)", () => {
    expect(validateSchema("PortalRowOut", SORTED)).toEqual([]);
    expect(SORTED.files?.every((f) => f.receipt.kind === "rule_linked_pending")).toBe(true);
  });

  it("shows a firm-provided row with no action and an emailed file without withdraw", () => {
    expect(K1.allowed_actions).toEqual([]);
    expect(W2.files?.[0]?.withdrawable).toBe(false);
    expect(W2.allowed_actions).not.toContain("withdraw");
  });
});

describe("the request sheet (POR-04) and the undos", () => {
  it("serves the returned 1095-C with the firm's note, name and date", () => {
    expect(validateResponse("get", "/v1/portal/request-items/{item_id}", RETURNED)).toEqual([]);
    expect(RETURNED.returned?.reason).toBe("wrong_year");
  });

  it("types the question and decision slots without serving them", () => {
    expect(validateSchema("PortalRequestOut", { ...RETURNED, variant: "question" })).toEqual([]);
    expect(
      validateSchema("PortalRequestOut", { ...RETURNED, variant: "review_point" }),
    ).toHaveLength(1);
  });

  it("answers an undo in client words, never the firm code", () => {
    const ignore: IgnoreUndoneOut = {
      request_item_id: ID.c1095,
      client_status: "to_do",
      undone_at: "2026-09-14T14:30:00Z",
    };
    const markDone: MarkDoneUndoneOut = {
      binder_id: ID.binder,
      mark_done: "tonal",
      undone_at: "2026-09-14T14:31:00Z",
    };
    expect(
      validateResponse("post", "/v1/portal/request-items/{item_id}/ignore/undo", ignore),
    ).toEqual([]);
    expect(
      validateResponse("post", "/v1/portal/binders/{binder_id}/mark-done/undo", markDone),
    ).toEqual([]);
    expect(
      validateSchema("IgnoreUndoneOut", { ...ignore, client_status: "requested" }),
    ).toHaveLength(1);
  });
});

describe("drops and the third-party room (POR-03 c, d; POR-14)", () => {
  it("polls a drop batch to two rule links and one file for the firm to sort", () => {
    expect(validateResponse("get", "/v1/portal/drops/{batch_id}", DROP)).toEqual([]);
    expect(DROP.files.map((f) => f.outcome)).toEqual(["rule_linked", "rule_linked", "waiting"]);
  });

  it("serves only Sam's delegated items, 4 of 9, in bands", () => {
    expect(validateResponse("get", "/v1/portal/room", ROOM)).toEqual([]);
    expect(ROOM.bands.reduce((n, b) => n + b.total, 0)).toBe(ROOM.total);
    expect(ROOM.bands.reduce((n, b) => n + b.uploaded, 0)).toBe(ROOM.uploaded_count);
  });

  it("refuses anything outside the delegated shape at run time", () => {
    expect(validateSchema("PortalRoomOut", { ...ROOM, binder_id: ID.binder })).toHaveLength(1);
    expect(
      validateSchema("PortalRoomOut", { ...ROOM, other_parties: ["Harborline"] }),
    ).toHaveLength(1);
    const row = ROOM.bands[1]?.rows[1];
    expect(validateSchema("PortalRoomRowOut", { ...row, client_status: "to_do" })).toHaveLength(1);
  });

  it("suggests a request from a file name only", () => {
    const answer: RoomSuggestOut = {
      suggestions: [
        { file_name: "Keystone_bridge_letter_Q4_2025.pdf", request_item_id: ID.bridge },
      ],
    };
    expect(validateResponse("post", "/v1/portal/room/suggest", answer)).toEqual([]);
    expect(validateSchema("RoomSuggestIn", { file_names: ["a.pdf"], content: "…" })).toHaveLength(
      1,
    );
  });
});
