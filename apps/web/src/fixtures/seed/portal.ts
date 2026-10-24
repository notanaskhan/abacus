// The portal minimum (blueprint 01 §9.3; F-04 §2.1): the client-side people of Northwind, Granite
// Peak and the Feld household, and the third parties on Northwind's PBC list. Names are fictional;
// every mailbox is on the synthetic sink domain, never a real inbox (SPEC-307 AC-5).

import type { ClientContactOut } from "@abacus/api-client";
import { stableId } from "./prng";
import { slugOf } from "./people";

export const SINK_DOMAIN = "sink.brightwaterhale.test";

/** `whitley` has no engagement in the seed: Dana Whitley exists for T15a sign-in only (F-05-T33).
 * `copperleaf` and `tessellate` hold the P-08-T08 personas: Tess Moreno (POR-01c, POR-02d) and
 * Marisol Vega (POR-02h); their engagements arrive with C-01 and A-07. */
export type PortalEngagement =
  | "northwind"
  | "granite-peak"
  | "feld"
  | "whitley"
  | "copperleaf"
  | "tessellate"
  | "meera"
  | "ridgeline";

export interface PortalUser {
  slug: string;
  name: string;
  /** Their organisation when they are a third party or hold a title worth showing. */
  org: string;
  title: string;
  engagement: PortalEngagement;
  /** `tcwg` is the benefits committee (POR-15): it reads, and holds no contact role. `delegate`
   * holds `request_item` grants only (a third party's room, DEC-211): no contact role either. */
  role: "client_admin" | "client_contributor" | "tcwg" | "delegate";
  thirdParty: boolean;
  email: string;
  id: string;
}

type Row = readonly [
  name: string,
  org: string,
  title: string,
  engagement: PortalEngagement,
  role: PortalUser["role"],
  thirdParty?: true,
];

const ROWS: readonly Row[] = [
  [
    "Dana Kowalski",
    "Northwind Robotics, Inc.",
    "HR Director, plan administrator",
    "northwind",
    "client_admin",
  ],
  [
    "Victoria Lam",
    "Northwind Robotics, Inc.",
    "CFO, benefits committee chair",
    "northwind",
    "tcwg",
  ],
  ["Robert Haines", "Northwind Robotics, Inc.", "Benefits committee member", "northwind", "tcwg"],
  [
    "Sam Ortiz",
    "Keystone Retirement Services",
    "Recordkeeper",
    "northwind",
    "client_contributor",
    true,
  ],
  ["Luis Ferrante", "Granite Peak Outdoor Supply, Inc.", "CFO", "granite-peak", "client_admin"],
  ["Claire Feld", "Jonah & Claire Feld", "Primary portal user", "feld", "client_admin"],
  ["Jonah Feld", "Jonah & Claire Feld", "Household", "feld", "client_contributor"],
  // F-05-T33: TPL-15's T15a signs in as Dana Whitley; F-04's persona list had no one for it.
  ["Dana Whitley", "Marcus & Dana Whitley", "Primary portal user", "whitley", "client_admin"],
  // P-08-T08: POR-01c (an owner grant meets the MFA floor) and POR-02d; POR-02h.
  ["Tess Moreno", "Copperleaf Coffee Roasters, Inc.", "Owner", "copperleaf", "client_admin"],
  ["Marisol Vega", "Tessellate Health Cloud", "Primary portal user", "tessellate", "client_admin"],
  // POR-02e: Meera Shah's role union (her own return and her Ridgeline K-1).
  ["Meera Shah", "Meera Shah", "Primary portal user", "meera", "client_admin"],
  // R-01-T05: POR-04 e (Copperleaf's controller answers a question), POR-04 f (the general
  // partner decides Ridgeline's §754 election) and POR-14 d (Harborline's certifications contact,
  // a team mailbox that signs in under the name the custodian gave the firm).
  [
    "Ben Ashby",
    "Copperleaf Coffee Roasters, Inc.",
    "Controller",
    "copperleaf",
    "client_contributor",
  ],
  [
    "Owen Calder",
    "Ridgeline GP LLC",
    "Managing Member, Ridgeline GP LLC",
    "ridgeline",
    "client_admin",
  ],
  [
    "Harborline Certifications",
    "Harborline Trust Company",
    "Certifications contact",
    "northwind",
    "delegate",
    true,
  ],
];

export const PORTAL_USERS: readonly PortalUser[] = ROWS.map(
  ([name, org, title, engagement, role, thirdParty]) => {
    const slug = slugOf(name);
    return {
      slug,
      name,
      org,
      title,
      engagement,
      role,
      thirdParty: thirdParty === true,
      email: `${slug.replace(/-/g, ".")}@${SINK_DOMAIN}`,
      id: stableId(`user:${slug}`),
    };
  },
);

/** Third parties who answer Northwind requests but hold no portal user at E0 (Harborline's
 * certifications contact signs in for POR-14 d on Fri Sep 11, before the epoch). */
export const THIRD_PARTIES: readonly string[] = [
  "Harborline Trust Company",
  "PayGrid Payroll",
  "Summit Plan Administrators",
];

/** `GET /v1/engagements/{id}/client-contacts`: the people who hold a contact role. */
export function contactsOf(engagement: PortalEngagement): ClientContactOut[] {
  return PORTAL_USERS.filter(
    (u) => u.engagement === engagement && u.role !== "tcwg" && u.role !== "delegate",
  ).map((u) => ({
    kind: "member",
    id: u.id,
    role: u.role,
    email: u.email,
    expires_at: null,
    display_name: u.name,
  }));
}
