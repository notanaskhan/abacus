// AUD-03 Source documents · PBC with viewer: one fixture scenario per artboard (A-01-T15;
// docs/screens/AUD-03.md). All seen by Ana Cruz (Staff, DV-3) on Northwind's PY2025 EBP audit:
//
//   a  Mon Sep 14, 9:41 AM  E0: BrokerWindow selected (Gordon Whitfield's holdings, SSNs masked)
//   b  9:41 AM              E0: the certified trust report (Match 94%, screened Sep 11)
//   c  Wed Sep 9, 9:41 AM   the matcher's 62% proposal on Schedule of Account Balances, flagged
//   d  as c                 "Return…" pressed (the screen opens the ReturnDialog)
//   e  9:41 AM              E0: the IRS opinion letter, requested from Dana Kowalski
//   f  Mon Sep 28, 9:41 AM  every Northwind request received ("late September")
//   g  Mon Sep 21, 9:41 AM  the rows due Sep 18 still requested read Overdue (derived)
//
// The rail and Source Documents aggregate are fixtures/handlers/audits.ts's over the seed, with the
// snapshot of seed/aud03.ts; the viewer documents, screening cards, decisions, follow-ups,
// delegation and the logged reveal answer here in the generated client's shapes. Each call to
// `scenarioFor` holds its own copy, so a test's Accept or Return never leaks into another.
// src/screens/AUD-03/scenarios.ts re-exports them.

import type {
  CapabilitiesOut,
  DecisionOut,
  DelegationOut,
  PiiRevealOut,
  SourceDocumentRowOut,
  SourceDocumentsOut,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { auditHandlers, northwindAuditId } from "../handlers/audits";
import { type FollowUpSpec, followUpHandlers } from "../handlers/follow-ups";
import { trustHandlers } from "../handlers/trust";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  AUD03_CITATIONS,
  AUD03_DOCUMENTS,
  BALANCES_TITLE,
  BROKERWINDOW_MASKS,
  BROKERWINDOW_TITLE,
  CERTIFIED_TITLE,
  IRS_LETTER_TITLE,
  WHITFIELD_SSN_REVEALED,
  allReceived,
  asOf,
  balancesCard,
  certificationCard,
  danaReminder,
  passedCard,
  recount,
  sep9,
} from "../seed/aud03";
import { northwindCockpit } from "../seed/audit-cockpit";
import { auditIndexRows, sourceDocuments } from "../seed/audits-index";
import { PORTAL_USERS } from "../seed/portal";
import { stableId } from "../seed/prng";
import { SEND_BACK_REASONS } from "../seed/screening";
import { capabilitiesFor } from "../seed/shell";
import { DOCUMENTS } from "../seed/trust";

const E0 = seedScenario();
const seed = getSeed();
const TODAY = new Date(seed.clock.ms).toISOString().slice(0, 10);

/** Every artboard is Northwind's PY2025 EBP audit (`$auditId`). */
export const AUDIT_ID = northwindAuditId(seed);
const FOUND = auditIndexRows(seed.engagements, seed.workItems, TODAY).find(
  (r) => r.work_item_id === AUDIT_ID,
);
if (FOUND === undefined) throw new Error("the seed has no Northwind audit");
const NORTHWIND = FOUND;
export const ENGAGEMENT_ID = NORTHWIND.engagement_id;
const BINDER_ID = stableId(`binder:${ENGAGEMENT_ID}:pbc`);
const NOT_FOUND = { detail: "not_found" };
const PERSONA = "ana-cruz";
const DANA = PORTAL_USERS.find((u) => u.name === "Dana Kowalski");

/** E0's aggregate (11 of 24) before any snapshot. */
function e0(): SourceDocumentsOut {
  return sourceDocuments(
    AUDIT_ID,
    BINDER_ID,
    seed.requestItems[ENGAGEMENT_ID] ?? [],
    seed.requestOwners,
    TODAY,
  );
}

/** The request a row title names in E0 (`?item=`). */
export function itemOf(title: string): string {
  const found = (e0().groups ?? []).flatMap((g) => g.rows ?? []).find((r) => r.title === title);
  if (found === undefined) throw new Error(`no request ${title}`);
  return found.request_item_id;
}

/** What Ana may do on the engagement: Staff with `staff_can_accept_evidence` on (DEC-37). */
export const ANA_ACTIONS = [
  "engagement.read_metadata",
  "request_item.read",
  "evidence.read",
  "evidence.accept",
  "evidence.reject",
  "evidence.upload",
  "follow_up.draft",
  "follow_up.send",
  "pii.reveal",
] as const;

export interface Aud03Options {
  /** The persona's actions on the engagement; Ana's by default. */
  actions?: readonly string[];
  /** DEC-369: an offshore reader gets the masked text view, never page images or a reveal. */
  textOnly?: boolean;
  /** The reveal answers 403 `mfa_required` (a stale step-up). */
  staleMfa?: boolean;
}

interface Snapshot {
  state: string;
  clock: string;
  docs: () => SourceDocumentsOut;
}

/** "Sample-driven · 0": not counted in the 24; A-03 populates it after Sample Selection. */
function withSampleBand(docs: SourceDocumentsOut): SourceDocumentsOut {
  return {
    ...docs,
    groups: [
      ...(docs.groups ?? []),
      {
        category_id: stableId(`category:${AUDIT_ID}:sample-driven`),
        label: "Sample-driven",
        received: 0,
        total: 0,
        counted: false,
        rows: [],
      },
    ],
  };
}

function capabilities(actions: readonly string[]): CapabilitiesOut {
  const base = capabilitiesFor(seed, PERSONA);
  return {
    ...base,
    capabilities: [...base.capabilities, ...actions],
    flags: { ...base.flags, "audits.cockpit": true },
  };
}

function handlers(snapshot: Snapshot, options: Aud03Options): Record<string, FixtureHandler> {
  let docs = snapshot.docs();
  const today = snapshot.clock.slice(0, 10);
  const rows = (): SourceDocumentRowOut[] => (docs.groups ?? []).flatMap((g) => g.rows ?? []);
  const patch = (id: string, edit: Partial<SourceDocumentRowOut>): void => {
    docs = recount({
      ...docs,
      groups: (docs.groups ?? []).map((g) => ({
        ...g,
        rows: (g.rows ?? []).map((r) => (r.request_item_id === id ? { ...r, ...edit } : r)),
      })),
    });
  };
  const mine = (request: FixtureRequest): boolean =>
    request.params.engagement_id === ENGAGEMENT_ID;
  const byVersion = (request: FixtureRequest): SourceDocumentRowOut | undefined =>
    rows().find((r) => r.latest_upload?.evidence_version_id === request.params.version_id);
  const decide = (request: FixtureRequest, decision: "accept" | "send_back"): Response => {
    const row = byVersion(request);
    if (!mine(request) || row === undefined || row.status !== "uploaded") {
      return json(NOT_FOUND, 404);
    }
    const reason =
      decision === "accept"
        ? null
        : ((request.body as { reason_code?: string } | null)?.reason_code ?? null);
    const status = decision === "accept" ? "received" : "returned";
    patch(row.request_item_id, { status, returned_reason: reason });
    const body: DecisionOut = {
      id: stableId(`decision:${request.params.version_id ?? ""}:${decision}`),
      decision,
      evidence_version_id: request.params.version_id ?? "",
      reason_code: reason,
      item_status: status,
      request_item_ids: [row.request_item_id],
      corrects_proposal: false,
    };
    return json(body, 201);
  };
  const ana = seed.people.find((p) => p.slug === PERSONA)?.userId ?? "";
  // Dana's open requests, drafted as one reminder (DEC-421); nothing else has a designed body.
  const followUps = followUpHandlers(
    (asked): FollowUpSpec[] => {
      const ids = new Set(asked.request_item_ids ?? []);
      const hers = rows().filter(
        (r) =>
          ids.has(r.request_item_id) &&
          (r.status === "requested" || r.status === "returned") &&
          r.owed_by?.display === "Dana Kowalski",
      );
      if (hers.length === 0 || DANA === undefined) return [];
      return [
        {
          engagementId: ENGAGEMENT_ID,
          binderId: BINDER_ID,
          recipientUserId: DANA.id,
          recipientName: DANA.name,
          body: danaReminder(hers.length, hers.filter((r) => r.overdue).length),
          items: hers.map((r) => ({
            id: r.request_item_id,
            title: r.title,
            due_on: r.due_on ?? null,
            overdue: r.overdue,
          })),
        },
      ];
    },
    () => ana,
  );
  const audits = auditHandlers(seed, "run");
  return {
    ...E0.handlers,
    ...trustHandlers({
      documents: { ...DOCUMENTS, ...AUD03_DOCUMENTS },
      citations: AUD03_CITATIONS,
      ...(options.textOnly === true ? { textOnly: true } : {}),
    }),
    ...audits,
    ...followUps,
    "GET /v1/me/capabilities": () =>
      json(
        capabilities(
          (options.actions ?? ANA_ACTIONS).filter(
            (a) => !(options.textOnly === true && a === "pii.reveal"),
          ),
        ),
      ),
    "GET /v1/audits/{work_item_id}/cockpit": async (request) => {
      const found = await audits["GET /v1/audits/{work_item_id}/cockpit"]?.(request);
      if (found === undefined || found.status !== 200) return found ?? json(NOT_FOUND, 404);
      // The rail's "n of 24 received" follows this scenario's own rows (b: 12 after Accept).
      return json(
        northwindCockpit(
          {
            workItemId: AUDIT_ID,
            engagementId: ENGAGEMENT_ID,
            clientId: NORTHWIND.client_id,
          },
          "run",
          docs.received,
          docs.total,
        ),
      );
    },
    "GET /v1/audits/{work_item_id}/source-documents": (request) => {
      if (request.params.work_item_id !== AUDIT_ID) return json(NOT_FOUND, 404);
      const sort = request.query.get("sort") === "received_first" ? "received_first" : undefined;
      return json(withSampleBand(recount(asOf(docs, today), sort)));
    },
    "GET /v1/engagements/{engagement_id}/request-items/{item_id}/screening": (request) => {
      const row = rows().find((r) => r.request_item_id === request.params.item_id);
      if (!mine(request) || row?.screening == null) return json(NOT_FOUND, 404);
      if (row.title === CERTIFIED_TITLE && row.match_confidence === 94) {
        return json(certificationCard(row.request_item_id));
      }
      if (row.title === BALANCES_TITLE && row.screening === "flagged") {
        return json(balancesCard(row.request_item_id));
      }
      return json(
        passedCard(row.request_item_id, row.title, row.latest_upload?.uploaded_on ?? TODAY),
      );
    },
    "GET /v1/engagements/{engagement_id}/review-reason-codes/{applies_to}": (request) =>
      mine(request) ? json(SEND_BACK_REASONS) : json(NOT_FOUND, 404),
    "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/accept": (r) =>
      decide(r, "accept"),
    "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/send-back": (
      r,
    ) => decide(r, "send_back"),
    "POST /v1/engagements/{engagement_id}/request-items/{item_id}/delegate": (request) => {
      const row = rows().find((r) => r.request_item_id === request.params.item_id);
      const contact = (request.body as { contact_id?: string } | null)?.contact_id ?? "";
      if (!mine(request) || row === undefined || contact === "") return json(NOT_FOUND, 404);
      const body: DelegationOut = {
        contact_id: contact,
        grant_id: stableId(`grant:${row.request_item_id}:${contact}`),
        granted_at: snapshot.clock,
        granted_by: ana,
        request_item_id: row.request_item_id,
      };
      return json(body, 201);
    },
    "POST /v1/evidence-versions/{version_id}/pii-reveals": (request) => {
      if (options.staleMfa === true) {
        return json({ detail: "forbidden", facts: { reason: "mfa_required" } }, 403);
      }
      const region = (request.body as { region_id?: string } | null)?.region_id;
      const mask = BROKERWINDOW_MASKS[0];
      if (mask === undefined || region !== mask.id) return json(NOT_FOUND, 404);
      const body: PiiRevealOut = {
        mask_id: mask.id,
        kind: "ssn",
        value: WHITFIELD_SSN_REVEALED,
        expires_in: 30,
        revealed_at: snapshot.clock,
        revealed_by: ana,
      };
      return json(body, 201);
    },
  };
}

const AT_941 = "T09:41:00-05:00";
const SNAPSHOTS = {
  a: { state: "a", clock: `2026-09-14${AT_941}`, docs: e0 },
  b: { state: "b", clock: `2026-09-14${AT_941}`, docs: e0 },
  c: { state: "c", clock: `2026-09-09${AT_941}`, docs: () => sep9(e0()) },
  d: { state: "d", clock: `2026-09-09${AT_941}`, docs: () => sep9(e0()) },
  e: { state: "e", clock: `2026-09-14${AT_941}`, docs: e0 },
  f: { state: "f", clock: `2026-09-28${AT_941}`, docs: () => allReceived(e0()) },
  g: { state: "g", clock: `2026-09-21${AT_941}`, docs: e0 },
} as const satisfies Record<string, Snapshot>;

export type Aud03State = keyof typeof SNAPSHOTS;

/** A fresh scenario for one artboard (its own rows), with the options a test varies. */
export function scenarioFor(state: Aud03State, options: Aud03Options = {}): Scenario {
  const snapshot = SNAPSHOTS[state];
  return {
    state,
    persona: PERSONA,
    clock: snapshot.clock,
    handlers: handlers(snapshot, options),
  };
}

export const scenarios = defineScenarios({
  a: scenarioFor("a"),
  b: scenarioFor("b"),
  c: scenarioFor("c"),
  d: scenarioFor("d"),
  e: scenarioFor("e"),
  f: scenarioFor("f"),
  g: scenarioFor("g"),
});

/** The row each artboard opens on and whether "Return…" is pressed (d). */
export const OPENS: Readonly<Record<Aud03State, { item: string; returning?: boolean }>> = {
  a: { item: itemOf(BROKERWINDOW_TITLE) },
  b: { item: itemOf(CERTIFIED_TITLE) },
  c: { item: itemOf(BALANCES_TITLE) },
  d: { item: itemOf(BALANCES_TITLE), returning: true },
  e: { item: itemOf(IRS_LETTER_TITLE) },
  f: { item: itemOf(BROKERWINDOW_TITLE) },
  g: { item: itemOf("W-3 Form") },
};
