import { FlagOffState } from "@abacus/ui";
import { Navigate, createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { appRoute, lazyScreen } from "../root";

// Home: `/` goes to `/home` when `home.dashboard` is on (I-01-T11); off, `/` and `/home` go to the
// engagements index (P-07-T58 retired the legacy landing, DEC-904), and HOME-01 makes no data
// call. HOME-01 is its own chunk (route-level lazy import), so the firm's initial bundle carries
// none of it.
const Home01 = lazyScreen(async () => (await import("../../screens/HOME-01")).HOME01);
const Home02 = lazyScreen(async () => (await import("../../screens/HOME-02")).HOME02);

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

// HOME-02 (I-01-T16): `/home/approvals` behind `home.approvals`; `?gate=` selects a row (an opaque
// id, ADR-031). Off: F-05's flag-off state, and HOME-01's rows open their host gates.
interface ApprovalsSearch {
  gate?: string;
}

export const homeApprovalsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/home/approvals",
  validateSearch: (search: Record<string, unknown>): ApprovalsSearch =>
    typeof search.gate === "string" && /^[0-9a-f-]{36}$/u.test(search.gate)
      ? { gate: search.gate }
      : {},
  component: function HomeApprovalsPage(): JSX.Element {
    // Loose hooks: the page also mounts in tests' routers (the same path, any tree).
    const navigate = useNavigate();
    const search: ApprovalsSearch = useSearch({ strict: false });
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate
          flag="home.approvals"
          fallback={<FlagOffState flag="home.approvals" label="Approvals" />}
        >
          <Home02
            gate={search.gate ?? null}
            onGate={(gate) => {
              void navigate({ to: ".", search: gate === null ? {} : { gate }, replace: true });
            }}
          />
        </FeatureGate>
      </div>
    );
  },
});

export const homeRoutes = [homeRoute, homeDashboardRoute, homeApprovalsRoute] as const;
