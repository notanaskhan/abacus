// C7 in fixture mode for SIG-01 (N-02-T10; docs/contracts/c7-envelopes.md): the hub's list and
// summary on the live routes' shapes, from seed/signatures.ts, seen by Grace Holloway at E0 (Mon
// Sep 14, 2026, 9:24 AM CT). One scenario per artboard (a–g, r). Nothing here sends, voids or
// signs: Remind answers a preview only and Send is a person's (INV-1).
import type {
  EnvelopeListRow,
  EnvelopeSummary,
  ListPageEnvelopeListRow,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { stableId } from "../seed/prng";
import {
  COMPLETED,
  EXPIRED,
  HUB_COUNTS,
  type HubEnvelope,
  OUT,
  TO_SEND,
} from "../seed/signatures";

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
      { key: "consent_7216", n: HUB_COUNTS.byType.consents },
    ],
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
  };
}

const base = (state: string, handlers: Record<string, FixtureHandler>): Scenario => ({
  state,
  persona: SIG01_PERSONA,
  clock: SIG01_CLOCK,
  handlers,
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
  r: base("r", signaturesHandlers()),
});
