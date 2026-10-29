// FIL-01's Files seed at E0, Mon Sep 14, 2026, 9:24 AM CT (N-01-T16; docs/screens/FIL-01.md; the
// FIL-01 handoff spec and revision R2), in the C-shapes the Files read model answers
// (`docs/contracts/files-browser.md`): Ridgeline Property Partners, LP's tree and its TY2025
// Form 1065 Source documents (12 documents, 7 virtual; the three mortgage interest statements foot
// to 512,400 and tie to 5500), the Iyer superseded 1099-DIV (c), the Collins TY2023 folder on hold
// (d), the Meridian sealed archive (e, fixture-only), and the empty Signed authorizations folder
// (g). Amounts are decimal strings; nothing here adds them (the tie total is the server's).

import type {
  AccessLogRow,
  DrawerOut,
  FileRow,
  FileTreeOut,
  TreeNode,
  VirtualChild,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const RIDGELINE = stableId("client:ridgeline");
export const RIDGELINE_1065 = stableId("work-item:ridgeline:ty2025:1065");
export const IYER_1040 = stableId("work-item:iyer:ty2025:1040");
export const COLLINS_1040_2023 = stableId("work-item:collins:ty2023:1040");
export const MERIDIAN_AUDIT = stableId("work-item:meridian:fy2025:audit");

export const SOURCE_DOCS = `folder:${RIDGELINE_1065}:source_documents`;
export const SIGNED_AUTHORIZATIONS = `folder:${RIDGELINE_1065}:signed_authorizations`;
export const IYER_SOURCE = `folder:${IYER_1040}:source_documents`;
export const COLLINS_SOURCE = `folder:${COLLINS_1040_2023}:source_documents`;
export const MERIDIAN_ARCHIVE = `folder:${MERIDIAN_AUDIT}:workpapers`;

const FOLDERS = [
  "source_documents",
  "workpapers",
  "correspondence",
  "deliverables",
  "signed_authorizations",
] as const;

function node(
  ref: string,
  kind: TreeNode["kind"],
  label: string,
  count: number,
  children: TreeNode[] = [],
  extra: Partial<TreeNode> = {},
): TreeNode {
  return {
    ref,
    kind,
    label,
    folder_kind: null,
    count,
    has_children: children.length > 0,
    on_hold: false,
    locked: false,
    children,
    ...extra,
  };
}

function folders(workItem: string, counts: readonly number[], extra: Partial<TreeNode> = {}) {
  return FOLDERS.map((kind, i) =>
    node(`folder:${workItem}:${kind}`, "folder", kind, counts[i] ?? 0, [], {
      folder_kind: kind,
      ...extra,
    }),
  );
}

/** The tree Olivia Brandt sees with Ridgeline open (FIL-01a), and the other clients collapsed. */
export const RIDGELINE_TREE: FileTreeOut = {
  nodes: [
    node(`client:${RIDGELINE}`, "client", "Ridgeline Property Partners, LP", 31, [
      node(`permanent:${RIDGELINE}`, "permanent_file", "Permanent file", 6),
      node(`year:${RIDGELINE}:2026`, "year", "2026", 1, [
        node(
          `work_item:${stableId("work-item:ridgeline:cost-seg")}`,
          "work_item",
          "Ridgeline cost segregation & §754 analysis",
          1,
        ),
      ]),
      node(`year:${RIDGELINE}:2025`, "year", "2025", 24, [
        node(
          `work_item:${RIDGELINE_1065}`,
          "work_item",
          "TY2025 Form 1065",
          24,
          folders(RIDGELINE_1065, [12, 3, 4, 5, 0]),
        ),
      ]),
      node(`year:${RIDGELINE}:2024`, "year", "2024", 0, [
        node(
          `work_item:${stableId("work-item:ridgeline:ty2024")}`,
          "work_item",
          "TY2024 Form 1065",
          0,
        ),
      ]),
    ]),
    ...[
      "Jonah & Claire Feld",
      "Meera Shah",
      "Northwind Robotics 401(k) Plan",
      "Copperleaf Coffee Roasters, Inc.",
      "Calloway Family Trust",
    ].map((name) => {
      const id = stableId(`client:${name}`);
      return { ...node(`client:${id}`, "client", name, 0), has_children: true };
    }),
  ],
};

export const IYER_TREE: FileTreeOut = {
  nodes: [
    node(`client:${stableId("client:iyer")}`, "client", "Priyanka & Sam Iyer", 2, [
      node(`year:${stableId("client:iyer")}:2025`, "year", "2025", 2, [
        node(
          `work_item:${IYER_1040}`,
          "work_item",
          "TY2025 Form 1040",
          2,
          folders(IYER_1040, [2]),
        ),
      ]),
    ]),
  ],
};

export const COLLINS_TREE: FileTreeOut = {
  nodes: [
    node(`client:${stableId("client:collins")}`, "client", "Wren & Avery Collins", 4, [
      node(`year:${stableId("client:collins")}:2023`, "year", "2023", 4, [
        node(
          `work_item:${COLLINS_1040_2023}`,
          "work_item",
          "TY2023 Form 1040",
          4,
          folders(COLLINS_1040_2023, [4], { on_hold: true }),
          { on_hold: true },
        ),
      ]),
    ]),
  ],
};

export const MERIDIAN_TREE: FileTreeOut = {
  nodes: [
    node(`client:${stableId("client:meridian")}`, "client", "Meridian Tool & Die, Inc.", 3, [
      node(`year:${stableId("client:meridian")}:2025`, "year", "2025", 3, [
        node(
          `work_item:${MERIDIAN_AUDIT}`,
          "work_item",
          "FY2025 FS audit",
          3,
          folders(MERIDIAN_AUDIT, [0, 3], { locked: true }),
          { locked: true },
        ),
      ]),
    ]),
  ],
};

// --- Ridgeline TY2025 Form 1065 · Source documents (FIL-01a) -----------------------------------

export const MORTGAGE = stableId("evidence:ridgeline:mortgage-interest-2025");
export const ROOF = stableId("evidence:ridgeline:elm-roof-invoice");

const MORTGAGE_CHILDREN: VirtualChild[] = [
  ["Interest statement · Lakeview Credit Union · Elm Street", 1, 3, "214600"],
  ["Interest statement · Front Range Bank · Larimer Lofts", 4, 6, "168300"],
  ["Interest statement · Kingsbridge Savings Bank · Bergen Street", 7, 9, "129500"],
].map(([label, first, last, amount]) => ({
  id: stableId(`virtual:mortgage:${String(first)}`),
  label: String(label),
  first_page: Number(first),
  last_page: Number(last),
  amount: String(amount),
}));

const PM_CHILDREN: VirtualChild[] = ["Q1", "Q2", "Q3", "Q4"].map((q, i) => ({
  id: stableId(`virtual:pm:${q}`),
  label: `Property management statement · ${q}`,
  first_page: i * 2 + 1,
  last_page: i * 2 + 2,
  amount: null,
}));

function row(
  key: string,
  title: string,
  classification: string,
  channel: FileRow["channel"],
  supports: string | null,
  status: FileRow["status"] = "accepted",
  children: VirtualChild[] = [],
): FileRow {
  return {
    evidence_item_id:
      key === "mortgage"
        ? MORTGAGE
        : key === "roof"
          ? ROOF
          : stableId(`evidence:ridgeline:${key}`),
    version_id: stableId(`version:ridgeline:${key}`),
    display_name: title,
    classification_label: classification,
    channel,
    status,
    superseded_by_name: null,
    superseded_on: null,
    supports,
    received_at: "2026-09-03T15:02:00Z",
    virtual_children: children,
  };
}

export const RIDGELINE_SOURCE_ROWS: FileRow[] = [
  row(
    "tb",
    "Ridgeline_QBO_TrialBalance_2025.xlsx",
    "Trial balance export",
    "retrieval",
    "01 Trial Balance",
  ),
  row(
    "muni",
    "Harborline_MuniBondFund_Dec2025.pdf",
    "Fund statement",
    "portal",
    "06 Schedule K!C31",
  ),
  row(
    "mortgage",
    "Mortgage_Interest_Statements_2025.pdf",
    "Lender interest statements",
    "email",
    "03 Liabilities!C12:C14",
    "accepted",
    MORTGAGE_CHILDREN,
  ),
  row(
    "rent",
    "Rent_Roll_Dec2025_AllProperties.xlsx",
    "Rent roll",
    "portal",
    "Form 8825 rents 3,776,500",
  ),
  row(
    "pm",
    "PropertyMgmt_Statements_2025.pdf",
    "Property management statements",
    "portal",
    "5200 Mgmt fees 164,000",
    "accepted",
    PM_CHILDREN,
  ),
  row(
    "parking",
    "Larimer_Parking_Invoice_Feb2025.pdf",
    "Invoice — fixed asset",
    "portal",
    "02 Fixed Assets · 180,000",
  ),
  row(
    "appliances",
    "Bergen_Appliances_Invoice_Aug2025.pdf",
    "Invoice — fixed asset",
    "portal",
    "02 Fixed Assets · 64,000",
  ),
  row(
    "roof",
    "Elm_Street_Roof_Invoice_LakesideRoofing.pdf",
    "Invoice — fixed asset",
    "portal",
    null,
    "processing",
  ),
  row(
    "capital-call",
    "Feld_Capital_Call_Wire_Mar2025.pdf",
    "Bank confirmation",
    "portal",
    "04 Partner Txns · 250,000",
  ),
  row(
    "distributions",
    "Distribution_Wires_Dec15_2025.pdf",
    "Bank confirmation",
    "portal",
    "04 Partner Txns · 600,000",
  ),
  row(
    "prior-1065",
    "Ridgeline_2024_Form1065.pdf",
    "Prior-year return",
    "import",
    "Pro forma 2025P:Ridgeline:V2",
  ),
  row(
    "deposits",
    "Tenant_Deposits_Ledger_Bergen_2024.xlsx",
    "Deposit ledger",
    "portal",
    null,
    "needs_review",
  ),
];

export const IYER_ROWS: FileRow[] = [
  {
    ...row(
      "iyer-corrected",
      "Iyer_2025_1099DIV_Halvard_Corrected.pdf",
      "Form 1099-DIV",
      "portal",
      null,
    ),
    evidence_item_id: stableId("evidence:iyer:1099div"),
    received_at: "2026-09-14T14:10:00Z",
  },
  {
    ...row(
      "iyer-march",
      "Iyer_2025_1099DIV_Halvard.pdf",
      "Form 1099-DIV",
      "portal",
      null,
      "superseded",
    ),
    evidence_item_id: stableId("evidence:iyer:1099div"),
    superseded_by_name: "Iyer_2025_1099DIV_Halvard_Corrected.pdf",
    superseded_on: "2026-09-14",
    received_at: "2026-03-02T16:00:00Z",
  },
];

export const COLLINS_ROWS: FileRow[] = [
  "W-2 · Collins Dental",
  "1099-INT · Front Range Bank",
  "1099-B · Halsey Brokerage",
  "Form 1040 (as filed)",
].map((title, i) => ({
  ...row(`collins-${String(i)}`, title, "Tax document", "portal", null, "on_hold"),
  evidence_item_id: stableId(`evidence:collins:${String(i)}`),
}));

export const MERIDIAN_ROWS: FileRow[] = ["A Planning", "B Risk assessment", "C Completion"].map(
  (t, i) => ({
    ...row(`meridian-${String(i)}`, `${t}.pdf`, "Archived workpaper", "generated", null),
    evidence_item_id: stableId(`evidence:meridian:${String(i)}`),
  }),
);

// --- Drawers -----------------------------------------------------------------------------------

const RETENTION_TAX: DrawerOut["retention"] = {
  policy_label: "Client tax records · 7 years after filing",
  eligible_on: "2033-09-15",
  hold_label: null,
  hold_placed_by: null,
  hold_placed_on: null,
};

export function mortgageDrawer(over: Partial<DrawerOut> = {}): DrawerOut {
  return {
    evidence_item_id: MORTGAGE,
    display_name: "Mortgage_Interest_Statements_2025.pdf",
    status: "accepted",
    folder_kind: "source_documents",
    scope: "engagement",
    page_count: 9,
    size_bytes: 2_516_582,
    fingerprint: "9f2c4b1e7a0d3c5f8e6b2a1d9c7e5f3a1b9d7c5e3f1a9b7d5c3e1f9a7b5d41ab",
    masked_tin: { kind: "ein", last4: "0287", presence: "on_file" },
    thumbnail_ref: null,
    virtual_children: MORTGAGE_CHILDREN,
    tie: { total: "512400", account_number: "5500", ties: true },
    linked_to: [
      {
        kind: "request",
        label: "Mortgage interest statements (3 properties) · Received ✓",
        route: "/binders",
      },
      { kind: "workpaper_cell", label: "03 Liabilities!C12:C14", route: "/workpapers" },
      { kind: "return_line", label: "TY2025 Form 1065 · Form 8825 line 9", route: "/tax-returns" },
    ],
    versions: [
      {
        id: stableId("version:ridgeline:mortgage"),
        version_no: 1,
        file_name: "Mortgage_Interest_Statements_2025.pdf",
        channel: "email",
        created_at: "2026-09-03T15:02:00Z",
        superseded: false,
      },
    ],
    retention: RETENTION_TAX,
    sign_off_slots: [
      { level: "preparer", initials: null, signed_at: null },
      { level: "reviewer", initials: null, signed_at: null },
    ],
    client_access: "off",
    allowed_actions: [],
    ...over,
  };
}

export function roofDrawer(): DrawerOut {
  return mortgageDrawer({
    evidence_item_id: ROOF,
    display_name: "Elm_Street_Roof_Invoice_LakesideRoofing.pdf",
    status: "processing",
    page_count: null,
    masked_tin: null,
    virtual_children: [],
    tie: null,
    linked_to: [],
    versions: [
      {
        id: stableId("version:ridgeline:roof"),
        version_no: 1,
        file_name: "Elm_Street_Roof_Invoice_LakesideRoofing.pdf",
        channel: "portal",
        created_at: "2026-09-14T13:47:00Z",
        superseded: false,
      },
    ],
  });
}

export function collinsDrawer(): DrawerOut {
  return mortgageDrawer({
    evidence_item_id: stableId("evidence:collins:0"),
    display_name: "W-2 · Collins Dental",
    status: "on_hold",
    page_count: null,
    masked_tin: null,
    virtual_children: [],
    tie: null,
    linked_to: [],
    retention: {
      policy_label: "Client tax records · 7 years after filing",
      eligible_on: null,
      hold_label: "On hold · IRS CP2000 TY2023 disagreed (N3)",
      hold_placed_by: "Victor Hammond",
      hold_placed_on: "2026-08-12",
    },
  });
}

export const MORTGAGE_ACCESS_LOG: AccessLogRow[] = [
  {
    occurred_at: "2026-09-14T14:20:00Z",
    actor_display: "Samuel Ito",
    verb: "viewed p. 4",
    version_no: 1,
  },
  {
    occurred_at: "2026-09-10T20:44:00Z",
    actor_display: "Olivia Brandt via Agent",
    verb: "extracted 3 values",
    version_no: 1,
  },
  {
    occurred_at: "2026-09-03T15:02:00Z",
    actor_display: "Grace Holloway",
    verb: "filed from Inbox",
    version_no: 1,
  },
  {
    occurred_at: "2026-09-03T14:58:00Z",
    actor_display: "Received",
    verb: "by email",
    version_no: 1,
  },
];
