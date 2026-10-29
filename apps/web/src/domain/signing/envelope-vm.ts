// C7's portal envelope view mapped onto the T16 kit's EnvelopeVM (F-06-T09; F-06.md §5.2; C7
// `docs/contracts/c7-envelopes.md`). The kit draws only what this returns; every count, status and
// date is the server's. The fields read here are pinned on the provider's side by
// `backend/tests/contracts/c7_n02/test_f06_consumer.py`, so a breaking change to any of them fails
// the backend's CI before the signing kit breaks.
//
// What C7 v1 does not carry yet (the other signers' names and fields, the steps' sub-lines, the
// authorizing text, the evidence record) comes from `extra`, which N-02's POR-06 container fills
// from its other reads; a missing reserved field is an additive C7 change (types.ts), never a kit
// workaround.
import type {
  FieldOut,
  PortalEnvelopeView,
  SignerDeclineIn,
  SigningSessionOut,
} from "@abacus/api-client";
import type {
  EnvelopeOutcome,
  EnvelopeVM,
  SignFieldVM,
  SignerVM,
  SigningDocumentVM,
  SigningSession,
  SigningStepVM,
} from "@abacus/ui";

/** The page a signer reviews: a same-origin image path (C7 portal page route, E5 pipeline). */
export function pagePath(envelopeId: string, documentId: string, n: number): string {
  return `/v1/portal/envelopes/${envelopeId}/documents/${documentId}/pages/${String(n)}`;
}

/** PDF points of a US Letter page; C7 v1 sends no page size, every 8879-family page is Letter. */
const LETTER = { width_pt: 612, height_pt: 792 } as const;

export function session(out: SigningSessionOut): SigningSession {
  return { url: out.url, presentation: out.presentation, expiresAt: out.expires_at };
}

/** DF-11: a signer whose identity failed is told a paper form follows; C7's `outcome` names how
 * the ceremony ended for the viewer. */
export function outcomeOf(view: PortalEnvelopeView): EnvelopeOutcome | undefined {
  if (view.paper_form_follows || view.row.my_status === "verification_failed") {
    return "verification_failed";
  }
  if (view.outcome === "declined" || view.row.status === "declined") return "declined";
  if (view.row.status === "expired") return "expired";
  if (view.row.status === "voided") return "voided";
  return undefined;
}

/** The kit's four decline reasons (TPL-16f copy, in order) and C7's codes. */
export const DECLINE_CODES: Readonly<Record<string, SignerDeclineIn["reason"]>> = {
  "The amounts look wrong": "something_wrong",
  "I have a question first": "have_questions",
  "Someone else should sign": "someone_else_should_sign",
  Other: "other",
};

function field(out: FieldOut, viewerId: string, label: string): SignFieldVM | null {
  if (out.kind !== "signature" && out.kind !== "pin" && out.kind !== "date") return null;
  return {
    id: out.id,
    documentId: out.document_id,
    page: out.page,
    rect: { x: out.x, y: out.y, w: out.w, h: out.h },
    signerId: viewerId,
    kind: out.kind,
    label,
  };
}

export interface EnvelopeExtra {
  /** The viewer's signer id in C7 (`my_fields[].signer_id`); every field here is the viewer's. */
  viewer: SignerVM;
  /** The other signers, read-only, from N-02's envelope read. */
  others?: readonly SignerVM[];
  /** Other signers' filled fields, read-only. */
  otherFields?: readonly SignFieldVM[];
  steps: readonly SigningStepVM[];
  /** The accessible label of each of the viewer's fields, by kind. */
  fieldLabels: Readonly<Record<"signature" | "pin" | "date", string>>;
  authorizing?: EnvelopeVM["authorizing"];
  evidence?: EnvelopeVM["evidence"];
  /** Document chips, by document id. */
  chips?: Readonly<Record<string, SigningDocumentVM["signerChips"]>>;
}

export function toEnvelopeVM(view: PortalEnvelopeView, extra: EnvelopeExtra): EnvelopeVM {
  const id = view.row.id;
  const outcome = outcomeOf(view);
  const mine = view.my_fields
    .map((f) => {
      const kind = f.kind === "signature" || f.kind === "pin" || f.kind === "date" ? f.kind : null;
      return kind === null ? null : field(f, extra.viewer.id, extra.fieldLabels[kind]);
    })
    .filter((f): f is SignFieldVM => f !== null);
  return {
    id,
    title: view.row.title,
    status: view.row.status,
    signedCount: view.signers_signed,
    signerCount: view.signers_total,
    documents: [...view.documents]
      .sort((a, b) => a.order - b.order)
      .map((d) => ({
        id: d.id,
        name: d.title,
        pages: Array.from({ length: d.page_count }, (_, i) => ({
          n: i + 1,
          ...LETTER,
          src: pagePath(id, d.id, i + 1),
          alt: `${d.title}, page ${String(i + 1)}`,
        })),
        signerChips: extra.chips?.[d.id] ?? [],
      })),
    signers: [{ ...extra.viewer, status: view.row.my_status }, ...(extra.others ?? [])],
    fields: [...mine, ...(extra.otherFields ?? [])],
    steps: extra.steps,
    ...(extra.authorizing === undefined ? {} : { authorizing: extra.authorizing }),
    ...(view.signing_session ? { signingSession: session(view.signing_session) } : {}),
    ...(extra.evidence === undefined ? {} : { evidence: extra.evidence }),
    ...(outcome === undefined ? {} : { outcome }),
  };
}
