import { Navigate, createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { type JSX, Suspense, lazy } from "react";
import { useFlag } from "../../app-core/flags";
import { registerOverlay } from "../../app-core/overlays";
import { appRoute, lazyScreen } from "../root";

// Home: `/` goes to `/home` when `home.dashboard` is on (I-01-T11); off, `/` and `/home` go to the
// engagements index (P-07-T58 retired the legacy landing, DEC-904), and HOME-01 makes no data
// call. HOME-01 is its own chunk (route-level lazy import), so the firm's initial bundle carries
// none of it.
const Home01 = lazyScreen(async () => (await import("../../screens/HOME-01")).HOME01);
const Home02 = lazyScreen(async () => (await import("../../screens/HOME-02")).HOME02);
// I-02-T16: HOME-05 docks the Today brief beside HOME-01 behind `today_brief.enabled`.
const Home05 = lazyScreen(async () => (await import("../../screens/HOME-05")).HOME05);

export const homeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  component: function HomePage(): JSX.Element {
    // I-01-T23: `/` is HOME-01 at `/home` (`home.dashboard` retired).
    return <Navigate to="/home" replace />;
  },
});

export const homeDashboardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/home",
  component: function HomeDashboardPage(): JSX.Element {
    const brief = useFlag("today_brief.enabled") === true;
    return <div className="flex min-h-0 flex-1 flex-col">{brief ? <Home05 /> : <Home01 />}</div>;
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
        <Home02
          gate={search.gate ?? null}
          onGate={(gate) => {
            void navigate({ to: ".", search: gate === null ? {} : { gate }, replace: true });
          }}
        />
      </div>
    );
  },
});

export const homeRoutes = [homeRoute, homeDashboardRoute, homeApprovalsRoute] as const;

// I-02-T16: `?ov=today`, the Today panel as a left drawer (x10–480, no scrim) over any firm route,
// from the bell and "Open Today ›". Flag off: the overlay renders nothing.
const TodayDrawer = lazy(async () => ({
  default: (await import("../../screens/HOME-05")).TodayDrawer,
}));

function TodayOverlay({ close }: { close: () => void }): JSX.Element | null {
  const on = useFlag("today_brief.enabled") === true;
  if (!on) return null;
  return (
    <Suspense fallback={null}>
      <TodayDrawer onClose={close} />
    </Suspense>
  );
}

registerOverlay("today", {
  layer: "drawer",
  render: ({ close }) => <TodayOverlay close={close} />,
});
