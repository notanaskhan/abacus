import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { appRoute, lazyScreen } from "../root";

// Home: `/` is today the engagements index with what's waiting on you (TASK-093, TASK-102) until
// I-01-T13 points it at `/home`. `/home` is HOME-01 (I-01-T06) behind `home.dashboard`; with the
// flag off it is the same legacy landing, and HOME-01 makes no data call. HOME-01 is its own chunk
// (route-level lazy import), so the firm's initial bundle carries none of it.
const Engagements = lazyScreen(async () => (await import("../../legacy/Engagements")).Engagements);
const Home01 = lazyScreen(async () => (await import("../../screens/HOME-01")).HOME01);

export const homeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  component: function HomePage() {
    return <Engagements />;
  },
});

export const homeDashboardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/home",
  component: function HomeDashboardPage(): JSX.Element {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate flag="home.dashboard" fallback={<Engagements />}>
          <Home01 />
        </FeatureGate>
      </div>
    );
  },
});

export const homeRoutes = [homeRoute, homeDashboardRoute] as const;
