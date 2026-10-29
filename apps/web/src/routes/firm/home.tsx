import { Navigate, createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { appRoute, lazyScreen } from "../root";

// Home: `/` goes to `/home` when `home.dashboard` is on (I-01-T11); off, `/` and `/home` go to the
// engagements index (P-07-T58 retired the legacy landing, DEC-904), and HOME-01 makes no data
// call. HOME-01 is its own chunk (route-level lazy import), so the firm's initial bundle carries
// none of it.
const Home01 = lazyScreen(async () => (await import("../../screens/HOME-01")).HOME01);

export const homeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  component: function HomePage(): JSX.Element {
    // I-01-T11: with `home.dashboard` on, `/` is HOME-01 at `/home`; off, the engagements index.
    return (
      <FeatureGate flag="home.dashboard" fallback={<Navigate to="/engagements" replace />}>
        <Navigate to="/home" replace />
      </FeatureGate>
    );
  },
});

export const homeDashboardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/home",
  component: function HomeDashboardPage(): JSX.Element {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate flag="home.dashboard" fallback={<Navigate to="/engagements" replace />}>
          <Home01 />
        </FeatureGate>
      </div>
    );
  },
});

export const homeRoutes = [homeRoute, homeDashboardRoute] as const;
