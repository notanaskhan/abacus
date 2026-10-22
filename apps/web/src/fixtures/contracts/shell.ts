// Draft wire types for the SHL-03 fixtures (P-01-T07), until the `/v1/me` v3 and capability nav
// stub lands (P-01-T04). Each one starts from the generated type it extends, so a schema change to
// the existing fields still breaks the build. Shapes follow the P-01 epic §4.3 endpoint table.
// Delete this file when `make generate` brings the real types, and retype seed/shell.ts.
// (Notifications v2 is no longer a draft: the C16 stub, P-01-T01, generated its types.)

import type {
  CapabilitiesOut,
  MeOut,
  MembershipOut,
  NotificationFeedData,
  NotificationItemOut,
} from "@abacus/api-client";

// --- /v1/me v3 (P-01-T04) --------------------------------------------------------------------

/** One SHL-03 admin row's access, computed from the matrix (`none` hides the row). */
export type NavAccess = "write" | "read" | "none";

/** `GET /v1/me/capabilities` `nav`: the SHL-03 admin section, never a role name (AC 2.1.2). */
export interface CapabilityNavDraft {
  firm_settings: NavAccess;
  users_roles: NavAccess;
  audit_log: NavAccess;
  security_center: NavAccess;
  developer_api: NavAccess;
}

export type CapabilitiesV3Draft = CapabilitiesOut & { nav: CapabilityNavDraft };

/** `memberships[].firm`: the SHL-03 firm row's facts ("US · Central Time · 46 seats"). */
export interface MembershipFirmDraft {
  region: "US";
  time_zone: string;
  /** P-28 entitlements; null where the firm has none (the training sandbox). */
  seats_total: number | null;
  is_sandbox: boolean;
  /** The firm a sandbox was made from. */
  sandbox_of: string | null;
}

export type MembershipV3Draft = MembershipOut & { firm: MembershipFirmDraft };

export interface OfficeRefDraft {
  id: string;
  name: string;
}

export type MeV3Draft = Omit<MeOut, "memberships"> & {
  user: { initials: string | null; job_title: string | null };
  /** The default office filter; null reads "All offices". */
  default_office_id: string | null;
  /** The active tenant's offices, for the office submenu (SHL-03f). */
  offices: OfficeRefDraft[];
  memberships: MembershipV3Draft[];
};

/** `PUT /v1/me/preferences` (AC 2.1.3). */
export interface UserPreferencesDraft {
  default_office_id: string | null;
}

// --- names for parts of the generated C16 types ---------------------------------------------

export type NotificationCategory = NotificationItemOut["category"];
export type InlineAction = NotificationItemOut["inline_actions"][number];
export type NotificationTab = NonNullable<NonNullable<NotificationFeedData["query"]>["tab"]>;
