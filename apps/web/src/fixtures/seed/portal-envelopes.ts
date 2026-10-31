// The portal's signing seed for POR-06 (N-02-T26; docs/screens/POR-06.md; handoff POR-06 README
// and spec): Owen Calder (Ridgeline Property Partners, LP) at E0, Mon Sep 14, 2026, 9:24 AM CT,
// on E13, the cost segregation and section 754 engagement letter Daniel Reyes sent at 8:40 AM, due
// Sep 24, three pages, Owen signs first and Daniel countersigns. Signed band: the 2025 Form 1065
// engagement letter and the two §7216 consents, each its own document (Rev. Proc. 2013-14 §5.05),
// signed Feb 6, 2026. C7's portal shapes only (`PortalEnvelopeView`, `PortalEnvelopeRow`); the
// signers in order, the family, the viewer's identity method and the date gate since N-02-T29
// (DEC-1388).
//
// N-02-T29 adds POR-06 d, e, f and h (handoff POR-06 README and spec; DF-11, DF-12):
// - d (E14): Owen's 2025 Form 8879-PE at 4:10 PM, KBA in the provider's view, Daniel Reyes the
//   ERO after him (Pub 1345: the taxpayer or officer signs first). Line 4 is 1,231,600 on the page.
// - e (E15): the Feld 2025 Form 8879 on Fri Oct 2, 2026: Claire signed at 9:10 AM, Jonah signs
//   with his own link, Daniel Reyes the ERO after both.
// - f (E16): Dana Kowalski's Northwind representation letter on Tue Oct 6, 2026, dated Oct 9 (the
//   report date): the server says signing opens Oct 9. Fixture only until A-07 registers
//   `rep_letter` (its family here is the letters family).
// - h: E14 after the provider's third failed identity check (DF-11): the paper form follows.
import type {
  FieldOut,
  PortalEnvelopeRow,
  PortalEnvelopeView,
  PortalSignerOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const POR06_PERSONA = "owen-calder";

/** a, b, g, the list: E0. c: the return at 9:31 AM, when Owen has signed (POR-06 README). */
export const POR06_CLOCK = "2026-09-14T09:24:00-05:00";
export const POR06_SIGNED_CLOCK = "2026-09-14T09:31:00-05:00";

export const E13_ID = stableId("envelope:E13");
const E13_LETTER = stableId("envelope-document:E13:letter");
const OWEN_SIGNER = stableId("envelope-signer:E13:owen-calder");

/** Daniel Reyes, Tax Partner and the firm's signer (seed §9). */
const DANIEL = "Daniel Reyes";

/** The letter's fingerprint as the completion card prints it, "SHA-256 a41f…9c07" (POR-06c): the
 * seed's synthetic digest with the handoff's visible ends. */
export const E13_SHA256 = `a41f${"0".repeat(56)}9c07`;

/** The brand's ERSD disclosure version (database content, counsel-approved; DEC-59). */
export const ERSD_VERSION = stableId("ersd:brightwater-hale:v1");

/** Owen's two fields on page 3 (points on a Letter page): "ACCEPTED: … by Ridgeline GP LLC" with
 * the 220 × 44 signature and the date filled at signing (POR-06 spec). */
const OWEN_FIELDS: readonly FieldOut[] = [
  {
    id: stableId("envelope-field:E13:owen:signature"),
    document_id: E13_LETTER,
    signer_id: OWEN_SIGNER,
    kind: "signature",
    page: 3,
    x: 72,
    y: 560,
    w: 220,
    h: 44,
    anchor: null,
  },
  {
    id: stableId("envelope-field:E13:owen:date"),
    document_id: E13_LETTER,
    signer_id: OWEN_SIGNER,
    kind: "date",
    page: 3,
    x: 320,
    y: 578,
    w: 140,
    h: 26,
    anchor: null,
  },
];

export const E13_ROW: PortalEnvelopeRow = {
  id: E13_ID,
  title: "Engagement letter — Cost segregation and section 754 analysis",
  status: "sent",
  my_status: "viewed",
  due_on: "2026-09-24",
};

/** E13 as Owen opens it (POR-06a): ERSD not yet accepted, no provider session, 0 of 2 signed. */
export const E13_VIEW: PortalEnvelopeView = {
  row: E13_ROW,
  documents: [
    {
      id: E13_LETTER,
      order: 1,
      page_count: 3,
      read_only: false,
      sha256: E13_SHA256,
      title: "Engagement letter — Cost segregation and §754",
      tri: false,
    },
  ],
  my_fields: [...OWEN_FIELDS],
  signers_signed: 0,
  signers_total: 2,
  esign_consent_needed: true,
  disclosure_version_id: ERSD_VERSION,
  date_as_of: null,
  paper_form_follows: false,
  signing_session: null,
  outcome: null,
  family: "engagement_letter",
  identity_method: "email_code",
  signers: [
    {
      id: OWEN_SIGNER,
      name: "Owen Calder",
      role: "signer",
      routing_group: 1,
      status: "viewed",
      signed_at: null,
      me: true,
    },
    {
      id: stableId("envelope-signer:E13:daniel-reyes"),
      name: DANIEL,
      role: "countersigner",
      routing_group: 2,
      status: "pending",
      signed_at: null,
      me: false,
    },
  ],
  signing_opens_on: null,
};

/** The provider's one-time view for E13 (DF-12). The `.invalid` host never resolves (RFC 2606):
 * fixture mode loads nothing from a provider. */
export const E13_SESSION = {
  session_id: stableId("signing-session:E13:owen-calder:1"),
  presentation: "iframe" as const,
  url: "https://signing.example.invalid/session/e13-owen",
  expires_at: "2026-09-14T09:44:00-05:00",
};

/** The signed band (POR-06 list): each completed Feb 6, 2026. */
export const SIGNED_ROWS: readonly PortalEnvelopeRow[] = [
  {
    id: stableId("envelope:ridgeline-2025-1065-letter"),
    title: "2025 engagement letter — Form 1065",
    status: "completed",
    my_status: "signed",
    due_on: null,
  },
  {
    id: stableId("envelope:ridgeline-7216-use"),
    title: "Consent to use tax return information",
    status: "completed",
    my_status: "signed",
    due_on: null,
  },
  {
    id: stableId("envelope:ridgeline-7216-disclose-ai"),
    title: "Consent to disclose tax return information to AI service providers",
    status: "completed",
    my_status: "signed",
    due_on: null,
  },
];

// ---- N-02-T29: d, e, f, h ------------------------------------------------------------------------

/** d: Mon Sep 14, 2026, 4:10 PM CT (POR-06 README). h keeps E0 (9:24 AM). */
export const POR06_D_CLOCK = "2026-09-14T16:10:00-05:00";

export const E14_ID = stableId("envelope:E14");
const E14_FORM = stableId("envelope-document:E14:8879-pe");
const OWEN_E14 = stableId("envelope-signer:E14:owen-calder");

/** Owen's PIN authorization and signature on the 8879-PE's Part II (points on a Letter page). */
const OWEN_E14_FIELDS: readonly FieldOut[] = [
  {
    id: stableId("envelope-field:E14:owen:signature"),
    document_id: E14_FORM,
    signer_id: OWEN_E14,
    kind: "signature",
    page: 1,
    x: 108,
    y: 452,
    w: 220,
    h: 42,
    anchor: null,
  },
  {
    id: stableId("envelope-field:E14:owen:date"),
    document_id: E14_FORM,
    signer_id: OWEN_E14,
    kind: "date",
    page: 1,
    x: 382,
    y: 452,
    w: 110,
    h: 42,
    anchor: null,
  },
];

/** d: the 2025 Form 8879-PE as Owen opens it; identity questions run in the provider's view. */
export const E14_VIEW: PortalEnvelopeView = {
  row: {
    id: E14_ID,
    title: "Form 8879-PE · 2025 · Ridgeline Property Partners, LP",
    status: "sent",
    my_status: "viewed",
    due_on: "2026-09-15",
  },
  documents: [
    {
      id: E14_FORM,
      order: 1,
      page_count: 1,
      read_only: false,
      sha256: `${"0".repeat(60)}e14a`,
      title: "Form 8879-PE — 2025 e-file authorization",
      tri: false,
    },
  ],
  my_fields: [...OWEN_E14_FIELDS],
  signers_signed: 0,
  signers_total: 2,
  esign_consent_needed: true,
  disclosure_version_id: ERSD_VERSION,
  date_as_of: null,
  paper_form_follows: false,
  signing_session: null,
  outcome: null,
  family: "efile_authorization",
  identity_method: "kba",
  signers: [
    {
      id: OWEN_E14,
      name: "Owen Calder",
      role: "signer",
      routing_group: 1,
      status: "viewed",
      signed_at: null,
      me: true,
    },
    {
      id: stableId("envelope-signer:E14:daniel-reyes"),
      name: DANIEL,
      role: "ero",
      routing_group: 2,
      status: "pending",
      signed_at: null,
      me: false,
    },
  ],
  signing_opens_on: null,
};

/** h: E14 after the provider's third failed identity check (DF-11; C7 `verification_failed`). */
export const E14_FAILED_VIEW: PortalEnvelopeView = {
  ...E14_VIEW,
  row: { ...E14_VIEW.row, my_status: "verification_failed" },
  paper_form_follows: true,
  signers: E14_VIEW.signers.map((s) =>
    s.me ? { ...s, status: "verification_failed" as const } : s,
  ),
};

/** e: Fri Oct 2, 2026, 9:10 AM CT, when Claire has signed (POR-06 README). */
export const POR06_E_CLOCK = "2026-10-02T09:10:00-05:00";
export const POR06_E_PERSONA = "claire-feld";

export const E15_ID = stableId("envelope:E15");
const E15_FORM = stableId("envelope-document:E15:8879");
const CLAIRE_E15 = stableId("envelope-signer:E15:claire-feld");

const E15_SIGNERS: readonly PortalSignerOut[] = [
  {
    id: CLAIRE_E15,
    name: "Claire Feld",
    role: "signer",
    routing_group: 1,
    status: "signed",
    signed_at: POR06_E_CLOCK,
    me: true,
  },
  {
    id: stableId("envelope-signer:E15:jonah-feld"),
    name: "Jonah Feld",
    role: "signer",
    routing_group: 1,
    status: "pending",
    signed_at: null,
    me: false,
  },
  {
    id: stableId("envelope-signer:E15:daniel-reyes"),
    name: DANIEL,
    role: "ero",
    routing_group: 2,
    status: "pending",
    signed_at: null,
    me: false,
  },
];

/** e: the Feld 2025 Form 8879; each spouse verifies and signs with their own link. */
export const E15_VIEW: PortalEnvelopeView = {
  row: {
    id: E15_ID,
    title: "Form 8879 · 2025 · Jonah & Claire Feld",
    status: "partially_signed",
    my_status: "signed",
    due_on: "2026-10-15",
  },
  documents: [
    {
      id: E15_FORM,
      order: 1,
      page_count: 1,
      read_only: false,
      sha256: `${"0".repeat(60)}e15a`,
      title: "Form 8879 — 2025 e-file authorization",
      tri: false,
    },
  ],
  my_fields: [
    {
      id: stableId("envelope-field:E15:claire:signature"),
      document_id: E15_FORM,
      signer_id: CLAIRE_E15,
      kind: "signature",
      page: 1,
      x: 108,
      y: 640,
      w: 220,
      h: 42,
      anchor: null,
    },
  ],
  signers_signed: 1,
  signers_total: E15_SIGNERS.length,
  esign_consent_needed: false,
  disclosure_version_id: ERSD_VERSION,
  date_as_of: null,
  paper_form_follows: false,
  signing_session: null,
  outcome: null,
  family: "efile_authorization",
  identity_method: "kba",
  signers: [...E15_SIGNERS],
  signing_opens_on: null,
};

/** f: Tue Oct 6, 2026, 10:02 AM CT; the letter is dated Oct 9, the report date (POR-06 spec). */
export const POR06_F_CLOCK = "2026-10-06T10:02:00-05:00";
export const POR06_F_PERSONA = "dana-kowalski";

export const E16_ID = stableId("envelope:E16");
const E16_LETTER = stableId("envelope-document:E16:rep-letter");
const DANA_E16 = stableId("envelope-signer:E16:dana-kowalski");

/** f: Dana's representation letter; the server says signing opens Oct 9 (`before_date_as_of`). */
export const E16_VIEW: PortalEnvelopeView = {
  row: {
    id: E16_ID,
    title: "Representation letter — Northwind Robotics 401(k) Plan, 2025",
    status: "sent",
    my_status: "viewed",
    due_on: "2026-10-09",
  },
  documents: [
    {
      id: E16_LETTER,
      order: 1,
      page_count: 2,
      read_only: false,
      sha256: `${"0".repeat(60)}e16a`,
      title: "Representation letter — Northwind Robotics 401(k) Plan, 2025",
      tri: false,
    },
  ],
  my_fields: [
    {
      id: stableId("envelope-field:E16:dana:signature"),
      document_id: E16_LETTER,
      signer_id: DANA_E16,
      kind: "signature",
      page: 2,
      x: 72,
      y: 600,
      w: 220,
      h: 44,
      anchor: null,
    },
  ],
  signers_signed: 0,
  signers_total: 1,
  esign_consent_needed: true,
  disclosure_version_id: ERSD_VERSION,
  date_as_of: "2026-10-09",
  paper_form_follows: false,
  signing_session: null,
  outcome: null,
  family: "engagement_letter",
  identity_method: "email_code",
  signers: [
    {
      id: DANA_E16,
      name: "Dana Kowalski",
      role: "signer",
      routing_group: 1,
      status: "viewed",
      signed_at: null,
      me: true,
    },
  ],
  signing_opens_on: "2026-10-09",
};
