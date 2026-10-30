// The T16 signing kit's prop API (F-06-T04; F-06.md §5.2, SPEC-400 AC-1…AC-8): the contract the
// F-06-T07 acceptance tests and N-02's POR-06 container build against. L2 rule: generic shapes
// only, no @abacus/api-client types, no role names. N-02 maps C7's PortalEnvelopeView onto
// EnvelopeVM (C7 v1 has not merged; a missing reserved field is an additive C7 change, not a kit
// workaround). Counts, statuses and TINs are server values: the kit never counts, never unmasks.

import type { ReactNode } from "react";
import type { PortalNavItem } from "../layout/portal-toolbar";
import type { RegistryCode } from "../status";

/** A page of a document as the server renders it (E5 pipeline, ADR-052): an image, never a file
 * to parse. Sizes in PDF points. */
export interface SigningPage {
  n: number;
  width_pt: number;
  height_pt: number;
  /** A same-origin URL, or a data URL in fixtures. */
  src: string;
  /** What the page shows, for assistive technology ("Form 8879, page 1"). */
  alt: string;
}

/** A field box in PDF points, top-left origin. */
export interface FieldRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface SignerChipVM {
  signerId: string;
  /** The short name the chip shows ("Dev"). */
  name: string;
  status: RegistryCode<"envelope_signer">;
  /** The chip's date for a signed signer ("Sep 9"). */
  date?: string;
}

export interface SigningDocumentVM {
  id: string;
  name: string;
  pages: readonly SigningPage[];
  signerChips: readonly SignerChipVM[];
}

export type IdentityMethod = "kba" | "email_code" | "in_person_id";

export interface SignerVM {
  id: string;
  name: string;
  isViewer: boolean;
  status: RegistryCode<"envelope_signer">;
  method: IdentityMethod;
  /** The signer band's line, from the server ("✓ Signed Sep 9, 6:12 PM · identity verified"). */
  detail: string;
}

export type FieldKind = "pin" | "signature" | "date";

export interface SignFieldVM {
  id: string;
  documentId: string;
  page: number;
  rect: FieldRect;
  signerId: string;
  kind: FieldKind;
  /** What the field says once filled ("Dev Kapoor · signed electronically Sep 9, 2026"). */
  filled?: string;
  /** The accessible name of the open field ("spouse signature"); the kit adds the document and
   * page ("Sign here: spouse signature, Form 8879, page 1"). */
  label: string;
}

export type StepKey = RegistryCode<"signing_step">;

export interface SigningStepVM {
  key: StepKey;
  state: "done" | "current" | "todo";
  sub: string;
}

/** Firm or template text only, never model text (ADR-111, DEC-79). */
export interface AuthorizingVM {
  title: string;
  body: string;
}

export interface EvidenceItem {
  label: string;
  value: string;
}

export interface SigningSession {
  url: string;
  presentation: "iframe" | "redirect";
  expiresAt: string;
}

export type EnvelopeOutcome = "verification_failed" | "declined" | "expired" | "voided";

export interface EnvelopeVM {
  id: string;
  title: string;
  status: RegistryCode<"envelope">;
  /** "1 of 2 signed": server values, never counted in the browser. */
  signedCount: number;
  signerCount: number;
  documents: readonly SigningDocumentVM[];
  signers: readonly SignerVM[];
  /** Provider tagging may omit fields (DF-12). */
  fields: readonly SignFieldVM[];
  steps: readonly SigningStepVM[];
  authorizing?: AuthorizingVM;
  /** Provider mode: the session N-02 opens. F-06-T05 hosts it in ProviderSigningFrame. */
  signingSession?: SigningSession;
  /** Six items once the envelope is completed (TPL-16d). */
  evidence?: readonly EvidenceItem[];
  outcome?: EnvelopeOutcome;
}

export interface SigningCompletionVM {
  /** "Signed. Thank you, Mira." */
  title: string;
  /** "Brightwater Hale will file your returns and message you when they're accepted." */
  note?: string;
}

/** F-06-T05, F-06-T06: the identity, exception and phone states' words, from the screen's copy
 * module (the kit holds no copy of its own). */
export interface SigningOutcomeCopy {
  /** DF-11 (TPL-16e): the title and the paper-form text naming the firm's contact. */
  verifyFailedTitle: string;
  verifyFailedBody: string;
  /** After the provider returns, until the server confirms the signature (Story 1.1). */
  pendingTitle: string;
  pendingBody: string;
  /** ProviderSigningFrame: the frame's title, the redirect call to action, and a URL it can't
   * host. */
  providerTitle: string;
  providerContinue: string;
  providerUnavailable: string;
  decline: {
    title: string;
    reasons: readonly string[];
    reasonsLabel: string;
    noteLabel: string;
    confirm: string;
    trigger: string;
  };
  /** The 390 step chips' names. */
  stepNames: Readonly<Record<StepKey, string>>;
}

export interface SigningCeremonyProps {
  envelope: EnvelopeVM;
  /** The signed-in person (the toolbar's user chip). The firm's name comes from the portal brand
   * (white label: never the product's). */
  user: string;
  /** The portal nav the app gives the viewer; default: an individual client's. */
  nav?: readonly PortalNavItem[];
  /** "All documents to sign". Without it the header draws no back control (the T16 frames). */
  backLabel?: string;
  /** The signers card under the documents; default true (TPL-16). T16's frames draw none. */
  showSigners?: boolean;
  /** The documents column's centred title; default "Documents (n)". T16 draws "Documents". */
  documentsTitle?: string;
  /** A centred title over the steps column ("Steps", T16); default none (TPL-16). */
  stepsTitle?: string;
  /** Replaces the sign call to action in the steps column: the native adopt panel the T16 frames
   * draw (a specimen; production signs in the provider's view, DF-12). */
  signPanel?: ReactNode;
  completion?: SigningCompletionVM;
  /** Envelope state outside the data: the query is loading or failed. */
  view?: "ready" | "loading" | "error";
  onBack?: () => void;
  /** The verify step's call to action (provider mode starts the session). */
  onContinueToVerify?: () => void;
  /** A viewer's open field, or the sign call to action with the next open field. */
  onSignField?: (fieldId: string) => void;
  /** Opens the decline dialog (F-06-T05 owns the dialog). */
  onOpenDecline?: () => void;
  onDownload?: () => void;
  onRetry?: () => void;
  /** A signer chip opens SIG-01 for the firm; the portal passes nothing. */
  onOpenSignatures?: (envelopeId: string) => void;
  /** Presentation only (the gallery): a 1400 window, or a 390 phone. */
  frame?: boolean;
  height?: number;
  /** F-06-T05, F-06-T06: the identity, exception and phone states' words. */
  copy?: SigningOutcomeCopy;
  /** F-06-T06: 390 (TPL-16g, TPL-19 frame 9, POR-06 on a phone). */
  layout?: "desktop" | "phone";
  /** The phone's sticky bar: 64 (TPL-16g, POR-06) or 72 (TPL-19 frame 9). */
  stickyBarHeight?: 64 | 72;
  /** The provider sent the signer back (the return URL's event parameter). A hint only: the kit
   * shows Completed only when the server's envelope says so (Story 1.1). */
  providerReturned?: boolean;
  /** Decline with a reason (TPL-16f): called once per confirmation. Given the outcome words, the kit owns the
   * dialog; `declineForceState` holds it open for a specimen. */
  onDecline?: (choice: { reason: string; note: string }) => void;
  declineForceState?: "open";
  /** N-02-T26 (POR-06): the container's own step control, drawn under the steps at 1400 and as
   * the sticky footer at 390, in place of the kit's sign call to action: "Continue to sign" while
   * the viewer reviews, the e-sign consent card, "Withdraw decline". The kit adds no behaviour. */
  action?: ReactNode;
  /** N-02-T26: a page of the shown document came at least half into view (review progress: POR-06
   * enables "Continue to sign" once the last page has been seen). */
  onPageSeen?: (documentId: string, page: number) => void;
  /** N-02-T26: a portal nav item (the app's area routing). */
  onNavigate?: (label: string) => void;
  /** With `declineForceState`: the held dialog sits over the frame on the scrim (TPL-16f). */
  declineHeldScrim?: boolean;
}
