import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { useParam } from "./params";
import { lazyScreen, rootRoute } from "./root";

// The client portal and the sign-up and join pages: a tree beside the firm's (ADR-011; SPEC-015,
// SPEC-016). The portal entry and its own shell come with P-08.
const screens = {
  ClientHome: lazyScreen(async () => (await import("../legacy/ClientHome")).ClientHome),
  ClientEngagement: lazyScreen(
    async () => (await import("../legacy/ClientEngagement")).ClientEngagement,
  ),
  Join: lazyScreen(async () => (await import("../legacy/Join")).Join),
  Signup: lazyScreen(async () => (await import("../legacy/Signup")).Signup),
  ConnectCallback: lazyScreen(
    async () => (await import("../legacy/ConnectCallback")).ConnectCallback,
  ),
  Accept: lazyScreen(async () => (await import("../legacy/ClientAccept")).Accept),
};

const clientEngagementRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/client/engagements/$engagementId",
  component: function ClientEngagementPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.ClientEngagement engagementId={engagementId} />;
  },
});

function page<const P extends string>(path: P, component: () => JSX.Element) {
  return createRoute({ getParentRoute: () => rootRoute, path, component });
}

export const portalRoutes = [
  page("/client", () => <screens.ClientHome />),
  clientEngagementRoute,
  page("/client/connect/callback", () => <screens.ConnectCallback />),
  page("/signup", () => <screens.Signup />),
  page("/join", () => <screens.Join />),
  page("/client/accept", () => <screens.Accept />),
] as const;
