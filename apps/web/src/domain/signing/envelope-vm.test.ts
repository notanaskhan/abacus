import type { PortalEnvelopeView } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { DECLINE_CODES, outcomeOf, pagePath, toEnvelopeVM } from "./envelope-vm";

// F-06-T09: C7's portal envelope view onto EnvelopeVM. The fixture is typed by the generated
// client, so a renamed or retyped C7 field fails `tsc` here as the provider's test fails CI there.

const VIEW: PortalEnvelopeView = {
  row: {
    id: "e6",
    title: "Form 8879 · TY2025 · Dev & Mira Kapoor",
    status: "partially_signed",
    my_status: "verified",
    due_on: "2026-10-05",
  },
  documents: [
    {
      id: "tr579",
      order: 2,
      title: "Form TR-579-IT",
      page_count: 1,
      sha256: null,
      read_only: false,
      tri: true,
    },
    {
      id: "f8879",
      order: 1,
      title: "Form 8879",
      page_count: 2,
      sha256: null,
      read_only: false,
      tri: true,
    },
  ],
  my_fields: [
    {
      id: "f1",
      document_id: "f8879",
      signer_id: "mira",
      kind: "signature",
      page: 1,
      x: 72,
      y: 600,
      w: 300,
      h: 26,
      anchor: null,
    },
    {
      id: "f2",
      document_id: "f8879",
      signer_id: "mira",
      kind: "title_prefill",
      page: 1,
      x: 72,
      y: 640,
      w: 300,
      h: 26,
      anchor: null,
    },
  ],
  signers_signed: 1,
  signers_total: 2,
  esign_consent_needed: false,
  disclosure_version_id: null,
  date_as_of: null,
  paper_form_follows: false,
  signing_session: {
    session_id: "s1",
    presentation: "iframe",
    url: "https://provider.example/s/1",
    expires_at: "2026-09-14T15:00:00Z",
  },
  family: "efile_authorization",
  identity_method: "kba",
  signers: [],
  signing_opens_on: null,
};

const EXTRA = {
  viewer: {
    id: "mira",
    name: "Mira Kapoor",
    isViewer: true,
    status: "verified" as const,
    method: "kba" as const,
    detail: "",
  },
  steps: [],
  fieldLabels: { signature: "spouse signature", pin: "spouse PIN", date: "date" },
};

describe("toEnvelopeVM", () => {
  it("takes counts, status and pages from the server, in document order", () => {
    const vm = toEnvelopeVM(VIEW, EXTRA);
    expect(vm.signedCount).toBe(1);
    expect(vm.signerCount).toBe(2);
    expect(vm.status).toBe("partially_signed");
    expect(vm.documents.map((d) => d.id)).toEqual(["f8879", "tr579"]);
    expect(vm.documents[0]?.pages.map((p) => p.src)).toEqual([
      pagePath("e6", "f8879", 1),
      pagePath("e6", "f8879", 2),
    ]);
  });

  it("maps only the viewer's signable fields, all as the viewer's", () => {
    const vm = toEnvelopeVM(VIEW, EXTRA);
    expect(vm.fields.map((f) => [f.id, f.signerId, f.kind])).toEqual([
      ["f1", "mira", "signature"],
    ]);
  });

  it("carries the provider session and DF-11's paper-form path", () => {
    expect(toEnvelopeVM(VIEW, EXTRA).signingSession?.presentation).toBe("iframe");
    expect(outcomeOf({ ...VIEW, paper_form_follows: true })).toBe("verification_failed");
    expect(outcomeOf({ ...VIEW, outcome: "declined" })).toBe("declined");
    expect(outcomeOf(VIEW)).toBeUndefined();
  });

  it("maps every kit decline reason to a C7 code", () => {
    expect(Object.values(DECLINE_CODES).sort()).toEqual(
      ["have_questions", "other", "someone_else_should_sign", "something_wrong"].sort(),
    );
  });
});
