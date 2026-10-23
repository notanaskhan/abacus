// The client portal's session basics (P-08-T07, T09, T11): where a signed-in person lands, and the
// access token, held in memory only by the portal auth client (app-core/auth/bff.ts: refresh
// through the host cookie, 401 to sign-in, sign-out). In app-core so the portal's entry and route
// tree reach it without the portal domain's design-system imports: the portal's first load stays
// inside its budget.

import type { PortalLanding } from "./portal-contracts";

export { portalAccessToken, setPortalAccessToken, setPortalSession } from "./auth/bff";

/** Where a signed-in person lands, by their portal scopes (DEC-129, P-08 Story 2.3). */
export const LANDING_PATH: Readonly<Record<PortalLanding, string>> = {
  home: "/",
  requests: "/requests",
  k1s: "/k1s",
  governance: "/governance",
  intake: "/intake",
  component_room: "/component-room",
  none: "/",
};
