// ac-test-author: ayushkbhatia
// F-06-T07 (ADR-078): the independent suite for the T16 signing kit, written from F-06.md §3
// Stories 1.1 to 1.8 and the row, not from the code: one spouse cannot act on the other's fields,
// no agent element, no full TIN, the provider frame titled and sandboxed with return parameters
// never trusted, DF-11's copy with no retry. axe and the 390 geometry are in
// apps/web/e2e/screens/TPL-16.spec.ts.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import * as kit from "..";
import { PortalBrandProvider } from "../brand";
import { SigningCeremony } from "../templates/signing-ceremony/SigningCeremony";
import type { EnvelopeVM, SigningCeremonyProps, SigningOutcomeCopy } from "./types";

afterEach(cleanup);

const PAGE =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC";

const COPY: SigningOutcomeCopy = {
  verifyFailedTitle: "We couldn't verify your identity.",
  verifyFailedBody:
    "Harbor Lane will send you a paper form to sign by hand. If you have questions, contact Ruth Ames at Harbor Lane.",
  pendingTitle: "Checking your signature",
  pendingBody: "This page updates as soon as your signature is recorded.",
  providerTitle: "Verify your identity and sign: Form 8879",
  providerContinue: "Continue to verify",
  providerUnavailable: "Signing isn't available right now.",
  decline: {
    title: "Decline to sign?",
    reasons: ["The amounts look wrong", "Other"],
    reasonsLabel: "Why are you declining?",
    noteLabel: "Note",
    confirm: "Decline",
    trigger: "Decline…",
  },
  stepNames: { verify: "Verify", review: "Review", sign: "Sign", done: "Done" },
};

/** A joint envelope typed from the stories: Ann (viewer) and Ben, two fields each. */
function envelope(over: Partial<EnvelopeVM> = {}, annStatus = "verified"): EnvelopeVM {
  return {
    id: "env",
    title: "Form 8879 · TY2025 · Ann & Ben Lee",
    status: "partially_signed",
    signedCount: 1,
    signerCount: 2,
    documents: [
      {
        id: "d1",
        name: "Form 8879 — IRS e-file Signature Authorization",
        pages: [{ n: 1, width_pt: 612, height_pt: 792, src: PAGE, alt: "Form 8879, page 1" }],
        signerChips: [],
      },
    ],
    signers: [
      {
        id: "ann",
        name: "Ann Lee",
        isViewer: true,
        status: annStatus as EnvelopeVM["signers"][number]["status"],
        method: "kba",
        detail: "identity verified",
      },
      {
        id: "ben",
        name: "Ben Lee",
        isViewer: false,
        status: "pending",
        method: "kba",
        detail: "",
      },
    ],
    fields: [
      {
        id: "ann-sig",
        documentId: "d1",
        page: 1,
        rect: { x: 72, y: 600, w: 300, h: 26 },
        signerId: "ann",
        kind: "signature",
        label: "spouse signature",
      },
      {
        id: "ann-pin",
        documentId: "d1",
        page: 1,
        rect: { x: 72, y: 560, w: 120, h: 26 },
        signerId: "ann",
        kind: "pin",
        label: "spouse PIN",
      },
      {
        id: "ben-sig",
        documentId: "d1",
        page: 1,
        rect: { x: 72, y: 520, w: 300, h: 26 },
        signerId: "ben",
        kind: "signature",
        label: "taxpayer signature",
      },
      {
        id: "ben-pin",
        documentId: "d1",
        page: 1,
        rect: { x: 72, y: 480, w: 120, h: 26 },
        signerId: "ben",
        kind: "pin",
        label: "taxpayer PIN",
      },
    ],
    steps: [
      { key: "verify", state: "done", sub: "" },
      { key: "review", state: "done", sub: "" },
      { key: "sign", state: "current", sub: "" },
      { key: "done", state: "todo", sub: "" },
    ],
    ...over,
  };
}

function ceremony(props: Partial<SigningCeremonyProps> & { envelope: EnvelopeVM }) {
  return render(
    <PortalBrandProvider
      brand={{
        name: "Harbor Lane",
        mark: "wave",
        securedFooter: false,
        signInMethods: ["email_code"],
      }}
    >
      <SigningCeremony user="Ann Lee" backLabel="All documents to sign" copy={COPY} {...props} />
    </PortalBrandProvider>,
  );
}

describe("one spouse cannot act on the other's fields (INV-4, Story 1.2)", () => {
  it("only the viewer's open fields are controls; the other spouse's are never focusable", () => {
    const signed: string[] = [];
    ceremony({ envelope: envelope(), onSignField: (id) => signed.push(id) });
    const controls = screen.getAllByRole("button", { name: /^Sign here:/ });
    expect(controls.map((c) => c.getAttribute("data-field")).sort()).toEqual([
      "ann-pin",
      "ann-sig",
    ]);
    for (const id of ["ben-sig", "ben-pin"]) {
      const node = document.querySelector(`[data-field="${id}"]`);
      expect(node?.tagName).not.toBe("BUTTON");
      expect(node?.getAttribute("tabindex")).toBeNull();
    }
    for (const control of controls) control.click();
    expect(signed.every((id) => id.startsWith("ann-"))).toBe(true);
  });

  it("a viewer who is not a signer sees no page and no field", () => {
    const e = envelope();
    ceremony({ envelope: { ...e, signers: e.signers.map((s) => ({ ...s, isViewer: false })) } });
    expect(document.querySelector('[data-signing="restricted"]')).toBeTruthy();
    expect(document.querySelector('[data-signing="page"]')).toBeNull();
  });
});

describe("no agent element and no full TIN (INV-1, INV-5, Story 1.3, 1.8)", () => {
  it.each(["b", "phone", "failed", "completed"])("state %s carries no agent marker", (state) => {
    const base = envelope();
    const env =
      state === "completed"
        ? {
            ...base,
            status: "completed" as const,
            evidence: [{ label: "Signed", value: "Sep 14" }],
          }
        : state === "failed"
          ? envelope({ outcome: "verification_failed" }, "verification_failed")
          : base;
    ceremony({ envelope: env, ...(state === "phone" ? { layout: "phone" as const } : {}) });
    expect(
      document.querySelector("[data-agent],[data-actor-kind='agent'],[data-agent-text]"),
    ).toBeNull();
    expect(document.body.textContent).not.toMatch(/Accrued|via Agent|Agent run/);
    expect(document.body.textContent).not.toMatch(/\b\d{3}-\d{2}-\d{4}\b/);
  });
});

describe("the provider frame (DF-12, Story 1.1)", () => {
  const session = (url: string) =>
    envelope({
      steps: [
        { key: "verify", state: "current", sub: "" },
        { key: "review", state: "todo", sub: "" },
        { key: "sign", state: "todo", sub: "" },
        { key: "done", state: "todo", sub: "" },
      ],
      signingSession: { url, presentation: "iframe", expiresAt: "2026-09-14T15:00:00Z" },
    });

  it("is titled and sandboxed without top navigation", () => {
    ceremony({ envelope: session("https://provider.example/s/1") });
    const frame = document.querySelector("iframe");
    expect(frame?.getAttribute("title")).toBe(COPY.providerTitle);
    const sandbox = (frame?.getAttribute("sandbox") ?? "").split(/\s+/);
    expect(sandbox).toContain("allow-scripts");
    expect(sandbox.some((t) => t.startsWith("allow-top-navigation"))).toBe(false);
  });

  it.each(["javascript:alert(1)", "http://provider.example/s/1", "data:text/html,x", "nonsense"])(
    "never hosts %s",
    (url) => {
      ceremony({ envelope: session(url) });
      expect(document.querySelector("iframe")).toBeNull();
    },
  );

  it("a return parameter never shows Completed while the server says unsigned", () => {
    ceremony({ envelope: envelope(), providerReturned: true });
    expect(document.querySelector('[data-signing="pending-confirmation"]')).toBeTruthy();
    expect(document.querySelector('[data-signing="evidence"]')).toBeNull();
    expect(screen.queryByText(/Completed/)).toBeNull();
  });
});

describe("DF-11 (Story 1.4)", () => {
  it("names the paper form and the contact, with no retry or countdown", () => {
    ceremony({ envelope: envelope({ outcome: "verification_failed" }, "verification_failed") });
    const card = document.querySelector('[data-signing="verification-failed"]');
    expect(card?.textContent).toContain("paper form");
    expect(card?.textContent).toContain("Ruth Ames");
    expect(card?.querySelectorAll("button, a")).toHaveLength(0);
    expect(document.body.textContent).not.toMatch(/try again|tomorrow|\d+:\d\d remaining/i);
  });
});

describe("no native identity component is exported (Story 1.7)", () => {
  it("has no KBA card, email-code card, adopt dialog or native adapter", () => {
    const names = Object.keys(kit);
    for (const banned of [
      "KbaCard",
      "EmailCodeCard",
      "AdoptSignatureDialog",
      "NativeIdentityAdapter",
    ]) {
      expect(names).not.toContain(banned);
    }
  });
});
