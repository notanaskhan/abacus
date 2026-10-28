// The ten 8879-family envelopes behind the Awaiting signature returns at E0 (F-06-T02;
// blueprint 01 §9.7 E1 to E10), and envelope E6 in full for the TPL-16 signing specimen: Form 8879
// and TR-579-IT for Dev & Mira Kapoor, sent Sep 8, Dev signed Sep 9, 6:12 PM, due Oct 5
// (docs/screens/TPL-16.md). TINs exist only as the masked strings the server sends. Figures are
// whole-dollar decimal strings; the browser never adds them (tax.foot.test.ts does, in BigInt).

export type EnvelopeStatus =
  "sent" | "viewed" | "partially_signed" | "completed" | "declined" | "expired" | "voided";

export interface SeedSignerChip {
  name: string;
  signed: boolean;
}

export interface SeedEnvelope {
  key: string; // "E1" … "E10"
  title: string;
  client: string;
  signers: readonly SeedSignerChip[];
  sent: string; // ISO date
  status: EnvelopeStatus;
  due: string; // ISO date
}

const chip = (name: string, signed = false): SeedSignerChip => ({ name, signed });

export const ENVELOPES: readonly SeedEnvelope[] = [
  {
    key: "E1",
    title: "Form 8879 · TY2025 · Elena Varga",
    client: "Elena Varga",
    signers: [chip("Elena")],
    sent: "2026-09-09",
    status: "viewed",
    due: "2026-10-01",
  },
  {
    key: "E2",
    title: "Form 8879 · TY2025 · Thomas & Irene Kowal",
    client: "Thomas & Irene Kowal",
    signers: [chip("Thomas", true), chip("Irene")],
    sent: "2026-09-10",
    status: "partially_signed",
    due: "2026-10-01",
  },
  {
    key: "E3",
    title: "Form 8879-PE · TY2025 · Kestrel Ventures Fund I, LP",
    client: "Kestrel Ventures Fund I, LP",
    signers: [chip("GP officer")],
    sent: "2026-09-11",
    status: "sent",
    due: "2026-09-15",
  },
  {
    key: "E4",
    title: "Form 8879-F · TY2025 · Pryor Irrevocable Trust",
    client: "Pryor Irrevocable Trust",
    signers: [chip("trustee")],
    sent: "2026-09-10",
    status: "viewed",
    due: "2026-09-28",
  },
  {
    key: "E5",
    title: "Form 8879 · TY2025 · Corinne Abbott",
    client: "Corinne Abbott",
    signers: [chip("Corinne")],
    sent: "2026-09-12",
    status: "sent",
    due: "2026-10-05",
  },
  {
    key: "E6",
    title: "Form 8879 · TY2025 · Dev & Mira Kapoor",
    client: "Dev & Mira Kapoor",
    signers: [chip("Dev", true), chip("Mira")],
    sent: "2026-09-08",
    status: "partially_signed",
    due: "2026-10-05",
  },
  {
    key: "E7",
    title: "Form 8879-S · TY2025 · Larkspur Floral, Inc.",
    client: "Larkspur Floral, Inc.",
    signers: [chip("president")],
    sent: "2026-09-11",
    status: "viewed",
    due: "2026-09-15",
  },
  {
    key: "E8",
    title: "Form 8879 · TY2025 · Hugo Brandvold",
    client: "Hugo Brandvold",
    signers: [chip("Hugo")],
    sent: "2026-09-13",
    status: "sent",
    due: "2026-10-05",
  },
  {
    key: "E9",
    title: "Form 8879 · TY2025 · Noor & Adam Farouk",
    client: "Noor & Adam Farouk",
    signers: [chip("Noor"), chip("Adam")],
    sent: "2026-09-13",
    status: "sent",
    due: "2026-10-05",
  },
  {
    key: "E10",
    title: "Form 8879-C · TY2025 · Brightline Optics, Inc.",
    client: "Brightline Optics, Inc.",
    signers: [chip("CFO")],
    sent: "2026-09-12",
    status: "sent",
    due: "2026-10-08",
  },
];

// --- E6 in full (TPL-16) -------------------------------------------------------------------------

export const KAPOOR = "Dev & Mira Kapoor";

export interface E6Signer {
  id: string;
  name: string;
  first: string;
  persona: string;
  /** Masked SSN, as the server sends it. */
  tin: string;
  method: "kba";
}

export const E6_SIGNERS: readonly E6Signer[] = [
  {
    id: "e6-dev",
    name: "Dev Kapoor",
    first: "Dev",
    persona: "dev-kapoor",
    tin: "•••-••-7731",
    method: "kba",
  },
  {
    id: "e6-mira",
    name: "Mira Kapoor",
    first: "Mira",
    persona: "mira-kapoor",
    tin: "•••-••-2058",
    method: "kba",
  },
];

export const E6 = {
  key: "E6",
  title: "Form 8879 · TY2025 · Dev & Mira Kapoor",
  shortTitle: "Form 8879 · TY2025",
  sent: "2026-09-08",
  due: "2026-10-05",
  preparer: "Dina Sato",
  firm: "Brightwater Hale",
  ero: "Brightwater Hale LLP",
  documents: [
    { id: "e6-8879", name: "Form 8879 — IRS e-file Signature Authorization" },
    { id: "e6-tr579", name: "Form TR-579-IT — New York e-file Signature Authorization" },
  ],
  /** Dev signed Sep 9, 6:12 PM CT; Mira verified 9:21 AM on Sep 14. */
  devSignedAt: "2026-09-09T18:12:00-05:00",
  miraVerifiedAt: "2026-09-14T09:21:00-05:00",
  /** Form 8879 Part I, whole dollars. Refund = withheld − total tax. */
  partI: {
    agi: "312640",
    totalTax: "58904",
    withheld: "61200",
    refund: "2296",
    owed: null,
  },
  nyRefund: "410",
  eroLine: "EFIN ••••12 · ERO PIN •••••",
  /** The completion record (TPL-16d), in the handoff's order. */
  evidence: [
    { key: "signed", value: "Sep 14, 2026, 9:24 AM CT" },
    { key: "method", value: "Typed name + PIN (remote)" },
    { key: "identity", value: "Knowledge-based authentication — passed 4 of 4 · 9:21 AM" },
    { key: "ip", value: "203.0.113.42" },
    { key: "login", value: "mira.kapoor@example.com" },
    { key: "documents", value: "Form 8879, Form TR-579-IT (SHA-256 recorded)" },
  ],
} as const;
