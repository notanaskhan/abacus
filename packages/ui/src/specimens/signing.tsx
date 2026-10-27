import type { JSX } from "react";
import { PortalBrandProvider } from "../brand";
import type { EnvelopeVM, SignerVM, SigningStepVM } from "../signing/types";
import { SigningCeremony } from "../templates/signing-ceremony/SigningCeremony";
import { Artboard, BRIGHTWATER_BRAND } from "./portal";

// T16 signing ceremony (F-06-T04; docs/screens/T16.md): the template board's placeholder data,
// Claire Feld signing the couple's e-file authorizations (the T16 canvas `T16.LINES`,
// `T16.EVIDENCE`). b and c are built; a (the email-code card) is a Tier C screenshot only, because
// identity runs in the provider's view (DF-11, DF-12). The page is a synthetic blank page image:
// the form face is the server's render, which no fixture carries yet (DECISIONS.md, F-06-T04).

/** A blank page image (a white PNG, which E5 allows) as a data URL, the stand-in for the server's page render. */
export const BLANK_PAGE =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC";

const page = (alt: string) => ({ n: 1, width_pt: 612, height_pt: 792, src: BLANK_PAGE, alt });

const JONAH = "t16-jonah";
const CLAIRE = "t16-claire";

function signers(claireSigned: boolean): SignerVM[] {
  return [
    {
      id: JONAH,
      name: "Jonah Feld",
      isViewer: false,
      status: "signed",
      method: "email_code",
      detail: "✓ Signed · identity verified",
    },
    {
      id: CLAIRE,
      name: "Claire Feld",
      isViewer: true,
      status: claireSigned ? "signed" : "verified",
      method: "email_code",
      detail: claireSigned ? "✓ Signed Sep 14, 9:24 AM" : "identity verified · 1 field left",
    },
  ];
}

const STEPS_SIGN: SigningStepVM[] = [
  { key: "verify", state: "done", sub: "Email code · 9:21 AM" },
  { key: "review", state: "done", sub: "1 document" },
  { key: "sign", state: "current", sub: "1 field left" },
  { key: "done", state: "todo", sub: "" },
];

export function t16Envelope(state: "b" | "c"): EnvelopeVM {
  const done = state === "c";
  return {
    id: "t16-feld",
    title: "2025 e-file authorizations",
    status: done ? "completed" : "partially_signed",
    signedCount: done ? 2 : 1,
    signerCount: 2,
    documents: [
      {
        id: "t16-8879",
        name: "Form 8879 — IRS e-file Signature Authorization",
        pages: [page("Form 8879, page 1")],
        signerChips: [
          { signerId: JONAH, name: "Jonah", status: "signed" },
          { signerId: CLAIRE, name: "Claire", status: done ? "signed" : "waiting" },
        ],
      },
    ],
    signers: signers(done),
    fields: [
      {
        id: "t16-jonah-sig",
        documentId: "t16-8879",
        page: 1,
        rect: { x: 72, y: 520, w: 300, h: 26 },
        signerId: JONAH,
        kind: "signature",
        label: "taxpayer signature",
        filled: "Jonah Feld · signed electronically",
      },
      {
        id: "t16-claire-sig",
        documentId: "t16-8879",
        page: 1,
        rect: { x: 72, y: 600, w: 300, h: 26 },
        signerId: CLAIRE,
        kind: "signature",
        label: "spouse signature",
        ...(done ? { filled: "Claire Feld · signed electronically Sep 14, 2026" } : {}),
      },
    ],
    steps: done ? STEPS_SIGN.map((s) => ({ ...s, state: "done" as const })) : STEPS_SIGN,
    ...(done
      ? {
          evidence: [
            { label: "Signed by", value: "Jonah Feld · Claire Feld" },
            { label: "Last signature", value: "Sep 14, 2026 · 9:24 AM CT" },
            { label: "Identity", value: "Email code to each signer" },
            { label: "IP address", value: "73.•••.•••.18" },
            { label: "Fingerprint", value: "SHA-256 4f1c…9a2e" },
          ],
        }
      : {}),
  };
}

export function T16Specimen(): JSX.Element {
  return (
    <PortalBrandProvider brand={BRIGHTWATER_BRAND}>
      <div className="flex flex-col gap-6">
        <Artboard
          id="t16a"
          badge="T16a"
          name="Verify identity"
          note="Tier C screenshot only: identity runs in the provider's view (DF-11, DF-12)"
        >
          <p className="text-dense text-ink-2">
            The native email-code card is not built. Compare against the handoff screenshot.
          </p>
        </Artboard>
        <Artboard
          id="t16b"
          badge="T16b"
          name="Sign"
          note="1 of 2 signed: Claire's field carries the Sign here tab"
        >
          <SigningCeremony
            envelope={t16Envelope("b")}
            user="Claire Feld"
            backLabel="All documents to sign"
            frame
            height={860}
          />
        </Artboard>
        <Artboard id="t16c" badge="T16c" name="Done" note="Both signed, with the evidence summary">
          <SigningCeremony
            envelope={t16Envelope("c")}
            user="Claire Feld"
            backLabel="All documents to sign"
            completion={{ title: "Signed. Thank you, Claire." }}
            frame
            height={860}
          />
        </Artboard>
      </div>
    </PortalBrandProvider>
  );
}
