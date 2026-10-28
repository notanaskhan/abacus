// The signatures hub at E0 (N-02-T10; SIG-01 spec.md, blueprint 01 §9.7): the 17 envelopes out
// for signature (E1 to E17; the ten 8879-family rows are F-06-T02's `tax/envelopes.ts`, extended
// here with what SIG-01 draws), the two To send drafts (Harborview's 8879-PE, E18; the
// agent-drafted Form 2848), the 30-day Completed list, the Expired consent and the Declined variant,
// and E13's Ridgeline letter fee (ENG-04: $6,500 + $12,000 = $18,500). Verbatim from the handoff;
// figures are whole-dollar decimal strings the browser never adds (signatures.foot.test.ts does).
import { ENVELOPES } from "./tax/envelopes";

export type HubStatus =
  "draft" | "sent" | "viewed" | "partially_signed" | "completed" | "declined" | "expired";

export interface HubSigner {
  name: string;
  signed: boolean;
}

export interface HubEnvelope {
  key: string;
  title: string;
  client: string;
  purpose: "form_8879" | "engagement_letter" | "rep_letter" | "consent_7216" | "form_2848";
  signers: readonly HubSigner[];
  sent: string | null; // ISO date
  viewed: string | null;
  due: string | null; // null: "Dated as of report date"
  workItem: string;
  status: HubStatus;
  /** E2's amber note; a draft's needs-review note; a declined signer's reason. */
  note?: string;
  draftedBy?: string;
  outcome?: string; // Completed: what it unblocked ("Filed Sep 11", "Accepted")
}

const s = (name: string, signed = false): HubSigner => ({ name, signed });

/** SIG-01's per-row facts for the ten 8879-family envelopes, in E-number order. */
const TAX_ROWS: Readonly<Record<string, { viewed: string | null; workItem: string }>> = {
  E1: { viewed: "2026-09-10", workItem: "TY2025 Form 1040 · Varga" },
  E2: { viewed: "2026-09-13", workItem: "TY2025 Form 1040 · Kowal" },
  E3: { viewed: null, workItem: "TY2025 Form 1065 · Kestrel" },
  E4: { viewed: "2026-09-11", workItem: "TY2025 Form 1041 · Pryor" },
  E5: { viewed: null, workItem: "TY2025 Form 1040 · Abbott" },
  E6: { viewed: "2026-09-08", workItem: "TY2025 Form 1040 · Kapoor" },
  E7: { viewed: "2026-09-12", workItem: "TY2025 Form 1120-S · Larkspur" },
  E8: { viewed: null, workItem: "TY2025 Form 1040 · Brandvold" },
  E9: { viewed: null, workItem: "TY2025 Form 1040 · Farouk" },
  E10: { viewed: null, workItem: "TY2025 Form 1120 · Brightline" },
};

/** SIG-01 capitalises role signers ("President", "Trustee"); the tax seed keeps them lower. */
const capital = (name: string): string =>
  name === name.toLowerCase() ? name.charAt(0).toUpperCase() + name.slice(1) : name;

const TAX: readonly HubEnvelope[] = ENVELOPES.map((e) => {
  const row = TAX_ROWS[e.key];
  if (row === undefined) throw new Error(`no SIG-01 row for ${e.key}`);
  return {
    key: e.key,
    title: e.title,
    client: e.client,
    purpose: "form_8879",
    signers: e.signers.map((x) => s(capital(x.name), x.signed)),
    sent: e.sent,
    viewed: row.viewed,
    due: e.due,
    workItem: row.workItem,
    status: e.status === "partially_signed" ? "partially_signed" : (e.status as HubStatus),
    ...(e.key === "E2" ? { note: "Identity check locked" } : {}),
  };
});

const LETTERS: readonly HubEnvelope[] = [
  {
    key: "E11",
    title: "Engagement letter · PY2025 EBP audit · Fairhaven Foods 401(k) Plan",
    client: "Fairhaven Foods 401(k) Plan",
    purpose: "engagement_letter",
    signers: [s("Plan administrator"), s("MO")],
    sent: "2026-09-08",
    viewed: null,
    due: "2026-09-18",
    workItem: "PY2025 EBP audit · Fairhaven",
    status: "sent",
  },
  {
    key: "E12",
    title: "Engagement letter · 2026 Close (from Oct) · Bluestem Analytics",
    client: "Bluestem Analytics",
    purpose: "engagement_letter",
    signers: [s("Arjun Mehta"), s("PR")],
    sent: "2026-09-11",
    viewed: "2026-09-12",
    due: "2026-09-25",
    workItem: "2026 Close · Bluestem",
    status: "viewed",
  },
  {
    key: "E13",
    title: "Engagement letter · Ridgeline cost segregation & §754 analysis",
    client: "Ridgeline",
    purpose: "engagement_letter",
    signers: [s("Owen Calder"), s("DR")],
    sent: "2026-09-14",
    viewed: null,
    due: "2026-09-24",
    workItem: "Advisory project · Ridgeline",
    status: "sent",
  },
  {
    key: "E14",
    title: "Engagement letter · FY2026 FS audit · Granite Peak Outdoor Supply",
    client: "Granite Peak Outdoor Supply",
    purpose: "engagement_letter",
    signers: [s("Luis Ferrante", true), s("MO")],
    sent: "2026-09-02",
    viewed: "2026-09-03",
    due: "2026-09-16",
    workItem: "FY2026 FS audit · Granite Peak",
    status: "partially_signed",
  },
  {
    key: "E15",
    title: "Rep letter · PY2025 EBP audit · Cobalt Ridge Manufacturing 401(k) Plan",
    client: "Cobalt Ridge Manufacturing 401(k) Plan",
    purpose: "rep_letter",
    signers: [s("Plan administrator")],
    sent: "2026-09-11",
    viewed: null,
    due: null,
    workItem: "PY2025 EBP audit · Cobalt Ridge",
    status: "sent",
  },
  {
    key: "E16",
    title: "Rep letter · PY2025 EBP audit · Halden Health 403(b) Plan",
    client: "Halden Health 403(b) Plan",
    purpose: "rep_letter",
    signers: [s("Plan administrator")],
    sent: "2026-09-12",
    viewed: "2026-09-13",
    due: null,
    workItem: "PY2025 EBP audit · Halden",
    status: "viewed",
  },
  {
    key: "E17",
    title: "§7216 consents (use · AI disclosure — 2 documents) · Morgan & Kai Ferris",
    client: "Morgan & Kai Ferris",
    purpose: "consent_7216",
    signers: [s("Morgan", true), s("Kai")],
    sent: "2026-09-09",
    viewed: "2026-09-09",
    due: "2026-09-23",
    workItem: "TY2025 Form 1040 · Ferris",
    status: "partially_signed",
  },
];

/** Out for signature (SIG-01 a): the 17, in the handoff's due order. */
export const OUT: readonly HubEnvelope[] = [...TAX, ...LETTERS].sort((a, b) =>
  (a.due ?? "9999") === (b.due ?? "9999")
    ? Number(a.key.slice(1)) - Number(b.key.slice(1))
    : (a.due ?? "9999").localeCompare(b.due ?? "9999"),
);

/** To send (SIG-01 b): the two drafts. */
export const TO_SEND: readonly HubEnvelope[] = [
  {
    key: "E18",
    title: "Form 8879-PE · TY2025 · Harborview Dental Properties, LP",
    client: "Harborview Dental Properties, LP",
    purpose: "form_8879",
    signers: [s("Dr. Sofia Lindqvist")],
    sent: null,
    viewed: null,
    due: "2026-09-15",
    workItem: "TY2025 Form 1065 · Harborview",
    status: "draft",
    draftedBy: "Grace Holloway",
  },
  {
    key: "D2",
    title: "Form 2848 · Aurelio Santos · IRS CP14 TY2024",
    client: "Aurelio Santos",
    purpose: "form_2848",
    signers: [s("Aurelio Santos"), s("DR")],
    sent: null,
    viewed: null,
    due: null,
    workItem: "IRS CP14 TY2024 · Santos",
    status: "draft",
    draftedBy: "Accrued Agent",
    note: "Needs review — notice N5 blocked until filed",
  },
];

/** Completed, last 30 days (SIG-01 c). */
export const COMPLETED: readonly HubEnvelope[] = [
  {
    key: "C1",
    title: "Form 8879 · Sunil & Asha Rao",
    client: "Sunil & Asha Rao",
    purpose: "form_8879",
    signers: [s("Sunil", true), s("Asha", true)],
    sent: "2026-09-10",
    viewed: null,
    due: null,
    workItem: "TY2025 Form 1040 · Rao",
    status: "completed",
    outcome: "Filed Sep 11",
  },
  {
    key: "C2",
    title: "Form 8879-S · Summit Line Logistics, Inc.",
    client: "Summit Line Logistics, Inc.",
    purpose: "form_8879",
    signers: [s("President", true)],
    sent: "2026-09-11",
    viewed: null,
    due: null,
    workItem: "TY2025 Form 1120-S · Summit Line",
    status: "completed",
    outcome: "Filed Sep 12",
  },
  {
    key: "C3",
    title: "Form 8879-PE · Vantage Point Realty, LLC",
    client: "Vantage Point Realty, LLC",
    purpose: "form_8879",
    signers: [],
    sent: "2026-09-04",
    viewed: null,
    due: null,
    workItem: "TY2025 Form 1065 · Vantage Point",
    status: "completed",
    outcome: "Accepted",
  },
  {
    key: "C4",
    title: "Form 8879-PE · Cedar Hollow Farms, LLC",
    client: "Cedar Hollow Farms, LLC",
    purpose: "form_8879",
    signers: [],
    sent: "2026-09-02",
    viewed: null,
    due: null,
    workItem: "TY2025 Form 1065 · Cedar Hollow",
    status: "completed",
    outcome: "Accepted",
  },
  {
    key: "C5",
    title: "Engagement letter · 2025 Form 990 (FYE Jun 30, 2026) · Lakeshore Literacy Alliance",
    client: "Lakeshore Literacy Alliance",
    purpose: "engagement_letter",
    signers: [s("Monica Hale-Ruiz", true), s("CM", true)],
    sent: "2026-08-28",
    viewed: null,
    due: null,
    workItem: "2025 Form 990 · Lakeshore",
    status: "completed",
  },
  {
    key: "C6",
    title: "Form 8879-S · Two Rivers Brewing Co.",
    client: "Two Rivers Brewing Co.",
    purpose: "form_8879",
    signers: [],
    sent: "2026-08-27",
    viewed: null,
    due: null,
    workItem: "TY2025 Form 1120-S · Two Rivers",
    status: "completed",
    outcome: "Accepted",
  },
];

/** Expired (SIG-01 d). */
export const EXPIRED: readonly HubEnvelope[] = [
  {
    key: "X1",
    title: "§7216 consent (disclosure to offshore preparers) · Sunil & Asha Rao",
    client: "Sunil & Asha Rao",
    purpose: "consent_7216",
    signers: [s("Sunil"), s("Asha")],
    sent: "2026-08-16",
    viewed: null,
    due: "2026-08-30",
    workItem: "TY2025 Form 1040 · Rao",
    status: "expired",
    note: "Not resent — no offshore staffing on this return; services are never conditioned on consent",
  },
];

/** The handoff's to-send count, tile counts and the by-type tile (SIG-01 tabsbar and tiles). */
export const HUB_COUNTS = {
  toSend: 2,
  out: 17,
  expired: 1,
  tiles: { sent: 8, viewed: 5, partially_signed: 4, dueWithin7: 4 },
  byType: { efile: 10, letters: 4, rep: 2, consents: 1 },
} as const;

/** The four due within seven days of E0 (Mon Sep 14): Sep 15, 15, 16 and 18. */
export const DUE_WITHIN_7 = ["E3", "E7", "E14", "E11"] as const;

/** E13's fee (ENG-04 §6 "Fees and billing"): two lines and their total, whole dollars. */
export const E13_FEE = {
  lines: [
    { label: "section 754 work", amount: "6500" },
    { label: "cost segregation coordination and Form 3115", amount: "12000" },
  ],
  total: "18500",
} as const;
