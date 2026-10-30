// ADM-05's registry rows (T-01-T13; docs/screens/ADM-05.md; the handoff spec's ROWS 1 to 14):
// the 14 rows a needs-attention-first page shows of the firm's 218 consents. The standard
// individual set is two consents, a consent to use and a consent to disclose to AI
// sub-processors, one purpose each (Rev. Proc. 2013-14 §5.05); a third-party disclosure is one.
// Recipients come from the provider register (DF-16, deviation D1), never free text. Dates are
// the spec's, at E0 (Mon Sep 14, 2026, 9:24 AM CT).
import type { ConsentOut, ConsentRecipientOut, ConsentSignerOut } from "@abacus/api-client";
import { stableId } from "./prng";

/** The provider register's party for model inference (DF-16; ADR-114). */
export const BEDROCK: ConsentRecipientOut = {
  kind: "provider",
  name: "Amazon Web Services (Bedrock)",
  country: "US",
};

type Purpose = ConsentOut["purpose"];

interface Signer {
  name: string;
  role: ConsentSignerOut["role"];
  signedAt?: string;
  title?: string;
}

interface Row {
  client: string;
  /** The set's purposes: the standard set is use + ai_disclosure. */
  purposes: readonly Purpose[];
  years: readonly number[];
  scope: string;
  recipient?: ConsentRecipientOut;
  status: ConsentOut["status"];
  signedAt?: string;
  expiresAt?: string;
  declinedAt?: string;
  revokedAt?: string;
  signers: readonly Signer[];
}

const SET: readonly Purpose[] = ["use", "ai_disclosure"];
const TP: readonly Purpose[] = ["third_party_disclosure"];
const TY2025 = "TY2025 return information";
const DEC31 = "2026-12-31T23:59:00-06:00";

/** The spec's rows in its order ("needs attention first"). */
const ROWS: readonly Row[] = [
  {
    client: "Morgan & Kai Ferris",
    purposes: SET,
    years: [2025],
    scope: TY2025,
    status: "requested",
    signers: [
      { name: "Morgan Ferris", role: "taxpayer", signedAt: "2026-09-09T14:02:00-05:00" },
      { name: "Kai Ferris", role: "spouse" },
    ],
  },
  {
    client: "Harold Stein",
    purposes: SET,
    years: [2025],
    scope: TY2025,
    status: "declined",
    declinedAt: "2026-02-10T10:30:00-06:00",
    signers: [{ name: "Harold Stein", role: "taxpayer" }],
  },
  {
    client: "Priyanka & Sam Iyer",
    purposes: TP,
    years: [2023, 2024],
    scope: "TY2023–TY2024 returns",
    recipient: {
      kind: "third_party",
      name: "Lakeview Credit Union (mortgage underwriting)",
      country: null,
    },
    status: "expired",
    signedAt: "2025-08-01T10:00:00-05:00",
    expiresAt: "2026-08-01T10:00:00-05:00",
    signers: [
      { name: "Priyanka Iyer", role: "taxpayer", signedAt: "2025-08-01T10:00:00-05:00" },
      { name: "Sam Iyer", role: "spouse", signedAt: "2025-08-01T10:00:00-05:00" },
    ],
  },
  {
    client: "Sunil & Asha Rao",
    purposes: TP,
    years: [2024],
    scope: "TY2024 return",
    recipient: {
      kind: "third_party",
      name: "Halvard Securities (financial advisor)",
      country: null,
    },
    status: "signed",
    signedAt: "2025-09-30T10:00:00-05:00",
    expiresAt: "2026-09-30T10:00:00-05:00",
    signers: [
      { name: "Sunil Rao", role: "taxpayer", signedAt: "2025-09-30T10:00:00-05:00" },
      { name: "Asha Rao", role: "spouse", signedAt: "2025-09-30T10:00:00-05:00" },
    ],
  },
  {
    client: "Benjamin Osterberg",
    purposes: TP,
    years: [2023, 2024],
    scope: "TY2023–TY2024 returns",
    recipient: { kind: "third_party", name: "Ellery & Shaw LLP (estate attorney)", country: null },
    status: "signed",
    signedAt: "2025-10-06T10:00:00-05:00",
    expiresAt: "2026-10-06T10:00:00-05:00",
    signers: [
      { name: "Benjamin Osterberg", role: "taxpayer", signedAt: "2025-10-06T10:00:00-05:00" },
    ],
  },
  {
    client: "Delia Fortune",
    purposes: TP,
    years: [2025],
    scope: "TY2025 return",
    recipient: { kind: "third_party", name: "Halvard Securities", country: null },
    status: "revoked",
    signedAt: "2026-03-02T10:00:00-06:00",
    revokedAt: "2026-06-02T10:00:00-05:00",
    signers: [{ name: "Delia Fortune", role: "taxpayer", signedAt: "2026-03-02T10:00:00-06:00" }],
  },
  {
    client: "Daniel & Ruth Okafor",
    purposes: TP,
    years: [2025],
    scope: "TY2025 return",
    recipient: { kind: "third_party", name: "Lakeview Credit Union (refinance)", country: null },
    status: "signed",
    signedAt: "2026-03-03T10:00:00-06:00",
    expiresAt: "2027-03-03T10:00:00-06:00",
    signers: [
      { name: "Daniel Okafor", role: "taxpayer", signedAt: "2026-03-03T10:00:00-06:00" },
      { name: "Ruth Okafor", role: "spouse", signedAt: "2026-03-03T10:00:00-06:00" },
    ],
  },
  {
    client: "Jonah & Claire Feld",
    purposes: SET,
    years: [2025],
    scope: TY2025,
    status: "signed",
    signedAt: "2026-02-02T18:41:00-06:00",
    expiresAt: DEC31,
    signers: [
      { name: "Claire Feld", role: "taxpayer", signedAt: "2026-02-02T10:14:00-06:00" },
      { name: "Jonah Feld", role: "spouse", signedAt: "2026-02-02T18:41:00-06:00" },
    ],
  },
  {
    client: "Marcus & Dana Whitley",
    purposes: SET,
    years: [2025],
    scope: TY2025,
    status: "signed",
    signedAt: "2026-01-20T10:00:00-06:00",
    expiresAt: DEC31,
    signers: [
      { name: "Marcus Whitley", role: "taxpayer", signedAt: "2026-01-20T10:00:00-06:00" },
      { name: "Dana Whitley", role: "spouse", signedAt: "2026-01-20T10:00:00-06:00" },
    ],
  },
  {
    client: "Meera Shah",
    purposes: SET,
    years: [2025],
    scope: TY2025,
    status: "signed",
    signedAt: "2026-01-27T10:00:00-06:00",
    expiresAt: DEC31,
    signers: [{ name: "Meera Shah", role: "taxpayer", signedAt: "2026-01-27T10:00:00-06:00" }],
  },
  {
    client: "Calloway Family Trust",
    purposes: SET,
    years: [2025],
    scope: TY2025,
    status: "signed",
    signedAt: "2026-02-09T10:00:00-06:00",
    expiresAt: DEC31,
    signers: [
      {
        name: "Eleanor Calloway",
        role: "fiduciary",
        title: "trustee",
        signedAt: "2026-02-09T10:00:00-06:00",
      },
    ],
  },
  {
    client: "Elena Varga",
    purposes: SET,
    years: [2025],
    scope: TY2025,
    status: "signed",
    signedAt: "2026-02-16T10:00:00-06:00",
    expiresAt: DEC31,
    signers: [{ name: "Elena Varga", role: "taxpayer", signedAt: "2026-02-16T10:00:00-06:00" }],
  },
  {
    client: "Ridgeline Property Partners, LP",
    purposes: SET,
    years: [2025],
    scope: TY2025,
    status: "signed",
    signedAt: "2026-02-06T10:00:00-06:00",
    expiresAt: "2027-02-06T23:59:00-06:00",
    signers: [
      {
        name: "Owen Calder",
        role: "partner",
        title: "for Ridgeline GP LLC",
        signedAt: "2026-02-06T10:00:00-06:00",
      },
    ],
  },
  {
    client: "Copperleaf Coffee Roasters, Inc.",
    purposes: SET,
    years: [2025],
    scope: TY2025,
    status: "signed",
    signedAt: "2026-01-13T10:00:00-06:00",
    expiresAt: DEC31,
    signers: [
      {
        name: "Tess Moreno",
        role: "officer",
        title: "CEO",
        signedAt: "2026-01-13T10:00:00-06:00",
      },
    ],
  },
];

/** The firm's published consent templates (database content in a live firm; KNW-05). */
const TEMPLATES: Partial<Record<Purpose, string>> = {
  use: "BH §7216 Consent to Use v2",
  ai_disclosure: "BH §7216 Consent to Disclose — AI sub-processors v2",
};

function slug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function signerOut(s: Signer): ConsentSignerOut {
  return {
    contact_id: stableId(`contact:${slug(s.name)}`),
    name: s.name,
    role: s.role,
    required: true,
    signed_at: s.signedAt ?? null,
    method: s.signedAt === undefined ? null : "email_code",
    title: s.title ?? null,
  };
}

function consentsOf(row: Row): ConsentOut[] {
  const key = slug(row.client);
  const set = row.purposes.length > 1 ? stableId(`consent-set:${key}`) : null;
  const signers = row.signers.map(signerOut);
  const signed = signers.filter((s) => s.signed_at !== null).length;
  return row.purposes.map((purpose) => ({
    id: stableId(`consent:${key}:${purpose}`),
    client_id: stableId(`client:${key}`),
    client_entity_id: stableId(`client-entity:${key}`),
    client_name: row.client,
    consent_set_id: set,
    purpose,
    tax_years: [...row.years],
    scope: { label: row.scope },
    recipients:
      purpose === "ai_disclosure" ? [BEDROCK] : row.recipient === undefined ? [] : [row.recipient],
    provider_terms_version: "probe",
    template_version_id: stableId(`consent-template:${purpose}:v2`),
    source: "envelope",
    envelope_id: row.status === "requested" ? stableId("envelope:E17") : null,
    status: row.status,
    signed_count: signed,
    signer_count: signers.length,
    requested_at: row.signedAt ?? "2026-09-08T10:00:00-05:00",
    signed_at: row.signedAt ?? null,
    expires_at: row.expiresAt ?? null,
    renewal_of_id: null,
    offshore: false,
    allowed_actions:
      row.status === "declined" ? ["consent.read"] : ["consent.read", "consent.request"],
    template_name: TEMPLATES[purpose] ?? null,
    declined_at: row.declinedAt ?? null,
    revoked_at: row.revokedAt ?? null,
    signers,
  }));
}

/** The page's consents, in the spec's row order (a set's two consents side by side). */
export const REGISTRY_CONSENTS: readonly ConsentOut[] = ROWS.flatMap(consentsOf);
export const REGISTRY_ROWS = ROWS.length;
/** The firm's consents in all (the tiles' 212 + 2 + 1 + 1 + 1 + 1). */
export const REGISTRY_TOTAL = 218;
