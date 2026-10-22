// SHL-04 notifications panel: one fixture scenario per artboard (P-01-T07), plus b′ (nothing
// waiting), the Raj Malhotra Approvals variant and the Notification settings menu. Frames a–f
// stand at Mon Sep 14, 9:41 AM CT (the spec; the README renders them at "Thu Oct 1" for review);
// g and the settings menu at Thu Oct 1, 11:00 AM CT (R2). Data: fixtures/seed/notifications.ts.
//
// They live under fixtures/ (dev and test only, inside the L10 scan; screens may not import across
// feature roots) until the SHL-04 screen task (P-01-T10) wires them into src/screens/SHL-04/.

import {
  type FixtureHandler,
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import type {
  NotificationItemOut,
  NotificationPreferenceOut,
  NotificationPreferencesIn,
  NotificationPreferencesOut,
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

function handlers(data: Data): Record<string, FixtureHandler> {
  let prefs: NotificationPreferenceOut[] = preferences();
  const prefsBody = (): NotificationPreferencesOut => ({ items: prefs });
  const list: FixtureHandler = (request) => {
    if (data.loading === true) return never();
    const tab = tabOf(request);
    const page = pageOf(data.items, tab);
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
