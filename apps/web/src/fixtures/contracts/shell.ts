// Names for parts of the generated types the SHL-03 and SHL-04 fixtures use. The /v1/me v3 drafts
// (P-01-T07) were retired by P-01-T08 once P-01-T04's `make generate` brought the real types.

import type {
  CapabilitiesOut,
  NotificationFeedData,
  NotificationItemOut,
} from "@abacus/api-client";

// --- /v1/me/capabilities nav (P-01-T04) --------------------------------------------------------

/** One SHL-03 admin row's access, computed from the matrix (`none` hides the row). */
export type NavAccess = NonNullable<CapabilitiesOut["nav"]>[string];

/** The five SHL-03 admin keys the fixtures answer for (AC 2.1.2); the wire type is a record. */
export type CapabilityNav = {
  firm_settings: NavAccess;
  users_roles: NavAccess;
  audit_log: NavAccess;
  security_center: NavAccess;
  developer_api: NavAccess;
};

// --- names for parts of the generated C16 types ---------------------------------------------

export type NotificationCategory = NotificationItemOut["category"];
export type InlineAction = NotificationItemOut["inline_actions"][number];
export type NotificationTab = NonNullable<NonNullable<NotificationFeedData["query"]>["tab"]>;
