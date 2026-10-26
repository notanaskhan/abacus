import { Navigate, createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { lazyScreen, rootRoute } from "./root";

// The client portal and the sign-up and join pages: a tree beside the firm's (ADR-011; SPEC-015,
// SPEC-016). The portal entry and its own shell come with P-08.
const screens = {
  ClientHome: lazyScreen(async () => (await import("../legacy/ClientHome")).ClientHome),
  Join: lazyScreen(async () => (await import("../legacy/Join")).Join),
  Signup: lazyScreen(async () => (await import("../legacy/Signup")).Signup),
  ConnectCallback: lazyScreen(
    async () => (await import("../legacy/ConnectCallback")).ConnectCallback,
  ),
  Accept: lazyScreen(async () => (await import("../legacy/ClientAccept")).Accept),
};

// R-01-T18 retired the legacy client engagement page (ClientEngagement.tsx): a client's documents
// are POR-03 and POR-04 at `/documents` in the portal entry. The old path stays only as a redirect
// to the legacy home, so links from ClientHome, ConnectCallback and the client's notifications land
// somewhere until P-08-T28 removes this whole tree (DEC-443).
const clientEngagementRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/client/engagements/$engagementId",
  component: function ClientEngagementRedirect(): JSX.Element {
    return <Navigate to="/client" replace />;
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
