// The portal's signing seed for POR-06 (N-02-T26; docs/screens/POR-06.md; handoff POR-06 README
// and spec): Owen Calder (Ridgeline Property Partners, LP) at E0, Mon Sep 14, 2026, 9:24 AM CT,
// on E13, the cost segregation and section 754 engagement letter Daniel Reyes sent at 8:40 AM, due
// Sep 24, three pages, Owen signs first and Daniel countersigns. Signed band: the 2025 Form 1065
// engagement letter and the two §7216 consents, each its own document (Rev. Proc. 2013-14 §5.05),
// signed Feb 6, 2026. C7's portal shapes only (`PortalEnvelopeView`, `PortalEnvelopeRow`): no name
// of another signer, no evidence record (C7 v1 does not carry them; N-02-T25 adds them).
import type { FieldOut, PortalEnvelopeRow, PortalEnvelopeView } from "@abacus/api-client";
import { stableId } from "./prng";

export const POR06_PERSONA = "owen-calder";

/** a, b, g, the list: E0. c: the return at 9:31 AM, when Owen has signed (POR-06 README). */
export const POR06_CLOCK = "2026-09-14T09:24:00-05:00";
export const POR06_SIGNED_CLOCK = "2026-09-14T09:31:00-05:00";

export const E13_ID = stableId("envelope:E13");
const E13_LETTER = stableId("envelope-document:E13:letter");
const OWEN_SIGNER = stableId("envelope-signer:E13:owen-calder");

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
