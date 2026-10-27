import {
  type EnvelopeVM,
  type PortalBrand,
  PortalBrandProvider,
  type SigningCeremonyProps,
  SigningCeremony,
} from "@abacus/ui";
import type { JSX } from "react";
import { E6, E6_SIGNERS } from "../../../fixtures/seed/tax";
import type { FixtureParams } from "../../fixture-mode";
import { COPY } from "./copy";

// TPL-16 signing ceremony specimen (F-06-T04; docs/screens/TPL-16.md): Mira Kapoor on envelope E6,
// b (signing, Dev signed Sep 9) and d (completed, six evidence items), from the tax seed. a and c
// are Tier C screenshots (DF-12); e, f and g are F-06-T05/T06's. The page is a synthetic blank
// page image until the server's render reaches fixtures (DECISIONS.md, F-06-T04). Registered for
// /components/screens/TPL-16?st=b|d.

export const TPL16_STATES = ["b", "d"] as const;
export type Tpl16State = (typeof TPL16_STATES)[number];

const BLANK_PAGE =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="612" height="792" viewBox="0 0 612 792"><rect width="612" height="792" fill="white"/></svg>',
  );

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
          status: done ? "signed" : "waiting",
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
        status: done ? "signed" : "verified",
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

const BRAND: PortalBrand = {
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
        {...rest}
      />
    </PortalBrandProvider>
  );
}

export function Tpl16Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: Tpl16State = TPL16_STATES.find((s) => s === params.st) ?? "b";
  return <Tpl16Specimen state={state} frame={params.frame} height={860} />;
}
