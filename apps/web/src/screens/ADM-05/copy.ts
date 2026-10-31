// ADM-05 · Consent registry (§7216): copy verbatim from the handoff's spec.md (T-01-T13). The
// status words are the registry's `consent` object; the purpose names are the spec's.
import type { ConsentOut } from "@abacus/api-client";

type Purpose = ConsentOut["purpose"];

export const COPY = {
  title: "Consents",
  back: "Settings",
  navTitle: "Settings",
  section: "Consents",
  filters: {
    purpose: "Purpose",
    status: "Status",
    expires: "Expires",
    client: "Client",
    all: "All",
    anyTime: "Any time",
  },
  templates: "Templates ›",
  templatesTip: "Opens KNW-05 · Templates filtered to consents",
  exportCsv: "Export CSV",
  exportQueued: "Export queued · logged",
  search: "Search consents",
  clearSearch: "Clear search",
  heading: (n: string): string => `Consents · ${n}`,
  request: "Request consent…",
  requestTip: "Opens SIG-02 with a purpose picker",
  tilesLabel: "Consents by status",
  note: "210 AI-use consents expire Dec 31, 2026 (Ridgeline's run to Feb 6, 2027). Renew them with the TY2026 engagement letters at season setup.",
  columns: {
    select: "Select",
    client: "Client / taxpayer",
    purpose: "Purpose",
    scope: "Scope & recipient",
    signed: "Signed",
    expires: "Expires",
    status: "Status",
    evidence: "Evidence",
  },
  selectRow: (client: string): string => `Select ${client}`,
  evidence: (client: string): string => `Evidence · ${client}`,
  envelopeDue: "Envelope due Sep 23",
  envelopeTip: "Opens SIG-01 · envelope E17",
  declinedNote: "No re-solicitation · prepared without agents",
  declinedTip:
    "Recorded Feb 10, 2026. Services are not conditioned on consent. Re-solicitation is blocked.",
  requested: (signed: number, of: number): string =>
    `Requested · ${String(signed)} of ${String(of)} signed`,
  expiring: (days: number): string => `Expiring · ${String(days)} days`,
  signedUntil: (date: string): string => `Signed · expires ${date}`,
  declinedOn: (date: string): string => `Declined ${date}`,
  revokedOn: (date: string): string => `Revoked ${date}`,
  footerCount: (shown: string, total: string): string => `${shown} of ${total} consents`,
  loadMore: "Load more",
  footerFacts:
    "Not requested: 1 — Estate of Walter Thornbury (executor consent follows acceptance, CLI-07). Return information withheld from agents for 3 clients.",
  emptyTitle: "No consents match.",
  emptyBody: (total: string): string => `Clear filters to see all ${total}.`,
  clearFilters: "Clear filters",
  selected: (n: number): string => `${String(n)} selected`,
  renew: (n: number): string => `Renew ${String(n)}…`,
  renewTip: "Opens SIG-02 with the drafted envelopes",
  clear: "Clear",
  error: "Consents couldn't load.",
  // T-01-T32 (part 2): renewals (d, h) and the evidence drawer (c).
  renewalsDrafted: (n: number): string => `${String(n)} renewal envelopes drafted`,
  drawer: {
    title: (client: string): string => `§7216 consents · ${client}`,
    purpose: "Purpose",
    templates: "Templates",
    signed: "Signed",
    method: "Method",
    expires: "Expires",
    reads: "Agent reads since signature",
    readCount: (n: number): string => `${String(n)} tool calls`,
    documents: "Signed documents",
    download: "Download evidence",
    esign: "Accrued e-signature",
    separate:
      "The two arrived in one envelope but are separate signed documents (Rev. Proc. 2013-14 §5.05).",
  },
  retry: "Try again",
} as const;

/** The Purpose column: a standard set is two consents, one purpose each (Rev. Proc. 2013-14). */
export const SET_PURPOSE = "Use · AI disclosure (2 consents)";
export const PURPOSES: Readonly<Record<Purpose, string>> = {
  use: "Use",
  ai_disclosure: "AI disclosure",
  offshore_disclosure: "Disclosure to offshore preparers",
  third_party_disclosure: "Disclosure to a named third party",
  other_services_use: "Use for other services",
  firm_defined: "Firm-defined purpose",
};

/** T-01-T32: each signed document's tab and the paper's heading (the handoff's c). */
export const DOCUMENT_TABS: Readonly<Partial<Record<Purpose, string>>> = {
  use: "Consent to use",
  ai_disclosure: "Consent to disclose — AI sub-processors",
};
export const DOCUMENT_HEADINGS: Readonly<Partial<Record<Purpose, string>>> = {
  use: "Consent to Use of Tax Return Information",
  ai_disclosure: "Consent to Disclose Tax Return Information to AI Service Providers",
};
export const METHODS: Readonly<Record<string, string>> = {
  email_code: "email code",
  kba: "KBA",
  wet: "wet signature",
  record: "recorded",
};

/** The purpose chip's options (the spec's picker, in its order). */
export const PURPOSE_OPTIONS = [
  { value: "use", label: SET_PURPOSE },
  { value: "offshore_disclosure", label: PURPOSES.offshore_disclosure },
  { value: "third_party_disclosure", label: PURPOSES.third_party_disclosure },
  { value: "other_services_use", label: PURPOSES.other_services_use },
] as const;

/** The status tiles and chip, in the spec's order; `expiring` is derived (signed, ≤ 30 days). */
export const STATUS_TILES = [
  { code: "signed", label: "Signed", variant: "green" },
  { code: "expiring", label: "Expiring", variant: "amber" },
  { code: "requested", label: "Requested", variant: "amber" },
  { code: "expired", label: "Expired", variant: "red-tint" },
  { code: "declined", label: "Declined", variant: "neutral" },
  { code: "revoked", label: "Revoked", variant: "soon" },
] as const;
export type TileCode = (typeof STATUS_TILES)[number]["code"];
