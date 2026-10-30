import {
  type EnvelopeVM,
  type PortalBrand,
  PortalBrandProvider,
  type SigningCeremonyProps,
  SigningCeremony,
  type SigningOutcomeCopy,
} from "@abacus/ui";
import type { JSX } from "react";
import { E6, E6_SIGNERS } from "../../../fixtures/seed/tax";
import type { FixtureParams } from "../../fixture-mode";
import { COPY } from "./copy";

// TPL-16 signing ceremony specimen (F-06-T04 to T06; docs/screens/TPL-16.md): Mira Kapoor on envelope
// E6 from the tax seed: b (signing, Dev signed Sep 9), d (completed, six evidence items), e
// (verification failed, DF-11), f (decline), g (390) and `pending` (the provider returned, the
// server not yet). a and c are Tier C screenshots (DF-12): no native identity component exists.
// The page is a synthetic blank page image until the server's render reaches fixtures
// (DECISIONS.md, F-06-T04). Registered for /components/screens/TPL-16?st=b|d|e|f|g|pending.

export const TPL16_STATES = ["b", "d", "e", "f", "g", "pending"] as const;
export type Tpl16State = (typeof TPL16_STATES)[number];

const BLANK_PAGE =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC";

const [DEV, MIRA] = E6_SIGNERS as readonly [
  (typeof E6_SIGNERS)[number],
  (typeof E6_SIGNERS)[number],
];
const [F8879, TR579] = E6.documents;

/** "$2,296" from the seed's decimal string: a display string, no arithmetic. */
function dollars(value: string): string {
  return `$${value.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`;
}

export function e6Envelope(state: Tpl16State): EnvelopeVM {
  const done = state === "d";
  const failedIdentity = state === "e";
  const devSigned = "Dev Kapoor · signed electronically Sep 9, 2026";
  const miraSigned = "Mira Kapoor · signed electronically Sep 14, 2026";
  return {
    id: "e6",
    title: COPY.title,
    status: done ? "completed" : "partially_signed",
    signedCount: done ? 2 : 1,
    signerCount: 2,
    documents: [F8879, TR579].map((d) => ({
      id: d.id,
      name: d.name,
      pages: [
        {
          n: 1,
          width_pt: 612,
          height_pt: 792,
          src: BLANK_PAGE,
          alt: `${d.name.split(" — ")[0] ?? d.name}, page 1`,
        },
      ],
      signerChips: [
        { signerId: DEV.id, name: DEV.first, status: "signed", date: "Sep 9" },
        {
          signerId: MIRA.id,
          name: MIRA.first,
          status: done ? "signed" : "pending",
          ...(done ? { date: "Sep 14" } : {}),
        },
      ],
    })),
    signers: [
      {
        id: DEV.id,
        name: DEV.name,
        isViewer: false,
        status: "signed",
        method: DEV.method,
        detail: "✓ Signed Sep 9, 6:12 PM · identity verified",
      },
      {
        id: MIRA.id,
        name: MIRA.name,
        isViewer: true,
        status: done ? "signed" : failedIdentity ? "verification_failed" : "verified",
        method: MIRA.method,
        detail: done
          ? "✓ Signed Sep 14, 9:24 AM · identity verified"
          : "identity verified 9:21 AM · 2 fields left",
      },
    ],
    fields: [F8879, TR579].flatMap((d) => [
      {
        id: `${d.id}-dev`,
        documentId: d.id,
        page: 1,
        rect: { x: 72, y: 520, w: 300, h: 26 },
        signerId: DEV.id,
        kind: "signature" as const,
        label: "taxpayer signature",
        filled: devSigned,
      },
      {
        id: `${d.id}-mira`,
        documentId: d.id,
        page: 1,
        rect: { x: 72, y: 600, w: 300, h: 26 },
        signerId: MIRA.id,
        kind: "signature" as const,
        label: "spouse signature",
        ...(done ? { filled: miraSigned } : {}),
      },
    ]),
    steps: [
      { key: "verify", state: "done", sub: COPY.stepSubs.verify },
      { key: "review", state: "done", sub: COPY.stepSubs.review },
      { key: "sign", state: done ? "done" : "current", sub: done ? "" : COPY.stepSubs.sign },
      { key: "done", state: done ? "done" : "todo", sub: "" },
    ],
    authorizing: {
      title: COPY.authorizingTitle,
      body: `You authorize ${E6.firm} to file your 2025 federal and New York returns electronically. Your federal refund is ${dollars(E6.partI.refund)} and your New York refund is ${dollars(E6.nyRefund)}.`,
    },
    ...(failedIdentity ? { outcome: "verification_failed" as const } : {}),
    ...(done
      ? {
          evidence: E6.evidence.map((e) => ({
            label: COPY.evidenceLabels[e.key],
            value: e.value,
          })),
        }
      : {}),
  };
}

export const OUTCOME_COPY: SigningOutcomeCopy = {
  verifyFailedTitle: COPY.verifyFailedTitle,
  verifyFailedBody: COPY.verifyFailedBody(E6.firm, E6.preparer),
  pendingTitle: COPY.pendingTitle,
  pendingBody: COPY.pendingBody,
  providerTitle: COPY.providerTitle("Form 8879"),
  providerContinue: COPY.providerContinue,
  providerUnavailable: COPY.providerUnavailable,
  decline: {
    title: COPY.declineTitle,
    reasons: COPY.declineReasons,
    reasonsLabel: COPY.declineReasonsLabel,
    noteLabel: COPY.declineNote,
    confirm: COPY.declineConfirm,
    trigger: COPY.decline,
  },
  stepNames: COPY.stepNames,
};

export const BRAND: PortalBrand = {
  name: E6.firm,
  mark: "wave",
  securedFooter: false,
  signInMethods: ["email_code"],
};

export function Tpl16Specimen({
  state,
  ...rest
}: { state: Tpl16State } & Partial<SigningCeremonyProps>): JSX.Element {
  return (
    <PortalBrandProvider brand={BRAND}>
      <SigningCeremony
        envelope={e6Envelope(state)}
        user={MIRA.name}
        backLabel={COPY.back}
        completion={{ title: COPY.completedTitle(MIRA.first), note: COPY.willFile(E6.firm) }}
        copy={OUTCOME_COPY}
        onDecline={() => undefined}
        {...(state === "f" ? { declineForceState: "open" as const, declineHeldScrim: true } : {})}
        {...(state === "g" ? { layout: "phone" as const, stickyBarHeight: 64 as const } : {})}
        {...(state === "pending" ? { providerReturned: true } : {})}
        {...rest}
      />
    </PortalBrandProvider>
  );
}

export function Tpl16Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: Tpl16State = TPL16_STATES.find((s) => s === params.st) ?? "b";
  return <Tpl16Specimen state={state} frame={params.frame} height={state === "g" ? 844 : 860} />;
}
