// SHL-04 notifications panel: one fixture scenario per artboard (P-01-T07), plus b′ (nothing
// waiting), the Raj Malhotra Approvals variant and the Notification settings menu. Frames a–f
// stand at Mon Sep 14, 9:41 AM CT (the spec; the README renders them at "Thu Oct 1" for review);
// g and the settings menu at Thu Oct 1, 11:00 AM CT (R2). Data: fixtures/seed/notifications.ts.
//
// They live under fixtures/ (dev and test only, inside the L10 scan); src/screens/SHL-04/scenarios.ts
// re-exports them for the screen's tests and the gallery (P-01-T10).

import {
  type FixtureHandler,
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import type {
  DecisionOut,
  NotificationItemOut,
  NotificationPageOut,
  ReadAllOut,
  NotificationPreferenceOut,
  NotificationPreferencesIn,
  NotificationPreferencesOut,
  UndoneDecisionOut,
} from "@abacus/api-client";
import type { NotificationTab } from "../contracts/shell";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  R2_ROWS,
  RAJ_ROW,
  ROWS,
  ROW_D_REQUEST,
  SHL04_INSTANT,
  SHL04_R2_INSTANT,
  pageOf,
  preferences,
  toWire,
} from "../seed/notifications";
import { SEND_BACK_REASONS } from "../seed/screening";
import { capabilitiesFor, meV3For } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();
const A1 = seed.engagementIds.A1 ?? "";

const TABS: readonly NotificationTab[] = ["all", "approvals", "mentions", "client_activity"];

function tabOf(request: FixtureRequest): NotificationTab {
  const tab = request.query.get("tab") ?? "all";
  return (TABS as readonly string[]).includes(tab) ? (tab as NotificationTab) : "all";
}

interface Data {
  items: NotificationItemOut[];
  /** b′: the Approvals tab answers with nothing waiting. */
  approvalsEmpty?: boolean;
  /** c: the certified trust report request reads received (PBC 12 of 24). */
  accepted?: boolean;
  loading?: boolean;
}

function decision(request: FixtureRequest, kind: DecisionOut["decision"]): DecisionOut {
  const reason = (request.body as { reason_code?: string } | null)?.reason_code ?? null;
  return {
    id: `decision-${kind}-${request.params.version_id ?? ""}`,
    decision: kind,
    evidence_version_id: request.params.version_id ?? "",
    item_status: kind === "accept" ? "received" : "returned",
    reason_code: kind === "accept" ? null : reason,
    request_item_ids: [],
    corrects_proposal: false,
  };
}

function handlers(data: Data): Record<string, FixtureHandler> {
  let prefs: NotificationPreferenceOut[] = preferences();
  const prefsBody = (): NotificationPreferencesOut => ({ items: prefs });
  // Reading a row or all of them is the viewer's own state; later pages read it back (P-01-T10).
  let items = [...data.items];
  const unreadPage = (): NotificationPageOut => ({
    items: [],
    unread_count: items.filter((n) => !n.read).length,
  });
  const list: FixtureHandler = (request) => {
    if (data.loading === true) return never();
    const tab = tabOf(request);
    const page = pageOf(items, tab);
    if (data.approvalsEmpty === true) {
      page.counts.approvals = 0;
      if (tab === "approvals") page.items = [];
    }
    return json(page);
  };
  return {
    ...E0.handlers,
    "GET /v1/me": ({ persona }) => {
      const me = meV3For(seed, persona ?? "");
      return me === undefined ? json({ detail: "unknown_persona" }, 404) : json(me);
    },
    "GET /v1/me/capabilities": ({ persona }) => json(capabilitiesFor(seed, persona ?? "")),
    // C16 v1: the v2 list sits beside v1 at /feed during the overlap (contract §10).
    "GET /v1/notifications/feed": list,
    // The bell's dot reads v1's `unread_count` (SHL-01; P-01-T02).
    "GET /v1/notifications": () => json(unreadPage()),
    "POST /v1/notifications/{notification_id}/read": ({ params }) => {
      items = items.map((n) => (n.id === params.notification_id ? { ...n, read: true } : n));
      return json(unreadPage());
    },
    "POST /v1/notifications/read-all": () => {
      const marked: ReadAllOut = { marked: items.filter((n) => !n.read).length };
      items = items.map((n) => ({ ...n, read: true }));
      return json(marked);
    },
    // P-01-T10 follow-up: row d's inline Accept or Return, and the receipt's Undo (SHL-04 c).
    "GET /v1/engagements/{engagement_id}/review-reason-codes/{applies_to}": () =>
      json(SEND_BACK_REASONS),
    "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/accept": (r) =>
      json(decision(r, "accept"), 201),
    "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/send-back": (
      r,
    ) => json(decision(r, "send_back"), 201),
    "POST /v1/engagements/{engagement_id}/review-decisions/{decision_id}/undo": ({ params }) => {
      const undone: UndoneDecisionOut = {
        id: `undo-${params.decision_id ?? ""}`,
        undoes_decision_id: params.decision_id ?? "",
        evidence_version_id: "",
        item_status: "uploaded",
        request_item_ids: [],
      };
      return json(undone, 201);
    },
    "GET /v1/me/notification-preferences": () => json(prefsBody()),
    "PUT /v1/me/notification-preferences": ({ body }) => {
      const given = (body as Partial<NotificationPreferencesIn> | null)?.items ?? [];
      if (given.some((g) => !prefs.some((p) => p.kind === g.kind))) {
        return json({ detail: "unknown_kind" }, 422);
      }
      prefs = prefs.map((p) => given.find((g) => g.kind === p.kind) ?? p);
      return json(prefsBody());
    },
    ...(data.accepted === true
      ? {
          "GET /v1/engagements/{engagement_id}/request-items": (request: FixtureRequest) => {
            const items = seed.requestItems[request.params.engagement_id ?? ""];
            if (request.params.engagement_id !== A1 || items === undefined) {
              return (
                E0.handlers["GET /v1/engagements/{engagement_id}/request-items"]?.(request) ??
                json({ detail: "not_found" }, 404)
              );
            }
            return json(
              items.map((r) =>
                r.description === ROW_D_REQUEST ? { ...r, status: "received" as const } : r,
              ),
            );
          },
        }
      : {}),
  };
}

const hannah = ROWS.map((r) => toWire(seed, r));

const at = (
  state: string,
  data: Data,
  persona = "hannah-leclerc",
  clock = SHL04_INSTANT,
): Scenario => ({
  state,
  persona,
  clock,
  handlers: handlers(data),
});

export const scenarios = defineScenarios({
  /** Default: rows a–i, 4 unread, one inline document approval (row d). */
  a: at("a", { items: hannah }),
  /** Approvals tab: rows a, b and d (count 3); "Open approvals queue →". */
  b: at("b", { items: hannah }),
  /** Approvals with nothing waiting: "No approvals waiting on you." */
  bp: at("bp", { items: hannah, approvalsEmpty: true }),
  /** Raj Malhotra (close rights): the Approvals tab adds the Copperleaf AJE proposal. */
  b_raj: at("b_raj", { items: [...hannah, toWire(seed, RAJ_ROW)] }, "raj-malhotra"),
  /** After Accept: the receipt line with Undo; PBC 12 of 24. */
  c: at("c", { items: ROWS.map((r) => toWire(seed, r, { accepted: true })), accepted: true }),
  /** All read: no dots, and the bell dot is gone. */
  d: at("d", { items: ROWS.map((r) => toWire(seed, r, { read: true })) }),
  /** Empty (new user): "You're all caught up." */
  e: at("e", { items: [] }),
  /** Loading: the list never answers; 5 skeleton rows. */
  f: at("f", { items: [], loading: true }),
  /** R2 kinds at Thu Oct 1, 11:00 AM: a to-do, a template update and two trigger runs. */
  g: at("g", { items: R2_ROWS.map((r) => toWire(seed, r)) }, "hannah-leclerc", SHL04_R2_INSTANT),
  /** The Notification settings menu: the four R2 kinds, Mention email on. */
  settings: at(
    "settings",
    { items: R2_ROWS.map((r) => toWire(seed, r)) },
    "hannah-leclerc",
    SHL04_R2_INSTANT,
  ),
});
