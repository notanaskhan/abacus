// A-02-T06: C20 v1 fixtures for POR-16 (docs/contracts/c20-integrations.md), from the POR-16
// handoff (README, spec, revision) and A-02 §3.9, never invented: Tess Moreno (Owner) on Copperleaf
// Coffee Roasters, Inc. at Mon Sep 14, 2026, 9:24 AM CT. QuickBooks Online connected by Tess on Mar
// 4, 2026, last sync 9:15 AM; Front Range Bank ••4410 (bank feed, daily, last sync 6:02 AM);
// American Express ••1009 needs reauth (asked Sep 10); Square (payouts and fees, last sync 6:00 AM);
// Shopify and a payroll provider not connected. c: 9:30 AM, the card is connecting; d: 9:31 AM,
// reconnected by Tess; e: Wed Mar 4, 2026, QuickBooks' first connect; g: Square's sync failed Sep
// 13. DF-19 masks the posting copy until P-16 (A-02 §3.9 AC-9.4; SPEC-333 AC-38): QuickBooks reads
// the ledger only, so "Post entries you approve" and the Approvals note are left out. Brightwater
// Hale, synthetic. The pytest half is backend/tests/contracts/c20_integrations/.
import type {
  ConnectionPersonOut,
  ConsentCopyOut,
  PortalConnectionCardOut,
  PortalConnectionsOut,
} from "@abacus/api-client";
import { SCOPE_IDS } from "./portal-home";
import { stableId } from "./prng";

/** The artboards' instants (POR-16 README), in UTC. */
export const POR16_CLOCKS = {
  a: "2026-09-14T09:24:00-05:00",
  c: "2026-09-14T09:30:00-05:00",
  d: "2026-09-14T09:31:00-05:00",
  e: "2026-03-04T09:24:00-06:00",
} as const;

export const COPPERLEAF_ENTITY_ID = SCOPE_IDS.copperleaf;
const id = (label: string): string => stableId(`connections:${label}`);

export const TESS: ConnectionPersonOut = {
  user_id: stableId("user:tess-moreno"),
  display_name: "Tess Moreno",
  kind: "client",
};

/** The consent sheet's toggle sentence (POR-16 b). */
const AUTHORIZATION =
  "I authorize Brightwater Hale LLP to access this account for the services in our engagement letter";

export const AMEX_CONSENT: ConsentCopyOut = {
  version: 1,
  title: "Reconnect American Express",
  will: ["Read statements and transactions for card ••1009", "Use them for your monthly close"],
  wont: ["Make payments or change your account", "See other cards on your login"],
  authorization: AUTHORIZATION,
  continue_label: "Continue to American Express",
  helper: "You'll sign in on American Express's site. Brightwater Hale never sees your password.",
};

/** POR-16 e with DF-19's mask: the disclosure reads the ledger only. */
export const QUICKBOOKS_CONSENT: ConsentCopyOut = {
  version: 1,
  title: "Connect QuickBooks Online",
  will: ["Brightwater Hale will read your ledger"],
  wont: [],
  authorization: AUTHORIZATION,
  continue_label: "Continue to QuickBooks Online",
  helper: null,
};

export const IDS = {
  quickbooks: id("quickbooks_online"),
  frontRange: id("front_range_bank"),
  amex: id("american_express"),
  square: id("square"),
} as const;

const QUICKBOOKS: PortalConnectionCardOut = {
  catalog_key: "quickbooks_online",
  name: "QuickBooks Online",
  category: "ledger",
  icon: "BookOpen",
  tone: "olive",
  status: "connected",
  status_reason: null,
  connection_id: IDS.quickbooks,
  display_label: null,
  connected_by: TESS,
  connected_at: "2026-03-04T15:00:00Z",
  reconnected: false,
  last_sync_at: "2026-09-14T14:15:00Z",
  last_failed_at: null,
  reauth_requested_at: null,
  helper: null,
  scopes: [{ code: "ledger.read", label: "Read ledger" }],
  consent: QUICKBOOKS_CONSENT,
  export_instead: { request_item_id: null, binder_id: null },
  version: 1,
  allowed_actions: ["details", "disconnect", "export_instead"],
};

const FRONT_RANGE: PortalConnectionCardOut = {
  catalog_key: "front_range_bank",
  name: "Front Range Bank",
  category: "bank_feed",
  icon: "Landmark",
  tone: "espresso",
  status: "connected",
  status_reason: null,
  connection_id: IDS.frontRange,
  display_label: "Front Range Bank ••4410",
  connected_by: null,
  connected_at: null,
  reconnected: false,
  last_sync_at: "2026-09-14T11:02:00Z",
  last_failed_at: null,
  reauth_requested_at: null,
  helper: "Bank feed · daily",
  scopes: [{ code: "transactions.read", label: "Read transactions and statements" }],
  consent: null,
  export_instead: null,
  version: 1,
  allowed_actions: ["details", "disconnect"],
};

const AMEX: PortalConnectionCardOut = {
  catalog_key: "american_express",
  name: "American Express",
  category: "card_feed",
  icon: "CreditCard",
  tone: "clay",
  status: "needs_reauth",
  status_reason: "token_expired",
  connection_id: IDS.amex,
  display_label: "American Express ••1009",
  connected_by: null,
  connected_at: null,
  reconnected: false,
  last_sync_at: null,
  last_failed_at: null,
  reauth_requested_at: "2026-09-10T15:00:00Z",
  helper: "American Express asks you to sign in again every 90 days.",
  scopes: [], // the artboard draws no tag on this card
  consent: AMEX_CONSENT,
  export_instead: null,
  version: 3,
  allowed_actions: ["reconnect", "details"],
};

const SQUARE: PortalConnectionCardOut = {
  catalog_key: "square",
  name: "Square",
  category: "sales",
  icon: "ShoppingBag",
  tone: "ochre",
  status: "connected",
  status_reason: null,
  connection_id: IDS.square,
  display_label: null,
  connected_by: null,
  connected_at: null,
  reconnected: false,
  last_sync_at: "2026-09-14T11:00:00Z",
  last_failed_at: null,
  reauth_requested_at: null,
  helper: "Payouts and fees · read only",
  scopes: [], // the artboard draws no tag on this card
  consent: null,
  export_instead: null,
  version: 1,
  allowed_actions: ["details", "disconnect"],
};

const SHOPIFY: PortalConnectionCardOut = {
  catalog_key: "shopify",
  name: "Shopify",
  category: "sales",
  icon: "ShoppingBag",
  tone: "ochre",
  status: "available",
  status_reason: null,
  connection_id: null,
  display_label: null,
  connected_by: null,
  connected_at: null,
  reconnected: false,
  last_sync_at: null,
  last_failed_at: null,
  reauth_requested_at: null,
  helper: "You upload payout reports each month instead.",
  scopes: [],
  consent: null,
  export_instead: null,
  version: 0,
  allowed_actions: ["connect"],
};

const PAYROLL: PortalConnectionCardOut = {
  catalog_key: "payroll_provider",
  name: "Payroll provider",
  category: "payroll",
  icon: "Users",
  tone: "espresso",
  status: "available",
  status_reason: null,
  connection_id: null,
  display_label: null,
  connected_by: null,
  connected_at: null,
  reconnected: false,
  last_sync_at: null,
  last_failed_at: null,
  reauth_requested_at: null,
  helper: "Connect your payroll provider to stop uploading registers.",
  scopes: [],
  consent: null,
  export_instead: null,
  version: 0,
  allowed_actions: ["connect"],
};

export type Por16State = "a" | "b" | "c" | "d" | "e" | "f" | "g";

function page(items: PortalConnectionCardOut[]): PortalConnectionsOut {
  return {
    entity: {
      client_entity_id: COPPERLEAF_ENTITY_ID,
      display_name: "Copperleaf Coffee Roasters, Inc.",
    },
    firm_display_name: "Brightwater Hale",
    items,
  };
}

/** The cards per artboard; b and f open an overlay over a's data (the sheet, the dialog). */
export function copperleafConnections(state: Por16State): PortalConnectionsOut {
  switch (state) {
    case "c":
      return page([
        QUICKBOOKS,
        FRONT_RANGE,
        { ...AMEX, status: "connecting", status_reason: null, allowed_actions: [] },
        SQUARE,
        SHOPIFY,
        PAYROLL,
      ]);
    case "d":
      return page([
        QUICKBOOKS,
        FRONT_RANGE,
        {
          ...AMEX,
          status: "connected",
          status_reason: null,
          connected_by: TESS,
          connected_at: "2026-09-14T14:31:00Z",
          reconnected: true,
          reauth_requested_at: null,
          version: 4,
          allowed_actions: ["details", "disconnect"],
        },
        SQUARE,
        SHOPIFY,
        PAYROLL,
      ]);
    case "e":
      // Wed Mar 4, 2026, onboarding: QuickBooks is the first connection.
      return page([
        {
          ...QUICKBOOKS,
          status: "available",
          connection_id: null,
          connected_by: null,
          connected_at: null,
          last_sync_at: null,
          version: 0,
          allowed_actions: ["connect", "export_instead"],
        },
      ]);
    case "g":
      return page([
        QUICKBOOKS,
        FRONT_RANGE,
        AMEX,
        {
          ...SQUARE,
          status: "needs_attention",
          status_reason: "sync_failed",
          last_failed_at: "2026-09-13T11:00:00Z",
          allowed_actions: ["retry", "details", "disconnect"],
        },
        SHOPIFY,
        PAYROLL,
      ]);
    default:
      return page([QUICKBOOKS, FRONT_RANGE, AMEX, SQUARE, SHOPIFY, PAYROLL]);
  }
}
