// The client portal's session basics (P-08-T07, T09): where a signed-in person lands, and the
// access token, held in memory only, never in storage or a URL (P-08-T11 adds refresh through the
// host cookie). In app-core so the portal's entry and route tree reach it without the portal
// domain's design-system imports: the portal's first load stays inside its budget.

import type { PortalLanding } from "./portal-contracts";

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

let accessToken: string | null = null;

export function setPortalAccessToken(token: string | null): void {
  accessToken = token;
}

export function portalAccessToken(): string | null {
  return accessToken;
}
