// C7 in fixture mode for SIG-01 (N-02-T10; docs/contracts/c7-envelopes.md): the hub's list and
// summary on the live routes' shapes, from seed/signatures.ts, seen by Grace Holloway at E0 (Mon
// Sep 14, 2026, 9:24 AM CT). One scenario per artboard (a–g, r). Nothing here sends, voids or
// signs: Remind answers a preview only and Send is a person's (INV-1).
import type {
  EmailPreviewIn,
  EnvelopeListRow,
  EnvelopeOut,
  EnvelopeSummary,
  ImportRecordIn,
  ListPageEnvelopeListRow,
  RemindIn,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { meHandlers } from "../handlers";
import { clientHandlers } from "./clients";
import { contactHandlers } from "./contacts";
import {
  FROM_ADDRESS,
  FROM_DISPLAY,
  type TemplateSeed,
  renderEmail,
  templateOut,
  templateSeed,
  versionOut,
} from "../seed/email-templates";
import { getSeed } from "../seed";
import { stableId } from "../seed/prng";
import {
  COMPLETED,
  EXPIRED,
  HUB_COUNTS,
  type HubEnvelope,
  OUT,
  TO_SEND,
} from "../seed/signatures";

/** The by-type tile's consent bucket (C7 purpose code). */
const CONSENT_PURPOSE: EnvelopeListRow["purpose"] = "consent_7216";

export const SIG01_PERSONA = "grace-holloway";
export const SIG01_CLOCK = "2026-09-14T09:24:00-05:00";

type Tab = "to_send" | "out" | "completed" | "expired";

const PURPOSE: Readonly<Record<HubEnvelope["purpose"], EnvelopeListRow["purpose"]>> = {
  form_8879: "form_8879",
  engagement_letter: "engagement_letter",
  rep_letter: "rep_letter",
  consent_7216: "consent_7216",
  form_2848: "form_2848",
};

/** "Form 8879-PE · …" carries its form code; the 8879 family rides `form_8879` (C21). */
function formCode(title: string): string | null {
  const found = /^Form (8879-[A-Z]+)/.exec(title);
  return found?.[1] ?? null;
}

const noon = (day: string | null): string | null => (day === null ? null : `${day}T12:00:00Z`);

export function rowOf(e: HubEnvelope, status: HubEnvelope["status"] = e.status): EnvelopeListRow {
  const signed = e.signers.filter((x) => x.signed).length;
  return {
    id: stableId(`envelope:${e.key}`),
    number: e.key,
    purpose: PURPOSE[e.purpose],
    form_code: formCode(e.title),
    title: e.title,
    client_id: stableId(`client:${e.client}`),
    client_name: e.client,
    work_item_id: stableId(`work-item:${e.workItem}`),
    provider: "fake",
    status,
    signed,
    total: e.signers.length,
    sent_by_name: e.sent === null ? null : "Grace Holloway",
    sent_at: noon(e.sent),
    due_on: e.due,
    needs_handwritten: e.key === "E2",
    allowed_actions: status === "draft" ? ["envelope.send"] : ["envelope.remind", "envelope.void"],
    signer_chips: e.signers.map((x) => ({ name: x.name, signed: x.signed })),
    viewed_at: noon(e.viewed),
    work_item_label: e.workItem,
    note: e.note ?? null,
    drafted_by_name: e.draftedBy ?? null,
    outcome: e.outcome ?? null,
  };
}

function page(rows: readonly EnvelopeListRow[]): ListPageEnvelopeListRow {
  return { items: [...rows], total: rows.length };
}

export interface HubView {
  toSend: readonly HubEnvelope[];
  declined: string | null; // the Declined variant's envelope key (e)
}

export function summaryOf(view: HubView): EnvelopeSummary {
  return {
    to_send: view.toSend.length,
    out: HUB_COUNTS.out,
    completed: COMPLETED.length,
    expired: HUB_COUNTS.expired,
    needs_handwritten: 1,
    by_type: [
      { key: "efile", n: HUB_COUNTS.byType.efile },
      { key: "engagement_letter", n: HUB_COUNTS.byType.letters },
      { key: "rep_letter", n: HUB_COUNTS.byType.rep },
      { key: CONSENT_PURPOSE, n: HUB_COUNTS.byType.consents },
    ],
  };
}

/** The firm's `signature_reminder` template (DEC-1057): until the content pack gives reminder
 * wording, a reminder re-sends the designed signature request (POR-20's `signature_request`
 * blocks, verbatim), published as version 1. A firm edits it in POR-20. */
function reminderSeed(): TemplateSeed {
  const request = templateSeed("signature_request");
  if (request === undefined) throw new Error("the POR-20 seed has no signature_request");
  return {
    ...request,
    key: "signature_reminder",
    name: "Signature reminder",
    usedByLabel: "SIG-01 reminders",
  };
}

/** What Import signed package (r) records: a completed `record` envelope (DF-12). */
function importedOut(body: ImportRecordIn): EnvelopeOut {
  const id = stableId(`envelope:import:${body.title}`);
  return {
    row: {
      id,
      number: "E19",
      purpose: body.purpose,
      form_code: body.form_code ?? null,
      title: body.title,
      client_id: body.client_id,
      client_name: "",
      work_item_id: body.work_item_id ?? null,
      provider: "record",
      status: "completed",
      signed: body.signers.length,
      total: body.signers.length,
      sent_by_name: null,
      sent_at: null,
      due_on: null,
      needs_handwritten: false,
      allowed_actions: ["envelope.evidence_download"],
    },
    policy_family: body.purpose.startsWith("form_8879") ? "efile_authorization" : "general",
    source_kind: "record_import",
    source_id: id,
    engagement_id: body.engagement_id ?? null,
    signer_order: "sequential",
    date_as_of_mode: "none",
    date_as_of: null,
    expires_at: null,
    message: null,
    reminder_cadence: null,
    documents: [],
    signers: [],
    fields: [],
    evidence: [],
    provider_envelope_id: null,
    superseded_at: null,
    voided_reason: null,
    version: 1,
  };
}

export function signaturesHandlers(
  view: HubView = { toSend: TO_SEND, declined: null },
): Record<string, FixtureHandler> {
  const tabRows = (tab: Tab): EnvelopeListRow[] => {
    if (tab === "to_send") return view.toSend.map((e) => rowOf(e));
    if (tab === "completed") return COMPLETED.map((e) => rowOf(e));
    if (tab === "expired") return EXPIRED.map((e) => rowOf(e));
    return OUT.map((e) => rowOf(e, e.key === view.declined ? "declined" : e.status));
  };
  return {
    "GET /v1/envelopes": ({ query }) => {
      const tab = (query.get("tab") ?? "out") as Tab;
      return json(page(tabRows(tab)));
    },
    "GET /v1/envelopes/summary": () => json(summaryOf(view)),
    // f: the preview counts what would go; Send answers only when a person clicks it (INV-1).
    "POST /v1/envelopes/remind/preview": ({ body }) =>
      json({ count: (body as RemindIn).envelope_ids.length, skipped: [] }),
    "POST /v1/envelopes/remind/send": ({ body }) =>
      json({ count: (body as RemindIn).envelope_ids.length, skipped: [] }),
    "GET /v1/firm/email-templates/{key}": ({ params }) => {
      if (params.key !== "signature_reminder") return json({ code: "not_found" }, 404);
      const seed = reminderSeed();
      return json(templateOut(seed, { published: versionOut(seed, 1), draft: null }, []));
    },
    "POST /v1/firm/email-templates/{key}/preview": ({ params, body }) => {
      if (params.key !== "signature_reminder") return json({ code: "not_found" }, 404);
      const seed = reminderSeed();
      const given = (body ?? {}) as EmailPreviewIn;
      return json({
        ...renderEmail(seed.content, seed.sample.values, given.width ?? 600),
        from_display: FROM_DISPLAY,
        from_address: FROM_ADDRESS,
        reply_to: null,
        findings: [],
      });
    },
    // r: each file staged, then one import (DF-12).
    "POST /v1/envelopes/import/files": ({ query }) =>
      json(
        {
          id: stableId(`import-file:${query.get("filename") ?? ""}`),
          file_name: query.get("filename") ?? "",
          media_type: "application/pdf",
          size_bytes: 1,
          sha256: "0".repeat(64),
        },
        201,
      ),
    "POST /v1/envelopes/import": ({ body }) => json(importedOut(body as ImportRecordIn), 201),
    // N-02-T27 (DF-11): the hand-signed form recorded; the drawer re-reads the list after it.
    "POST /v1/envelopes/{envelope_id}/signers/{signer_id}/wet-signature": () => json({}),
  };
}

const base = (state: string, handlers: Record<string, FixtureHandler>): Scenario => ({
  state,
  persona: SIG01_PERSONA,
  clock: SIG01_CLOCK,
  // N-02-T15: the signed-in person (the reminder's Send is a person's, HumanAction).
  handlers: { ...meHandlers(), ...handlers },
});

/** SIG-01's artboards: a (E2 drawer), b, c, d, e (Declined variant on E9), f (E5, E8, E9
 * checked), g (empty To send) and r (the Import sheet; DF-12). The drawer, tab and selection are
 * the screen's state; the data is the same hub. */
export const SIG01_SCENARIOS = defineScenarios({
  a: base("a", signaturesHandlers()),
  b: base("b", signaturesHandlers()),
  c: base("c", signaturesHandlers()),
  d: base("d", signaturesHandlers()),
  e: base("e", signaturesHandlers({ toSend: TO_SEND, declined: "E9" })),
  f: base("f", signaturesHandlers()),
  g: base("g", signaturesHandlers({ toSend: [], declined: null })),
  r: base("r", {
    ...signaturesHandlers(),
    ...clientHandlers(getSeed()),
    ...contactHandlers(getSeed()),
  }),
});
