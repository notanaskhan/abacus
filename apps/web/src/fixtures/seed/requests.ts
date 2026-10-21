// The three request lists of the audit-core slice, as RequestItemOut with the C2 request words
// (draft · requested · uploaded · received · returned · not_applicable; `open` and
// `needs_revision` are retired):
// - Northwind's PBC list: 24 requests, 11 received (AUD-03 spec, "Totals: 24 requests; 11
//   received; 1 needs review; 12 requested");
// - Granite Peak's FS PBC list: 41 requests, all still draft while the letter is out (ENG-01:
//   portal requests stay held until the letter is signed, G3);
// - the Feld 2025 Binder: 7 requests, 5 of 7 satisfied, 2 open (BND-02 spec, Intake 2).

import type { RequestItemOut } from "@abacus/api-client";
import { onDate } from "./clock";
import { PORTAL_USERS } from "./portal";
import { stableId } from "./prng";

type Status = RequestItemOut["status"];

export interface SeedRequest {
  item: RequestItemOut;
  /** Who answers it: a person or an organisation (the portal user, when there is one, is the assignee). */
  owner: string;
}

type Row = readonly [
  category: string,
  title: string,
  status: Status,
  dueOn: string | null,
  owner: string,
];

const NORTHWIND: readonly Row[] = [
  [
    "Plan documents",
    "Trust agreement — Harborline Trust Company",
    "requested",
    "2026-09-18",
    "Harborline Trust Company",
  ],
  [
    "Plan documents",
    "IRS opinion letter on the pre-approved plan document",
    "requested",
    "2026-09-18",
    "Dana Kowalski",
  ],
  ["Plan documents", "Plan document & amendments", "received", null, "Dana Kowalski"],
  ["Plan documents", "Adoption agreement", "received", null, "Dana Kowalski"],
  ["Plan documents", "Summary plan description", "received", null, "Dana Kowalski"],
  [
    "Trust / Recordkeeper Reports",
    "Certified trust report (full year, signed)",
    "uploaded",
    null,
    "Harborline Trust Company",
  ],
  [
    "Trust / Recordkeeper Reports",
    "Withdrawals / distributions report",
    "requested",
    "2026-09-18",
    "Keystone Retirement Services",
  ],
  [
    "Trust / Recordkeeper Reports",
    "Summary of net trust assets",
    "received",
    null,
    "Harborline Trust Company",
  ],
  [
    "Trust / Recordkeeper Reports",
    "Schedule of Account Balances",
    "received",
    null,
    "Keystone Retirement Services",
  ],
  [
    "Trust / Recordkeeper Reports",
    "Annual loan balance roll-forward",
    "received",
    null,
    "Keystone Retirement Services",
  ],
  [
    "Trust / Recordkeeper Reports",
    "Brokerage / SDBA asset detail — BrokerWindow",
    "received",
    null,
    "Keystone Retirement Services",
  ],
  ["Census & Payroll", "W-3 Form", "requested", "2026-09-18", "Dana Kowalski"],
  ["Census & Payroll", "Opt-Out Elections", "requested", "2026-09-18", "Dana Kowalski"],
  ["Census & Payroll", "Pay Rate Authorizations", "requested", "2026-09-18", "Dana Kowalski"],
  ["Census & Payroll", "YTD payroll register", "requested", "2026-09-18", "PayGrid Payroll"],
  ["Census & Payroll", "Employee Census File", "received", null, "Dana Kowalski"],
  ["Census & Payroll", "Contribution Reports — PayGrid", "received", null, "PayGrid Payroll"],
  ["Census & Payroll", "Quarterly 941 Forms", "received", null, "PayGrid Payroll"],
  [
    "Form 5500 & SOC 1",
    "Bridge letter — Keystone, Oct–Dec 2025",
    "requested",
    "2026-09-25",
    "Keystone Retirement Services",
  ],
  [
    "Form 5500 & SOC 1",
    "Draft Form 5500 & Schedule H — Summit Plan Administrators",
    "requested",
    "2026-09-30",
    "Summit Plan Administrators",
  ],
  [
    "Form 5500 & SOC 1",
    "ERISA 408(b)(2) fee disclosure",
    "requested",
    "2026-09-25",
    "Keystone Retirement Services",
  ],
  [
    "Form 5500 & SOC 1",
    "SOC 1 Type 2 — Keystone Retirement Services",
    "received",
    null,
    "Keystone Retirement Services",
  ],
  [
    "Cash",
    "Schedule of cash accounts, confirmations, and statements",
    "requested",
    "2026-09-18",
    "Harborline Trust Company",
  ],
  [
    "Compliance & other",
    "Participant Complaints Log and Support",
    "requested",
    "2026-09-18",
    "Dana Kowalski",
  ],
];

// Default FS-audit PBC catalogue (domain-audit.md Appendix A.1), the first n requests of each
// category so the list reads 41. The count is the handoff's (ENG-12: "41 requests"); the titles
// are the catalogue's, because the handoff gives no list.
const FS_CATALOGUE: readonly (readonly [
  category: string,
  take: number,
  titles: readonly string[],
])[] = [
  [
    "General & governance",
    7,
    [
      "TB (unadjusted) and GL detail for the year",
      "PY audited FS",
      "Board/committee minutes",
      "Org chart & ownership/cap table",
      "Significant contracts and agreements",
      "List of related parties",
      "List of legal counsel",
      "Insurance summary",
      "Accounting policies memo",
      "List of bank accounts and authorized signers",
    ],
  ],
  [
    "Cash",
    3,
    [
      "Bank statements (year-end month + subsequent month)",
      "Bank reconciliations",
      "Confirmation authorizations (signature)",
      "Restricted cash support",
    ],
  ],
  [
    "Receivables & revenue",
    5,
    [
      "AR aging at year end",
      "Subsequent receipts listing",
      "Allowance (CECL) calculation",
      "Revenue contracts (above threshold)",
      "Sales register",
      "Credit memos after year end",
      "Deferred revenue rollforward",
    ],
  ],
  [
    "Inventory",
    3,
    [
      "Count instructions and count sheets",
      "Priced inventory listing",
      "Costing support",
      "Reserve calculation",
      "Cutoff documents (receiving/shipping logs)",
    ],
  ],
  ["Prepaids & other assets", 1, ["Prepaid schedules with invoices", "Deposits"]],
  [
    "PP&E & leases",
    3,
    [
      "Fixed-asset rollforward",
      "Additions/disposals support",
      "Depreciation schedule",
      "Lease schedule (ASC 842) and new leases",
    ],
  ],
  ["Investments", 2, ["Broker/custodian statements", "Fair value support", "Investment policy"]],
  [
    "Payables & accruals",
    2,
    [
      "AP aging",
      "Subsequent disbursements listing (unrecorded liabilities)",
      "Calculations of unpaid payroll, bonus, PTO and interest",
    ],
  ],
  [
    "Debt & equity",
    3,
    [
      "Debt agreements & amendments",
      "Amortization schedules",
      "Covenant compliance calculations",
      "Equity rollforward",
      "Stock comp support",
    ],
  ],
  [
    "Payroll",
    3,
    ["Payroll registers", "Forms 941/W-3", "Bonus/commission calculations", "Benefits invoices"],
  ],
  [
    "Income taxes",
    2,
    ["Tax provision workpapers", "Returns filed", "Uncertain-tax-position memo"],
  ],
  [
    "IT",
    3,
    [
      "System inventory",
      "User access listings & terminations",
      "Change logs",
      "SOC reports for relevant service organizations + bridge letters",
    ],
  ],
  [
    "Completion",
    4,
    [
      "Subsequent-events questionnaire",
      "Going concern forecast (if indicated)",
      "Draft FS & notes (if client-prepared)",
      "Rep letter signatories",
    ],
  ],
];

const FELD: readonly (readonly [
  category: string,
  title: string,
  status: Status,
  createdOn: string,
  dueOn: string,
  owner: string,
])[] = [
  [
    "Income Sources",
    "2025 W-2 From Mercer Hill Health",
    "received",
    "2026-02-03",
    "2026-03-15",
    "Claire Feld",
  ],
  [
    "Income Sources",
    "2025 Consolidated 1099 From Halvard Securities (Acct ••3318)",
    "received",
    "2026-02-03",
    "2026-03-15",
    "Jonah Feld",
  ],
  // Firm-provided: the Ridgeline K-1 arrives as an internal draft handoff, which satisfies the row.
  [
    "Income Sources",
    "Schedule K-1 from Ridgeline Property Partners, LP",
    "received",
    "2026-02-03",
    "2026-03-15",
    "Brightwater Hale",
  ],
  [
    "Home & Property",
    "2025 Form 1098 From Hudson Mutual Savings (co-op loan)",
    "received",
    "2026-02-03",
    "2026-03-15",
    "Claire Feld",
  ],
  [
    "Health & Medical",
    "Form 1095-C From Mercer Hill Health",
    "requested",
    "2026-02-03",
    "2026-03-15",
    "Claire Feld",
  ],
  [
    "Charitable & Donations",
    "2025 donation receipts and acknowledgment letters",
    "received",
    "2026-02-03",
    "2026-03-15",
    "Claire Feld",
  ],
  [
    "Other Activity",
    "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
    "requested",
    "2026-09-01",
    "2026-09-21",
    "Claire Feld",
  ],
];

function assigneeOf(owner: string): string | null {
  const user = PORTAL_USERS.find((u) => u.name === owner || u.org === owner);
  return user === undefined || user.role === "tcwg" ? null : user.id;
}

function item(
  engagementId: string,
  label: string,
  position: number,
  fields: {
    category: string;
    title: string;
    status: Status;
    createdAt: string;
    dueOn: string | null;
    visible: boolean;
    owner: string;
  },
): SeedRequest {
  return {
    owner: fields.owner,
    item: {
      id: stableId(`request:${label}:${String(position)}`),
      engagement_id: engagementId,
      audit_area: fields.category,
      description: fields.title,
      status: fields.status,
      created_at: fields.createdAt,
      due_on: fields.dueOn,
      client_visible: fields.visible,
      client_assignee_user_id: assigneeOf(fields.owner),
    },
  };
}

export function northwindRequests(engagementId: string): SeedRequest[] {
  return NORTHWIND.map(([category, title, status, dueOn, owner], i) =>
    item(engagementId, "northwind", i + 1, {
      category,
      title,
      status,
      createdAt: onDate("2026-09-01"), // "Requested Sep 1"
      dueOn,
      visible: true,
      owner,
    }),
  );
}

export function granitePeakRequests(engagementId: string): SeedRequest[] {
  const out: SeedRequest[] = [];
  for (const [category, take, titles] of FS_CATALOGUE) {
    for (const title of titles.slice(0, take)) {
      out.push(
        item(engagementId, "granite-peak", out.length + 1, {
          category,
          title,
          status: "draft",
          createdAt: onDate("2026-08-31"),
          dueOn: null,
          visible: false, // draft: firm only, never client-visible
          owner: "Luis Ferrante",
        }),
      );
    }
  }
  return out;
}

export function feldRequests(engagementId: string): SeedRequest[] {
  return FELD.map(([category, title, status, createdOn, dueOn, owner], i) =>
    item(engagementId, "feld", i + 1, {
      category,
      title,
      status,
      createdAt: onDate(createdOn),
      dueOn,
      visible: true,
      owner,
    }),
  );
}
